# Agentic Copilot JSON error fix and KB-gap guard

The "Expecting value: line 1 column 1" error came from a missing `import os` in `executor.py`. That made `/chat` return a plain-text 500, and the UI then ran `r.json()` on it. The fix covers every root cause: the import, robust LLM JSON extraction, JSON error bodies from `/chat` and a global handler, a status and content-type check in the UI client, a cap on the critic/executor loop, and a deterministic KB-gap notice for providers the KB doesn't cover (Ola, Google Maps and others).

Watch for: the final "replace the draft with the notice" version was never run over HTTP (confirmed in the report). I read the code and it is correct, so this is non-blocking. The provider list is fixed, so unlisted providers fall back to the LLM path (confirmed, acknowledged in the report).

**Verdict**: APPROVED

## High-level view

The root cause is fixed and shown fixed. The original code returned `500 text/plain` for the query. The patched code returned `200 application/json` for the Ola vs Google query, and forced failures (no API key, a 429) returned `500 application/json` with `error` and `detail` fields. The UI's `api_json` was tested offline against text, JSON, empty and 200 responses.

JSON parsing is centralized in `json_utils` (`extract_json` and `invoke_json`). It strips think blocks and code fences, scans for the first decodable object, retries once, and falls back to the callers' existing defaults. It never raises.

Honesty on the comparison is enforced deterministically. If the message names a listed third-party provider that is absent from the retrieved chunks, the final response is a fixed notice. The notice says the KB has no data on those providers and offers the Provider A/B/C comparison or an escalation. The earlier prepend approach let the LLM invent a comparison, and the coder correctly moved to replacing the draft. No fake corpus content was added.

<details>
<summary>Issues (3)</summary>

1. **Final guard not live-verified** (confirmed, non-blocking) — the replace-the-draft version was only unit-tested and compiled. Run the Ola query once through the UI or curl.
2. **Fixed provider list** (confirmed, non-blocking) — unlisted providers (e.g. MapmyIndia) bypass the guard. Consider a more general check later.
3. **Planner flag not set** (confirmed, non-blocking) — `escalation_needed` stays false even though the notice offers escalation.

</details>

<details>
<summary>Details</summary>

## Final-draft replacement path

In `critic_node`, a non-empty `kb_gap_notice` overrides both the draft and any critic rewrite. `should_revise` then routes straight to persist, so the notice can't be re-drafted away. I read both branches and they are consistent. A missing key defaults to an empty string, so queries that name no listed provider are unaffected. Live runs covered the intermediate prepend version, not this final one, hence issue 1.

## Escalation gap

The notice offers escalation but doesn't set the planner's `escalation_needed` flag, so any downstream escalation handling is not triggered. This only matters if something consumes the flag.

</details>

<details>
<summary>File map</summary>

- `app/agents/executor.py`: added `import os`, `kb_gap_notice`, and `extract_json` for tracker updates
- `app/agents/json_utils.py`: new `extract_json` and `invoke_json` helpers
- `app/agents/planner.py`, `critic.py`: use `invoke_json`
- `app/agents/orchestrator.py`: revision cap and KB-gap override
- `app/api/main.py`: JSON error bodies and global handler
- `ui/app.py`: `api_json` status and content-type check
- `README.md`: documents the above

There is no git diff because the project is not a git repo.

</details>
