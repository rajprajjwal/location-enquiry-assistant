# Activity 19 · Agent orchestration

The goal is to handle a location API enquiry within **10 steps**. The workflow can return a sourced draft, ask for missing information, or propose a sandbox update or escalation for human review.

## Workflow

- `run_enquiry()` takes the enquiry and its validated Activity 2 interpretation. The LangGraph planner decides whether to search documentation or raise an escalation.
- The document search tool returns ranked passages with chunk IDs, source URLs and fetch dates. The drafter uses the shared Model Gateway to select a passage and quotes it with a citation.
- The critic checks that quoted text came from the retrieved source, asks the model whether it directly answers the question, and validates the seven structured outputs. The planner can refine the search within the same budget.
- General API definitions use reviewed excerpts from the local corpus. For sales enquiries, the calculator uses bundled vendor price tiers, and the documentation comparison checks each named provider separately. The planner asks for missing details, such as the monthly workload.
- A recognised reply to an active `provider` or `current_provider` question replaces stale provider facts and is bound into validated interpretation. This confirmation resolves that pending question even when the original task names several providers. Names from an initial comparison or general history do not select an arbitrary provider.
- An explicit request for a qualification checklist returns missing customer decisions as advice, rather than starting generic sales intake. The existing qualification planner supplies the structured follow-up list.
- Explicit documentation requests naming two to four providers retrieve and verify each provider separately. Missing provider evidence is stated in that provider’s section. Combined price comparisons keep their existing provider limit.
- Passage selection validates list size, ID types and ranges. A contract error allows one repair against the same candidates within shared retry, token and deadline limits; citation and relevance checks still apply.
- `run_case()` loads conversation history and records the result, steps and timing in SQLite. Escalations and sandbox field changes go to **Approvals**. A reviewer can edit, approve or reject the proposal. The decision and any applied sandbox diff appear in the audit log.

Planning, tool execution, drafting and critic review each count as one step, including failed actions. When the budget runs out, the workflow escalates. If it ends before review, it records `not_run` and the reason.

## Run the local UI

Run these commands from the repository root. The tested setup uses **Python 3.12**. On macOS, check `python3 --version` and `command -v python3`. If they show Apple's Python 3.9 from Command Line Tools, use a separate Python 3.12 installation. If you use Homebrew, install it with `brew install python@3.12`.

### 1. Prepare the Python environment

Reuse an existing Python 3.12 environment if you have one. For a fresh checkout, create a local environment with `python3.12 -m venv .venv`. The commands below assume the environment is named `.venv`.

```bash
source .venv/bin/activate
python --version
python -m pip install --upgrade pip
python -m pip install -r requirements.txt "streamlit==1.67.0"
python -m pip check
python -m streamlit --version
export PYTHONPATH="$PWD"
```

You can use `python3` in the same commands after activating the environment. Check `command -v python` or `command -v python3`: it should point into the active environment. If you see `No module named streamlit`, check the interpreter and rerun the install using that same interpreter. You can also use `.venv/bin/python` or `.venv/bin/python3` directly.

### 2. Configure live enquiries

You can open the UI without credentials. Before submitting a live enquiry, set both of these in the same terminal **before starting Streamlit**:

- `TRACKB_API_KEY` is the institute-issued API key for the chat model endpoint.
- `TRACKB_CA_CERT` is the absolute path to the readable CA certificate file used to verify the endpoint.

```bash
printf 'Track B API key: '
read -r -s TRACKB_API_KEY
printf '\n'
export TRACKB_API_KEY
export TRACKB_CA_CERT="/absolute/path/to/your-ca-certificate.crt"
test -n "$TRACKB_API_KEY" && test -r "$TRACKB_CA_CERT"
```

Replace the example certificate path with your own. The last command succeeds silently when the key is set and the certificate is readable. Keep both outside Git. If Streamlit is already running, stop it and relaunch it from this configured terminal so it inherits the variables.

