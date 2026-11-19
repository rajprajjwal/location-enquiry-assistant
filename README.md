# Location Enquiry Assistant

Sales and support copilot for location API enquiries, built for the institute's Track B capstone. This repository contains the task contracts, interpretation core, evaluation data and evidence, annotation materials, and shared model gateway.

## Repository layout

| Path | Purpose |
|---|---|
| `copilot/` | Shared Python implementation, including interpretation and the model endpoint client. |
| `contracts/`, `schemas/`, `vocab/` | Input/output contracts and controlled labels. |
| `data/ground-truth.xlsx` | Updated project GT workbook. |
| `data/` | GT review records and Activity 3–5 supporting artifacts. |
| `interpretation/` | Activity 2's 80-record inputs, gold, predictions, per-record results, scores and manifest. |
| `eval/frozen-interpretation/` | Versioned frozen Activity 2 snapshot. |
| `eval/activity-3-pilot/` | Ten-case annotation pilot, template and examples. Completed independent annotations are still pending. |
| `model-gateway/results/` | Synthetic endpoint checks and the 80-case endpoint reliability/latency run. |
| `docs/`, `tests/` | Component documentation and automated tests. |

All three project folders (`data/`, `interpretation/`, `model-gateway/`) are inside this Git repository. The separate Deepshikha integration checkout is outside it and has not been merged.

## Component guides

- [Interpretation design](docs/activity-2-interpretation-design.md)
- [Interpretation results](interpretation/report.md)
- [Gold annotation guide](docs/activity-3-labeling-guide.md)
- [Gold record contract](docs/activity-3-gold-record.md)
- [Model gateway](docs/model-gateway.md)
- [Model gateway run summary](model-gateway/results/frozen-001/summary.md)

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
```

Live model calls require `TRACKB_API_KEY` and `TRACKB_CA_CERT`. Keep credentials and certificates outside Git; the existing ignore rules remain in place.

The model gateway uses the institute-provided endpoint. Its frozen run checks completion reliability and latency, not answer correctness or interpretation accuracy. Original frozen manifests and historical reports retain their original provenance; references in those snapshots to data outside Git describe the layout when those snapshots were produced. The current workbook is `data/ground-truth.xlsx`.

[Historical C1 README](docs/legacy-c1-readme.md) preserves the original task-specification documentation. It describes an earlier workspace layout.
