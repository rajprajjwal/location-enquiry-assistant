# Install and run the application

Use Python 3.12 on macOS or Linux. The clean-checkout verification used macOS ARM64 and Python 3.12.14; Linux has not been independently verified. Native Windows is not supported by the current POSIX file-lock implementation. This guide runs the capstone sandbox on localhost. Model credentials are provided separately; they are not part of a checkout. Keep the checkout, model cache, dense index and case database writable. Preserve the case database when updating the application.

## 1. Install from the checkout

From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[retrieval]'
python -m pip check
```

After activation, `python` and `python3` are interchangeable; `command -v python` and `command -v python3` must point into `.venv`. For example, `python3 -m pip install -e '.[retrieval]'` is equivalent to the install command above. For BM25-only operation, install with `python -m pip install -e .` instead. The optional prompt comparison demo has its own setup and is not needed for this app.

## 2. Configure services and reviewers

Set these variables in the terminal used for preparation, checks and startup. Replace the example paths with your readable certificate files. The prompts keep keys out of command history.

```bash
printf 'Chat API key: '
read -r -s TRACKB_API_KEY
printf '\n'
export TRACKB_API_KEY
export TRACKB_CA_CERT='/absolute/path/to/chat-ca.crt'

printf 'Embedding API key: '
read -r -s EMBED_API_KEY
printf '\n'
export EMBED_API_KEY
export EMBED_BACKEND=endpoint
export EMBED_BASE_URL='https://103.42.50.41:1035/v1'
export EMBED_CA_BUNDLE='/absolute/path/to/vm02-ca.crt'
export HF_HOME="$PWD/.model-cache"
```

BM25 needs only the chat variables. The embedding URL and certificate must match the current institute access guide. Do not disable TLS verification. Keys and certificates stay outside Git. Chat variables are read from the process environment; creating a `.env` file alone does not configure the chat client.

Edit `copilot/config/approvers.yaml` to list the authorized reviewer names and allowed action types. The local reviewer selector checks this list; it does not verify a user's identity. For a shared host, keep the app behind authenticated private access until application-level identities are connected. The sandbox does not send messages or update production systems.

## 3. Prepare models and retrieval

For hybrid retrieval:

```bash
python -m copilot.deployment.prepare --mode hybrid
python -m copilot.rag.document_indexing.build_index --report /tmp/copilot-index-build.json
```

Preparation downloads the pinned chat tokenizer, chunk tokenizer and reranker weights. It defaults to HTTP downloads to avoid Xet transport failures on restricted networks. Allow disk space and time for the reranker download; keep `HF_HOME` the same at startup. Re-running preparation reuses valid cached files. The index rebuild uses the bundled 509-document corpus at 480 tokens; no GT records are used. It verifies every indexed chunk and its citation metadata before publishing.

For BM25 only:

```bash
python -m copilot.deployment.prepare --mode bm25
```

BM25 uses the bundled corpus and needs no dense index or reranker. Fetching websites or installing a browser is not required to launch the app from the bundled corpus.

## 4. Check setup and live access

```bash
python -m copilot.deployment.check --mode hybrid --live --report /tmp/copilot-setup-check.json
```

For BM25, replace `hybrid` with `bm25`. Without `--live`, the command checks local prerequisites and initializes the local case database without sending model requests. With `--live`, it also tests chat, JSON and native tool calls, plus four synthetic retrieval questions in hybrid mode. The command exits unsuccessfully if a check fails. Reports contain no keys or customer inputs.

If a check fails, resolve the named prerequisite before starting:

| Check | Action |
|---|---|
| dependencies | Install the application with the chosen extras using the same interpreter. |
| chat_tokenizer | Run the preparation command. |
| chat_configuration | Export the chat key and readable CA path. |
| embedding_configuration | Export the embedding URL, key and readable CA path. |
| case_storage | Make the checkout's case storage directory writable. |
| reviewers | Add an authorized reviewer to the reviewer configuration. |
| bm25_corpus | Restore the bundled processed corpus from the checkout. |
| dense_index | Run the index rebuild with the configured embedding endpoint. |
| reranker_assets | Run hybrid preparation with the same `HF_HOME`. |
| live_chat_json_tools | Check service availability, credentials and CA, then rerun. |
| live_hybrid_reranking | Check embedding availability and the local model cache; inspect the service-specific setup before retrying. |

## 5. Launch and test

```bash
python -m streamlit run copilot/streamlit_ui/streamlit_app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
```

Open http://127.0.0.1:8501. Choose BM25 or Hybrid with reranking. On first selecting hybrid mode, wait for the reranker loading indicator to finish; the UI warms the model before starting any enquiry deadline. Start with a synthetic question such as “What coordinate order does Mapbox Directions use?” Check the cited draft and structured output. For “How do I set waypoints in the Directions API?”, answer the provider clarification in the same case. Reopen the case to confirm saved history. Submit a synthetic production incident and confirm that its handoff stays pending until a reviewer decides it.

A separate automated UI check uses synthetic inputs and a temporary database. Run both modes after full hybrid setup:

```bash
python -m copilot.enquiry_workflow.verification.verify_ui --retrieval bm25
python -m copilot.enquiry_workflow.verification.verify_ui --retrieval hybrid
```

## Development tests and persistence

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

The freshness integration test skips when no dated raw-source snapshot is present. A checkout includes processed documents, not the complete raw snapshot.

Local state lives in `copilot/case_storage/data/lbs.db`; preserve this file and any SQLite sidecars during backup. Dense vectors are in `copilot/rag/data/chroma/`; rebuild after a corpus or embedding-model change. Model downloads live under `HF_HOME`, and the verified chat tokenizer lives under `copilot/model_gateway/assets/` unless `TRACKB_TOKENIZER_DIR` is set. Restart the app after changing configuration or rebuilding indexes. These runtime files are ignored by Git.

## Optional tracing service

Follow the [tracing setup guide](../copilot/observability/README.md) to run local Langfuse with Docker. Local traces work without this service. Reporting estimates use illustrative rates; institute endpoint access remains free.