Use **BM25** for the first live enquiry. It uses bundled documents and needs only the chat-model connection above. **Hybrid with reranking** also requires the embedding configuration and dense index described under [Retrieval setup](#retrieval-setup).

### 3. Start Streamlit

This is the exact command used to verify local startup. Run it from the repository root, then open **http://127.0.0.1:8501**:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" .venv/bin/python -m streamlit run copilot/streamlit_ui/streamlit_app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
```

You can substitute `.venv/bin/python3`, or use `python` or `python3` after activating `.venv`. The startup check verified that Streamlit was serving the UI. A live enquiry also tests the model connection.

1. In **Enquiries**, choose **BM25** and ask how to set waypoints in the Directions API. Give each new case a customer name or reference. If the provider is missing, the enquiry box clears and the same case stays selected. Enter the reply, such as Mapbox, then check the cited draft and structured output. Use the customer case picker to reopen previous conversations.
2. Submit a production incident and open **Approvals** to review the pending handoff. Check the decision log after approving or rejecting it.
3. Open **Traces** to inspect the saved steps and critic outcome. To remove a saved turn, select its run, open **Delete enquiry and traces**, confirm, and delete. The case and its other turns stay available. Deleting the only source for a pending approval cancels it. Decided approvals stay in the audit log and show that their source enquiry was deleted.

The reviewer selector is for local testing. A shared deployment requires authenticated reviewer identities.

## Retrieval setup

Run these commands in the same virtual environment with the import path set above.

BM25 builds its index in memory from the bundled chunks at `copilot/rag/data/processed/chunks.jsonl`. In Python, select it with `rag_document_search(mode="bm25", rerank=False)`. The default Python adapter combines BM25 and dense retrieval with reciprocal rank fusion. It keeps the highest-ranked passage per canonical URL in the fused top 30, then reranks those passages with the cross-encoder.

For hybrid retrieval, first install the additional dependencies with `python -m pip install -r copilot/rag/requirements-retrieval.txt`. Set `EMBED_BASE_URL` to the embedding service base URL ending in `/v1`, set `EMBED_API_KEY`, and supply `EMBED_CA_BUNDLE` if the service requires a custom CA. The default embedding backend is `endpoint`. The reranker loads on first use. The UI lists missing local prerequisites and disables submission in hybrid mode until they are available. Use BM25 to test while you set up hybrid retrieval.

From the repository root, activate the virtual environment and run one command to rebuild BM25 and dense retrieval from the approved corpus. The default chunk budget is 480 tokens, including headers and special tokens.

```bash
PYTHONPATH="$PWD" python -m copilot.rag.document_indexing.build_index
PYTHONPATH="$PWD" python3 -m copilot.rag.document_indexing.build_index
```

Use either Python command. Add `--report /path/to/index-build.json` to save the corpus checksum, model, token limit, chunk counts and retrieval checks. Restart the app after the rebuild so it reloads its cached retrieval indexes.

To rebuild directly from a complete dated raw snapshot, add `--raw-snapshot copilot/rag/data/raw/YYYY-MM-DD` to the same command. The snapshot must contain `manifest.jsonl` and a successful download for every source in `copilot/config/sources.yaml`. The rebuild checks source coverage and both indexes before publishing. Use `python -m copilot.rag.document_ingestion.fetch` to collect a fresh snapshot when you intend to refresh the source content. Sources that require browser rendering also need Chromium, installed with `python -m playwright install chromium`.

To audit the corpus for near-duplicates, run `python -m copilot.rag.document_ingestion.audit_corpus --report /path/to/corpus-audit.json` with the same import path. The audit uses datasketch MinHash for screening and exact five-word shingle Jaccard for confirmation.

## Verification

Run `python -m pytest -q tests/enquiry_workflow` from the repository root for local tests. With the Model Gateway variables set, run `python -m copilot.enquiry_workflow.verification.verify_ui` for the live Streamlit test. It uses synthetic enquiries, bundled BM25 documents and a temporary SQLite database.

The [live UI report](results/live-ui.json) records the definition, provider clarification and reply, document and price comparisons, sandbox approval, and incident handoff checks. Those checks verify routing and application behavior. The quality thresholds still require evaluation on the frozen set. Hybrid retrieval also requires a separate configured verification run.

The frozen workflow runner is `python -m copilot.enquiry_workflow.verification.verify_frozen --out copilot/enquiry_workflow/results/frozen-001`. Use it only once the 80 frozen inputs are approved for the configured model endpoint. The runner verifies the input manifest and records each outcome, step count and critic result. It does not load gold answers or holdout data.


## Human review acceptance

Activity 17 passed the 20-action sandbox review check. The scenarios cover record updates and escalations, approval, edited approval, rejection, and persistent audit diffs. The [acceptance report](results/activity-17/report.md) includes the scope and rerun command.


## Orchestration acceptance

The [Activity 19 report](results/activity-19/report.md) records 80 frozen runs, step counts, critic verdicts and the looping-prompt stress test. All runs terminated within 10 steps. The literal final/escalated status count is 76/80, with four additional delivered clarifications.

Activity 19 is complete under the approved criterion of a valid answer, clarification request, or escalation within 10 steps. Use `--clarifications-as-final` when rerunning the approved verification. The saved report retains both raw statuses and completed-turn classifications.

## Reliability

Model and tool calls share retry, deadline and token limits. Before running the app, install the pinned tokenizer assets using the [reliability setup guide](../../docs/activity-20-reliability.md). Saved fault-injection results are in `results/activity-20/`.
