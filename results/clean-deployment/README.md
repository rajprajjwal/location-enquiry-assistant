# Clean-checkout deployment verification

The application was installed into a new Python 3.12.14 virtual environment on macOS ARM64. System site packages were disabled, `PYTHONPATH` was unset, and no dependencies, model files or dense index were copied from the existing application. The documented preparation command downloaded the official pinned model assets into a new cache. Service keys and CA paths were supplied only to test processes.

Use [the deployment guide](../../docs/deployment.md) to repeat the installation, supplying service credentials and certificates separately. Verification covered the localhost capstone sandbox. Shared hosting still requires authenticated access; the local reviewer selector does not authenticate identities.

## Confirmed results

| Check | Result | Evidence |
| --- | --- | --- |
| Runtime installation | Editable install with retrieval extras succeeded | `install.log` |
| Dependency consistency | No broken requirements | `pip-check.log` |
| Compilation | 266 maintained Python files passed | `compilation.json` |
| Automated suite after the cold-start fix | 1,127 passed; 15 subtests passed; one skipped | `tests.log`, `pytest.xml` |
| Real interpretation validator | 167 passed; four subtests passed | `real-validation.log` |
| Model preparation | Pinned chat/chunk tokenizers and reranker downloaded successfully | `prepare-execution.json`, `prepare.log` |
| Offline reranker | Four synthetic queries passed without Hub access | `reranker-offline.json` |
| Fresh BM25 and dense index build | 509 documents, 7,576 chunks, 480-token maximum, 384-dimensional vectors; all chunk content and metadata verified | `index-build.json` |
| Hybrid live setup check | All 11 checks passed, including chat/JSON/tools and four queries through hybrid with reranking | `setup-check.json` |
| Hybrid live Streamlit flow | All 11 checks passed | `ui-hybrid.json` |
| Review queue | 20/20 consequential proposals held and audited; 20 unauthorized approvals blocked | `review-queue/scores.json` |
| Reliability fault scenarios | 50/50 passed; zero unexpected failures or unapproved decisions | `reliability/summary.json` |
| BM25 live setup check | All seven checks passed | `setup-bm25.json` |
| BM25 live Streamlit flow | All 11 checks passed | `ui-bm25.json` |
| Streamlit server startup | Home page and health endpoint returned HTTP 200 | `startup.json` |
| Distribution build | Runtime dependencies, retrieval extras and all 22 checked resources included; archived result code excluded | `wheel-check.json` |

The final results and unchanged GT/corpus checks are recorded in `summary.json` and `integrity.json`. The existing project environment was not modified.

The UI verifier covers a definition, provider documentation, provider clarification and reply, a price comparison, missing monthly volume, limits comparison, a sandbox update proposal and approval, and a production incident held for approval. It uses synthetic enquiries and a temporary case database. These checks verify execution and expected routes, not gold answer quality.

## Fixes discovered during setup

- Declared the application's runtime dependencies and retrieval extras in package metadata. Development and evaluation dependencies remain separate.
- Added model preparation and setup-check commands, plus one complete installation guide.
- Pinned chunk-tokenizer and reranker revisions. The initial Xet download failed; preparation now defaults to HTTP transport, which completed the download.
- Moved UI reranker loading and warm-up before the enquiry begins. Cold CPU loading took about 32 seconds, exceeding the 15-second tool limit; subsequent standalone reranks took about 3–5 seconds. Selecting hybrid mode now shows a loading indicator before accepting an enquiry.
- Added regression tests for missing credentials, missing tokenizer assets and BM25 operation without a dense index or reranker. Failure reports do not expose credential details.

The initial index attempt stopped when the embedding endpoint became unreachable after 512 chunks. The failed candidate was not published. A connectivity probe succeeded, and a fresh retry completed all 7,576 chunks. Initial failure logs are retained separately from the successful run.

## Limits and reproduction details

The freshness test skips because the checkout does not contain the required dated raw-source snapshot. Processed source documents are bundled, and the index rebuild verifies that processed corpus; this is not a fresh audit of current vendor websites. The earlier readiness report separately records a saved-snapshot self-comparison.

The server startup test used port 18501 to avoid interfering with an existing local application and stopped that test server afterward. The deployment guide uses the standard port 8501. The UI scenarios use Streamlit AppTest and temporary databases rather than a shared customer database.

`installed-packages.txt` records resolved package versions; it is evidence for this platform, not a portable lockfile. Linux has not been independently verified. Native Windows is outside the current POSIX file-lock implementation.

No frozen or holdout evaluation was run. Passing setup and execution checks does not close outstanding answer-quality criteria or complete the evaluation, tracing and dashboard activities.
