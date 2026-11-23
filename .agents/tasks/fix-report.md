# Fix report: "Error: Expecting value: line 1 column 1 (char 0)" in Agentic Copilot UI

## Symptom
In the Streamlit UI (Agentic Copilot tab), asking
"give me the comparison of location changes/details between Ola Maps and Google Maps"
showed `Error: Expecting value: line 1 column 1 (char 0)`.

## Root causes

1. **`NameError: name 'os' is not defined` in `app/agents/executor.py`.**
   `_parse_executor_response` calls `os.path.basename(...)`, but `os` was never imported.
   Every `/chat` request crashed after the executor's LLM call, so FastAPI returned
   `500 text/plain "Internal Server Error"`.
   Reproduced on the original code:
   `== ola_vs_google: 500 text/plain; charset=utf-8 -> Internal Server Error`, with traceback
   ending `executor.py, line 76 ... NameError: name 'os' is not defined`.
2. **The UI called `r.json()` without checking the response.** `ui/app.py` ran `r.json()` on that
   plain-text 500 body. That raised the JSON decode error the user saw, and the UI's generic
   `except Exception` displayed it.
3. **The Critic → Executor revision loop had no limit** (found while reproducing). The executor
   never receives the critic's feedback, so a critic that keeps rejecting loops
   executor ↔ critic until LangGraph's recursion limit (25) raises `GraphRecursionError`. That was
   another plain-text 500. The audit log showed 12+ executor/critic cycles for a single support query.
4. **Fragile LLM JSON parsing.** Planner and critic used bare `json.loads(response.content)`.
   Errors were caught, but `<think>` blocks, code fences, prose or empty output all fell straight
   to the fallback with no extraction attempt and no retry. Executor `TRACKER_UPDATES` had the
   same problem.

## Files changed
| File | Change |
|------|--------|
| `app/agents/executor.py` | Added `import os`; `TRACKER_UPDATES` parsed with `extract_json` (`{}` if none) |
| `app/agents/json_utils.py` (new) | `extract_json()`: strips `<think>…</think>` and code fences, tries the whole text, then scans for the first decodable `{...}`; never raises. `invoke_json()`: calls the LLM, parses, retries once on empty or unparsable output, then returns the caller's fallback |
| `app/agents/planner.py` | Uses `invoke_json` (fallback unchanged: `{"raw", "parse_error": True}`) |
| `app/agents/critic.py` | Uses `invoke_json` (fallback unchanged: approved=True, confidence=0.7) |
| `app/agents/orchestrator.py` | `revisions` state field and `MAX_REVISIONS = 1`: at most one re-draft, then persist. The existing rule still applies, so an unapproved draft is replaced by the critic's `suggested_revision` |
| `app/api/main.py` | `/chat` wraps the workflow in try/except, logs the traceback, and returns `500 {"error":"workflow_failed","detail":"<Type>: <msg>","conversation_id"}`. Global `Exception` handler returns `500 {"error":"internal_error","detail"}` for every endpoint |
| `ui/app.py` | New `api_json(r)` checks status and content-type before decoding and raises `APIError("API returned HTTP <code>: <detail or body>")`. Used for every API call (chat, baseline, tracker, approve, audit) |
| `README.md` | Documented the JSON error shapes, the revision cap, the `revisions` state field and the new parse fallbacks (replaced the "no explicit revision cap" note) |

## Commands run and verification output
The shell tool was unreliable, so HTTP calls ran from a temporary script (`tmp_repro.py`, now
deleted) using `httpx`, with output written to a file. Servers were started with:
```
python -m uvicorn app.api.main:app --host 127.0.0.1 --port <port> --env-file .env
```
Port 8010 was used for final verification because port 8000 is also bound by the user's own
`python run_api.py` (PID 34588, `0.0.0.0:8000`, started before this session). That server was
**not** touched, and it answered some of the early test requests on 8000.

**Before fix (port 8000, original code):**
```
== health: 200 application/json        {"status":"ok"}
== ola_vs_google: 500 text/plain        Internal Server Error   (NameError: os)
```

