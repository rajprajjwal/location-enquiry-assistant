# Model gateway

Capstone tracking: Activity 18.

The shared implementation is `copilot/llm/client.py`; endpoint verification is `copilot/llm/endpoint_checks.py`. Tests are in `tests/llm/`. This folder holds the module's saved verification evidence, without duplicating the repository's Python source tree.

- [Interface and configuration](../docs/model-gateway.md)
- [Synthetic smoke report](results/smoke-001/report.json)
- [80-record run summary](results/frozen-001/summary.md)
- [80-record report](results/frozen-001/report.json)
- [80 recorded responses](results/frozen-001/responses.jsonl)

The 80-case endpoint run passed. The institute-provided model is accepted by the project owner. Recorded latency: p50 2,680 ms, p95 5,463 ms. These are endpoint checks, separate from Activity 2 interpretation scores.
