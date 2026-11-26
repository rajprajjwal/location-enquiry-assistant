# Model gateway

Capstone tracking: Activities 18 and 20.

Use `copilot/model_gateway/client.py` for shared model access and `copilot/model_gateway/endpoint_checks.py` to verify the endpoint. Tests are in `tests/model_gateway/`; saved verification reports are in the `results/` subfolder.

- [Reliability setup, limits and verification](../../docs/activity-20-reliability.md)
- [Interface and configuration](../../docs/model-gateway.md)
- [Synthetic smoke report](results/smoke-001/report.json)
- [Original Activity 18 smoke report](results/activity18-smoke-001/report.json)
- [80-record run summary](results/frozen-001/summary.md)
- [80-record report](results/frozen-001/report.json)
- [80 recorded responses](results/frozen-001/responses.jsonl)

The 80-case endpoint run passed. The institute-provided model is accepted by the project owner. Recorded latency: p50 2,680 ms, p95 5,463 ms. These are endpoint checks, separate from Activity 2 interpretation scores.
