# Source history: Raj Kumar (a3ef3a6); see source-history.json.
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from app.agents.planner import run_planner
from app.agents.executor import run_executor
from app.agents.critic import run_critic
from app.tools.tracker import get_tracker_summary, propose_update
from app.tools.history import get_history, add_message, log_audit
from app.db.models import SessionLocal


class AgentState(TypedDict):
    conversation_id: str
    workflow: str
    user_message: str
    params: dict
    history: list
    tracker_summary: dict
    planner_output: dict
    executor_output: dict
    critic_output: dict
    final_response: str
    sources: list
    pending_tracker_updates: dict
    audit_trail: list
    revisions: int


# Max Critic → Executor re-draft loops. Without a cap a persistently rejecting
# Critic loops until LangGraph's recursion limit raises GraphRecursionError.
MAX_REVISIONS = 1


def planner_node(state: AgentState) -> AgentState:
    result = run_planner(
        state["workflow"], state["user_message"],
        state["history"], state["tracker_summary"]
    )
    db = SessionLocal()
    log_audit(db, state["conversation_id"], "planner", "plan_generated", result)
    db.close()
    return {**state, "planner_output": result}


def executor_node(state: AgentState) -> AgentState:
    result = run_executor(
        state["workflow"], state["user_message"],
        state["history"], state["planner_output"], state["params"]
    )
    db = SessionLocal()
    log_audit(db, state["conversation_id"], "executor", "response_drafted", {
        "sources_count": len(result["sources"]),
        "tracker_updates": result["tracker_updates"],
    })
    db.close()
    return {**state, "executor_output": result, "sources": result["sources"]}


def critic_node(state: AgentState) -> AgentState:
    result = run_critic(
        state["executor_output"]["draft_response"],
        state["executor_output"]["sources"],
        state["planner_output"],
    )
    db = SessionLocal()
    log_audit(db, state["conversation_id"], "critic", "review_complete", result)
    db.close()

    if not result.get("approved", True) and result.get("suggested_revision"):
        final = result["suggested_revision"]
    else:
        final = state["executor_output"]["draft_response"]
    # KB-gap guard: the user named a provider the KB has no data on. The LLM
    # draft (and any critic rewrite) tends to invent a comparison anyway, so the
    # deterministic notice replaces it.
    notice = state["executor_output"].get("kb_gap_notice", "")
    if notice:
        final = notice
    return {**state, "critic_output": result, "final_response": final,
            "revisions": state.get("revisions", 0) + 1}


def persist_node(state: AgentState) -> AgentState:
    db = SessionLocal()
    add_message(db, state["conversation_id"], "user", state["user_message"])
    add_message(db, state["conversation_id"], "assistant", state["final_response"],
                sources=state["sources"])

    tracker_updates = state["executor_output"].get("tracker_updates", {})
    if tracker_updates:
        propose_update(db, state["conversation_id"], state["workflow"], tracker_updates)

    db.close()
    return {**state, "pending_tracker_updates": tracker_updates}


def should_revise(state: AgentState) -> str:
    critic = state.get("critic_output", {})
    if state.get("revisions", 0) > MAX_REVISIONS:
        return "persist"
    if state.get("executor_output", {}).get("kb_gap_notice"):
        return "persist"  # final response is the fixed KB-gap notice; re-drafting can't change it
    if not critic.get("approved", True) and critic.get("suggested_revision"):
        return "executor"
    return "persist"


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)
    graph.add_node("planner", planner_node)
    graph.add_node("executor", executor_node)
    graph.add_node("critic", critic_node)
    graph.add_node("persist", persist_node)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", "critic")
    graph.add_conditional_edges("critic", should_revise, {"executor": "executor", "persist": "persist"})
    graph.add_edge("persist", END)

    return graph.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def run_workflow(conversation_id: str, workflow: str, user_message: str, params: dict = None) -> dict:
    db = SessionLocal()
    history = get_history(db, conversation_id)
    tracker_summary = get_tracker_summary(db, conversation_id)
    db.close()

    initial_state = AgentState(
        conversation_id=conversation_id,
        workflow=workflow,
        user_message=user_message,
        params=params or {},
        history=history,
        tracker_summary=tracker_summary,
        planner_output={},
        executor_output={},
        critic_output={},
        final_response="",
        sources=[],
        pending_tracker_updates={},
        audit_trail=[],
        revisions=0,
    )

    result = get_graph().invoke(initial_state)
    return {
        "response": result["final_response"],
        "planner": result["planner_output"],
        "critic": result["critic_output"],
        "sources": result["sources"],
        "pending_tracker_updates": result["pending_tracker_updates"],
    }
