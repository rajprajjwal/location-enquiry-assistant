# Verification before evaluation and observability work

This run checks the current application before further evaluation, tracing and dashboard work. Inputs are synthetic; it does not run a new frozen or holdout evaluation. Passing these checks does not close open answer-quality acceptance criteria.

## Results

| Check | Result | Evidence |
| --- | --- | --- |
| Python compilation | 260 files, no errors | `compilation.json` |
| Automated suite after packaging correction | 1,124 passed; 15 subtests passed; one skipped | `pytest-final.log`, `pytest-final.xml` |
| Interpretation with the real validator | 167 passed; four subtests passed | `pytest-real-validation.log` |
| Generated contract models | No drift | `model-drift.json` |
| Distribution build and isolated imports | Passed; all 20 checked resources included | `package-check.json` |
| Live model endpoint | Chat, JSON and native tool calls passed | `live-smoke.json` |
| Live embedding endpoint | Two valid normalized 384-dimensional vectors; TLS verified | `live-smoke.json` |
| Live Streamlit workflow using BM25 | 11 checks passed | `ui-live.json` |
| BM25, dense and hybrid retrieval, without reranking | 12/12 synthetic smoke checks passed | `retrieval-smoke.json` |
| Saved snapshot self-comparison | 180 unchanged pages, no unreadable pages | `freshness-snapshot.json` |
| Hybrid with reranking | Not completed: reranker weights absent from the configured local cache | `reranker-availability.json` |
| Review queue and sandbox decisions | 20/20 held, reviewed and audited; unauthorized approvals blocked | `review-queue/scores.json` |
| Fault-injection integration | 50/50 passed; 15 recovered answers and 35 expected safe fallbacks | `reliability/summary.json` |

The live UI checks cover a definition, provider-specific documentation, provider clarification and reply, pricing, missing volume, limits comparison, a sandbox proposal and approved update, and an incident awaiting approval. They exercise the institute model and local documents in a temporary case database. They check execution and expected routes, not gold answer accuracy.

The review-queue and fault-injection runs use scripted model responses and isolated databases. They verify application integration and safe behavior; they are not live-model quality measurements.

## Environment limits

The full automated suite uses a temporary dependency directory for Beautiful Soup and Transformers. Dense and hybrid smoke checks additionally use `/private/tmp/readiness-retrieval-deps` for ChromaDB and its dependencies. The normal project environment was not changed. See `native-environment.json` for missing application and optional demo dependencies. Endpoint credentials were supplied only to test processes and are not included here. The normal embedding configuration remains unset. Hybrid with reranking still needs the local reranker weights and the normal retrieval setup before it can be tested. Offline model loading was attempted and reported missing weights.

The skipped freshness check requires a local raw-source snapshot. No raw snapshot exists in the application's expected directory. Synthetic freshness tests pass. Separately, 180 available source-expansion pages were SHA-verified and compared with themselves using temporary filename mappings; no changes or unreadable pages were found. This does not establish that current live websites are unchanged, nor does it remove the full-suite skip in the normal checkout.

The initial non-isolated wheel command could not import setuptools in the project environment. A standard isolated build installed its declared build requirements temporarily and succeeded. Wheel inspection also found three missing diagnostic/qualification contract files and archived verification Python packages. Packaging now includes those contracts and excludes archived result packages. An extracted wheel loads the schemas and contracts successfully.

The optional standalone baseline API/demo was not launched. Its shared-model adapter is covered by the automated suite; its older optional web/database/vector dependencies are not installed in the main environment.

## Reproduction

From the project root, with the documented application dependencies installed:

```bash
python -m pytest -q
INTERPRET_VALIDATION=real python -m pytest -q tests/enquiry_interpretation tests/model_gateway tests/validation
python -m pip wheel --no-deps --wheel-dir /tmp/copilot-wheel .
python -m copilot.enquiry_workflow.verification.verify_review /tmp/copilot-review-check
python -m copilot.enquiry_workflow.verification.reliability_faults --output /tmp/copilot-reliability-check
```

Use `python3` in place of `python` where appropriate. For this run, commands used `.venv/bin/python`; the test environment additionally set `PYTHONPATH=/private/tmp/prompt-baseline-merge-test-deps:<project-root>` and the existing tokenizer cache through `HF_HOME`. Generated-model comparison was performed in a temporary copy with `model_drift_check.py`, leaving tracked models unchanged.

Live checks require `TRACKB_API_KEY` and `TRACKB_CA_CERT` for chat, and `EMBED_BACKEND=endpoint`, `EMBED_BASE_URL`, `EMBED_API_KEY`, `EMBED_CA_BUNDLE` for dense retrieval. Use the supplied CA files and keep keys outside version control. The live UI verifier can then run with:

```bash
python -m copilot.enquiry_workflow.verification.verify_ui
```

Dense retrieval checks use a temporary copy of the index so opening the database cannot alter the existing index. The corpus and GT integrity checks are recorded in `summary.json`.