**After fix (port 8010, final code), sequential requests:**
```
== health:          200 application/json (1s)  {"status":"ok"}
== ola_vs_google:   200 application/json (23s) {"conversation_id":"6093c7d3-…","response":"To provide a comprehensive comparison of location changes and details between Ola Maps and Google Maps, we need to gather more information about your specific use case, the number of devices … (8 qualification questions) …","planner":{"enquiry_type":"qualification",…,"escalation_needed":false},"critic":{"approved":true,"confidence":0.95,…}
== sales_normal:    200 application/json (18s) {"response":"Based on your requirement to track 500 delivery vehicles … the **Enterprise Plan** … [KB-3] …", …}
== support_normal:  200 application/json (29s) {"response":"The error appears to be related to a rate limit …","critic":{"approved":false,"confidence":0.65,…,"suggested_revision":"…"}}   <- revision cap working: finished instead of looping
== bad_workflow:    400 application/json (0s)  {"detail":"workflow must be 'sales' or 'support'"}
== bad_body:        422 application/json (0s)  {"detail":[{"type":"missing","loc":["body","message"],"msg":"Field required",…}]}
```

**Forced failures return JSON, not plain text:**
- Server on port 8001 started without `.env` (no API key):
  `== ola_vs_google: 500 application/json {"error":"workflow_failed","detail":"ValidationError: 1 validation error for ChatOpenAI … Did not find openai_api_key …","conversation_id":"3c26cf43-…"}`
- Concurrent requests overloaded the vLLM key (observed during testing):
  `500 application/json {"error":"workflow_failed","detail":"RateLimitError: Error code: 429 - {'detail': 'per-key concurrent request limit exceeded'}",…}`

**Offline checks (`tmp_unit.py`, deleted):**
```
compile OK: json_utils.py, planner.py, critic.py, executor.py, orchestrator.py, main.py, ui/app.py
extract_json: empty->None, fenced->{'a':1}, "<think>…</think>prose {"a":2} prose"->{'a':2}, no_json->None, plain->{'a':3}, unclosed <think>->None
ui api_json: 500 text/plain   -> "Error: API returned HTTP 500: Internal Server Error"
             500 json         -> "Error: API returned HTTP 500: RateLimitError: 429"
             200 empty body   -> "Error: API returned HTTP 200: empty response body"
             200 json         -> returns dict
should_revise: revisions=1 -> executor; revisions=2 -> persist (MAX_REVISIONS=1)
```
The Streamlit UI was not run interactively. Its client logic (`api_json`) was tested against the
response shapes above. All servers I started (PIDs 37280, 36968, 39224, 41768, 33876) were stopped,
and the temp files were removed.

## Iteration 2: KB-gap guard (review finding 1)

**Finding:** the Ola vs Google answer asked qualification questions and implied a comparison would
follow. It never said the KB has no Ola Maps or Google Maps data.

