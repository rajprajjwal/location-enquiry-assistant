# Location Enquiry Assistant

Sales and support copilot for location API enquiries, built for the institute's Track B capstone. This repository contains the task contracts, interpretation core, evaluation data and evidence, annotation materials, and shared model gateway.

## Repository layout

| Path | Purpose |
|---|---|
| `copilot/enquiry_interpretation/` | Interpret enquiries and extract qualification details. |
| `copilot/model_gateway/` | Hosted model client and endpoint contract checks. |
| `copilot/enquiry_workflow/` | LangGraph routing, case turns, and workflow adapters. |
| `copilot/registered_tools/` | Tool execution and Pydantic contracts. |
| `copilot/conversation_state/` | Case-scoped conversation state model. |
| `copilot/rag/` | Document ingestion, indexing, hybrid retrieval, reranking, and the local corpus. |
| `copilot/response_drafting/`, `copilot/pricing_tools/` | Structure responses and calculate sourced pricing. |
| `copilot/case_storage/` | SQLite persistence for cases, approvals, sandbox records, and traces. |
| `copilot/streamlit_ui/` | Staff interface for enquiries, approvals, and traces. |
| `copilot/observability/` | End-to-end OpenTelemetry tracing, local Langfuse export and INR cost reporting. |
| `copilot/deployment/` | Prepare model assets and check installation, configuration and live access. |
| `results/clean-deployment/` | Clean-checkout installation, index rebuild and end-to-end verification evidence. |
| `copilot/enquiry_workflow/verification/` | Synthetic UI and frozen workflow verification scripts. |
| `copilot/enquiry_workflow/results/` | Saved workflow verification results. |
| `copilot/validation/specification_checks/` | Standalone C1 checker, guide, and saved report. |
| `contracts/`, `schemas/`, `vocab/` | Input/output contracts and controlled labels. |
| `data/ground-truth.xlsx` | Updated project GT workbook. |
| `data/` | GT review records and Activity 3–5 supporting artifacts. |
| `copilot/enquiry_interpretation/results/` | Activity 2's 80-record inputs, gold, predictions, per-record results, scores and manifest. |
| `eval/frozen-interpretation/` | Versioned frozen Activity 2 snapshot. |
| `eval/activity-3-pilot/` | Ten-case annotation pilot, templates, examples and two-annotator agreement results. All three κ targets pass; disagreement adjudication remains pending. |
| `copilot/model_gateway/results/` | Synthetic endpoint checks and the 80-case endpoint reliability/latency run. |
| `docs/`, `tests/` | Component documentation and automated tests. |

## Component guides

- [Interpretation design](docs/activity-2-interpretation-design.md)
- [Interpretation results](copilot/enquiry_interpretation/results/report.md)
- [Gold annotation guide](docs/activity-3-labeling-guide.md)
- [Gold record contract](docs/activity-3-gold-record.md)
- [Workflow setup and verification](copilot/enquiry_workflow/README.md)
- [Model gateway](docs/model-gateway.md)
- [Model gateway run summary](copilot/model_gateway/results/frozen-001/summary.md)

## Local setup

Follow the [installation and deployment guide](docs/deployment.md) for the complete dependency install, service configuration, model preparation, index rebuild, setup check and launch commands. The tested interpreter is Python 3.12.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[retrieval]'
```

Installation alone does not configure services or download the required model assets. Complete the guide before submitting a live enquiry. For development tests, also install `requirements.txt`.

The model gateway uses the institute-provided endpoint. Its frozen run checks completion reliability and latency, not answer correctness or interpretation accuracy. Original frozen manifests and historical reports retain their original provenance; references in those snapshots to data outside Git describe the layout when those snapshots were produced. The current workbook is `data/ground-truth.xlsx`.

[Historical C1 README](docs/legacy-c1-readme.md) preserves the original task-specification documentation. It describes an earlier workspace layout.

## Prompt-engineering baseline

The isolated [prompt comparison module](prompt-engineering-baseline/README.md) contains three prompting strategies, a shared-model-client adapter and an optional standalone demo. Its evaluation status and separate setup are documented in that folder.

- [End-to-end tracing setup](copilot/observability/README.md)
