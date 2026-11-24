# Source history: Raj Kumar (a3ef3a6); see source-history.json.
from dotenv import load_dotenv

# Load .env before any app module reads os.getenv(), so the API works however it
# is started (run_api.py, `uvicorn app.api.main:app`, ...). Without this, plain
# uvicorn has no OPENAI_API_KEY and every /chat call fails with HTTP 500.
load_dotenv()

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.models import init_db, get_db
from app.agents.orchestrator import run_workflow
from app.tools.tracker import approve_update, get_tracker_summary
from app.tools.history import get_history, get_audit_trail, get_or_create_conversation
from app.baseline.prompting import run_baseline
from app.kb.evaluator import run_retrieval_eval, run_full_eval, BUILTIN_GT_RECORDS
import logging
import uuid

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Location Services Copilot", version="1.0.0", lifespan=lifespan)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Always return a JSON body so clients never get plain-text 'Internal Server Error'."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={
        "error": "internal_error",
        "detail": f"{type(exc).__name__}: {exc}",
    })


# ── Request / Response models ──────────────────────────────────────────────────

class ChatRequest(BaseModel):
    conversation_id: str | None = None
    workflow: str = "sales"          # "sales" | "support"
    message: str
    params: dict | None = None       # optional diagnostic params


class ApproveRequest(BaseModel):
    conversation_id: str


class BaselineRequest(BaseModel):
    query: str
    workflow: str = "sales"


class RagEvalRequest(BaseModel):
    mode: str = "retrieval"   # "retrieval" | "full"
    k: int = 4
    use_llm_judge: bool = False
    record_ids: list[str] | None = None  # None = run all built-in GT records


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.post("/chat")
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    if req.workflow not in ("sales", "support"):
        raise HTTPException(400, "workflow must be 'sales' or 'support'")

    conv_id = req.conversation_id or str(uuid.uuid4())
    try:
        get_or_create_conversation(db, conv_id, req.workflow)
        result = run_workflow(conv_id, req.workflow, req.message, req.params)
    except Exception as e:
        logger.exception("chat workflow failed (conversation_id=%s)", conv_id)
        return JSONResponse(status_code=500, content={
            "error": "workflow_failed",
            "detail": f"{type(e).__name__}: {e}",
            "conversation_id": conv_id,
        })
    return {"conversation_id": conv_id, **result}


@app.post("/approve-update")
def approve(req: ApproveRequest, db: Session = Depends(get_db)):
    result = approve_update(db, req.conversation_id)
    return result


@app.get("/tracker/{conversation_id}")
def tracker(conversation_id: str, db: Session = Depends(get_db)):
    return get_tracker_summary(db, conversation_id)


@app.get("/history/{conversation_id}")
def history(conversation_id: str, db: Session = Depends(get_db)):
    return get_history(db, conversation_id)


@app.get("/audit/{conversation_id}")
def audit(conversation_id: str, db: Session = Depends(get_db)):
    return get_audit_trail(db, conversation_id)


@app.post("/baseline")
def baseline(req: BaselineRequest):
    """Run all 3 prompting strategies against the same query and return comparison."""
    return run_baseline(req.query, req.workflow)


@app.post("/rag-eval")
def rag_eval(req: RagEvalRequest):
    """
    Evaluate RAG pipeline against built-in GT records.
    mode=retrieval  — Layer 1 only: Recall@k, no LLM calls (fast)
    mode=full       — Layer 1 + Layer 2: Recall@k + answer quality (slow)
    """
    records = BUILTIN_GT_RECORDS
    if req.record_ids:
        records = [r for r in records if r.id in req.record_ids]
    if req.mode == "full":
        from dataclasses import asdict
        report = run_full_eval(records, use_llm_judge=req.use_llm_judge)
    else:
        report = run_retrieval_eval(records, k=req.k)
    from dataclasses import asdict
    return asdict(report)


@app.get("/health")
def health():
    return {"status": "ok"}