**Fix (deterministic, no LLM involved):**
| File | Change |
|------|--------|
| `app/agents/executor.py` | `THIRD_PARTY_PROVIDERS` maps a display name to a case-insensitive regex (Ola / Ola Maps, Google Map(s), Mapbox, TomTom, HERE Maps, OpenStreetMap/OSM, Apple Maps, Azure Maps). `kb_gap_notice(user_message, kb_results)` returns a fixed note when a provider named in the message does not match the retrieved chunks. `run_executor` adds it to the result as `kb_gap_notice` |
| `app/agents/orchestrator.py` | `critic_node`: if `kb_gap_notice` is set, the final response is the notice. `should_revise`: go straight to persist when the notice is set (re-drafting can't change it) |
| `README.md` | Added a "KB-gap guard" row to the orchestration table |

The note reads: *"Note: the knowledge base has no information about Ola Maps, Google Maps, so I
can't compare them from the available sources. It only documents our service (Provider A) against
anonymised competitors (Provider B and Provider C) for directions, distance matrix, autocomplete,
reverse geocoding and pricing. I can share that comparison instead, or escalate to a specialist for
a named-provider comparison."*

**Why replace the draft instead of prepending the note:** I first prepended the note to the LLM
draft and tested that end to end. For the user's own wording ("…between ola and google map"),
the draft under the note began inventing a comparison (`1. **Accuracy**: - OLA typically…`), which
contradicts the note and breaks the "no invented facts" requirement. The guard therefore replaces
the draft. Queries that name no third-party provider are unaffected.

**Verification (commands run from the repo root with temporary scripts, since deleted):**

`python tmp_unit2.py` (offline, real retriever):
```
compile OK: app/agents/executor.py
compile OK: app/agents/orchestrator.py
'give me the compression of location changes details between ' -> 'Note: the knowledge base has no information about Ola Maps, Google Map'
'give me the comparison of location changes/details between O' -> 'Note: the knowledge base has no information about Ola Maps, Google Map'
'Compare reverse geocoding coverage with Provider B'          -> ''
'We need to track 500 delivery vehicles, which plan?'         -> ''
'hola, how do I use the polyline from Google Polyline Algorit' -> ''   (no false positive on "hola" or "Google Polyline")
```
I also grepped `data/**` for every provider pattern and got no matches, so the guard fires whenever
these providers are named.

`python tmp_verify2.py` (live API: `python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8011 --env-file .env`).
This ran the prepend version of the guard:
```
== give me the comparison of location chang… 200 application/json 21s
   Note: the knowledge base has no information about Ola Maps, Google Maps, … (then the LLM draft)
== give me the compression of location chan… 200 application/json 19s
   Note: … (then an LLM draft that starts inventing "OLA typically…"  -> led to the replace change)
== We need to track 500 delivery vehicles,   200 application/json 10s
   "Based on your requirement to track 500 delivery vehicles, we recommend considering the Enterprise Plan …"  (no note)
== bad_body   422 application/json {"detail":[{"type":"missing","loc":["body","message"],"msg":"Field required",…}]}
```
In an overlapping run, two concurrent requests hit the vLLM per-key limit. That returned
`500 application/json {"error":"workflow_failed","detail":"RateLimitError: Error code: 429 …"}`,
which is the JSON error path working as intended.

**Not verified:**
- **The final "replace" version was not run against the live API.** After the change, the shell
  tool stopped executing commands. It queued them for many minutes and then produced nothing, even
  for `echo`. The change is two small branches in `critic_node` and `should_revise`. Both files
  compile and the notice function was unit-tested above, but the HTTP round-trip on the final code
  is untested. Re-run the Ola query once in the UI or with `curl` to confirm.
- **UI (review finding 2, non-blocking):** the Streamlit UI was not run interactively, for the
  same shell reason. The `api_json` client logic remains tested only against synthetic responses.
  To check it: `streamlit run ui/app.py`, ask the Ola vs Google question in the Agentic Copilot tab,
  and expect the note above instead of `Error: Expecting value…`.

- **Cleanup:** a `Remove-Item` for `tmp_final.py`, `tmp_verify3_26772.out` and `tmp_final_*.out` is
  queued in the stalled shell. If those files are still in the repo root, delete them. Each test
  script kills the uvicorn server it started in a `finally` block (ports 8010, 8011, 8012). The
  user's own `run_api.py` on port 8000 was not touched.

## Known limitations / follow-ups
- The guard uses a fixed provider list. A provider not on the list (for example "MapmyIndia")
  falls through to the normal LLM path, and the original prompt-only behaviour applies.
- The planner still labels the query `qualification` with `escalation_needed: false`. The note
  offers escalation but does not set the planner flag.
- The user's own `run_api.py` server on port 8000 uses `reload=True`, so it should have picked up
  the changes. Restart it anyway to be sure.
- The vLLM key enforces a per-key concurrency limit (429). Parallel UI users or tabs will now get a
  readable JSON error instead of a crash.

## Ola Maps vs Google Maps: what the repo supports
**The repo corpus does not cover Ola Maps or Google Maps.** `data/corpus/*.md` and
`data/knowledge_base.txt` describe one location-services API ("Provider A (Our Service)") and
compare it only with anonymised competitors "Provider B" and "Provider C". "Google" appears only
as the "Google Polyline Algorithm" polyline encoding format in the Directions API docs. "Ola"
does not appear at all. So no Ola vs Google comparison of location changes, geocoding or places
can be given from the repo. The closest documented content is the Reverse Geocode comparison
(`04_reverse_geocode_api.md`):
- Provider A covers 195 countries, with street-level accuracy in 120 and batch up to 1000 (Professional+).
- Provider B covers 180 countries, with street-level accuracy in 90 and no batch.
- Provider C covers 160 countries, with street-level accuracy in 80 and batch up to 500 (Enterprise only).

Similar Provider A/B/C sections exist for Directions, Distance Matrix, Autocomplete and pricing.
