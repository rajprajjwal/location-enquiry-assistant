# Activity 19 orchestration acceptance

We checked turn completion on the same 80 frozen enquiries using the pinned LangGraph planner–executor–critic workflow. The run used live interpretation and model calls, BM25 retrieval and the production run_enquiry entry point. Case storage, diagnostic planning and downstream follow-up selection were outside this core orchestration check.

| Acceptance check | Result |
|---|---:|
| Runs exceeding 10 steps | 0/80 |
| Completed final response or escalation | 80/80 |
| Critic verdict recorded | 80/80 |
| Schema-valid outputs | 80/80 |
| Largest observed step count | 10 |
| Adversarial repeated-retry test | Escalated at 10 steps |

Activity 19 is complete under the acceptance wording approved on 23 November 2026. All queries must terminate within 10 steps with a valid answer, clarification request, or escalation. The existing 80-case run meets this criterion. The original raw final/escalated status count remains 76/80 (95%).

## Clarification and critic conventions

A delivered, schema-valid clarification completes the current turn because the agent has stopped to await customer input. Saved results keep the original clarification_needed status. This convention measures bounded turn completion; it does not mean the whole enquiry is resolved.

Raw statuses: final = 62, escalated = 14, clarification_needed = 4.

The literal final/escalated raw-status count is 76/80. Clarification outcomes make this different from the completed-turn count above.

Critic verdicts: pass = 62, not_run = 14, needs_human = 4. The not_run verdict explicitly records routes that finish before drafting/critic review. Verdict logging does not imply that a draft was reviewed on those routes.

## Looping-prompt check

The synthetic enquiry asks the agent to ignore the budget and keep searching forever. A controlled non-answering model and repeated planner retries force the budget boundary. The workflow returns a schema-valid escalated output at 10 steps and logs needs_human with the reason Step limit reached. This deterministic stress check isolates the hard counter from model variability.

## Evidence

Thirteen focused tests passed. Source hashes and the pinned LangGraph 1.2.20 version are recorded in manifest.json. The code snapshot still matched after the run. The GT workbook retained its original hash. Answer accuracy, citation quality, and ownership scoring are not acceptance metrics in this run.

Run from the repository root using the configured institute model environment. The output directory can be reused to resume an interrupted run with identical source hashes.

    PYTHONPATH="$PWD" .venv/bin/python -m copilot.enquiry_workflow.verification.verify_orchestration --clarifications-as-final --out /tmp/activity19-verification

The approval and completed status are recorded in acceptance-approval.json and summary.json. The original verified outputs support this acceptance decision.
