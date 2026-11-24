# Prompt-engineering baseline

This folder contains an isolated prompt-comparison implementation and its optional demonstration app. It keeps the existing copilot application, canonical data and retrieval indexes in their current locations.

## Available strategies

- Few-shot structured output: one generation with three examples.
- Chain-of-thought self-consistency: three generations with majority selection.
- Decomposition: five subproblem generations followed by synthesis.

Baseline chat calls use `copilot.model_gateway.LLMClient` through a small message adapter. The shared certificate verification, model configuration, request queue, retry limits and context checks apply. No retrieval tools or agent loop are used by `run_baseline.py`.

## Run a single-query comparison

Use the configured project environment and the `TRACKB_API_KEY` and `TRACKB_CA_CERT` settings described in [the model-client guide](../docs/model-gateway.md). Credentials stay outside Git. From the repository root, either command works:

```sh
python prompt-engineering-baseline/run_baseline.py --query "Directions requests return an authentication error. What information should we collect?" --workflow support --out prompt-engineering-baseline/results/sample.json
```

```sh
python3 prompt-engineering-baseline/run_baseline.py --query "Directions requests return an authentication error. What information should we collect?" --workflow support --out prompt-engineering-baseline/results/sample.json
```

The comparison makes ten model calls. It saves each strategy's output, observed latency, failure details and the original demonstration scores. Configure the shared client before running; the command exits unsuccessfully if all strategies fail.

## Optional demonstration API and UI

The original `app/`, `ui/`, corpus and index-building code are retained as a separate demo. Its dependencies are listed in this folder's `requirements.txt`; they include older framework versions. Use a separate environment for this demo rather than installing those versions over the main application's environment. Install the main project as an editable package into that demo environment so the shared model client is available. Configure the same shared-client credentials and certificate there.

From this folder, build its demo index, then start its API and UI in separate terminals:

```sh
python build_kb.py
python run_api.py
python -m streamlit run ui/app.py --server.port 8502
```

```sh
python3 build_kb.py
python3 run_api.py
python3 -m streamlit run ui/app.py --server.port 8502
```

The API uses port **8001** and the UI uses **8502**. `BASELINE_API_PORT` and `BASELINE_API_BASE` override the API settings. Its database defaults to `capstone.db` inside this folder; `BASELINE_DATABASE_URL` overrides it. Generated logs, databases and indexes are ignored by Git. The full optional demo has not received the main application's acceptance verification.

## Evaluation status

This import does **not** complete Activity 6. The original prompt examples, built-in labels, demonstration corpus and heuristic scoring are retained for review. They include scenarios and illustrative product claims that require alignment with the approved project scope and verified documentation.

A zero-shot strategy, canonical frozen-input adapter, shared acceptance scorer and the complete frozen comparison still need verification or integration. The displayed winner is based on the original heuristic; it is not the project's accepted best prompting baseline. Reported cost is an assumed character-based proxy, not measured endpoint billing. The main GT remains `../data/ground-truth.xlsx`; no GT or holdout evaluation was run during this import.

The original overview is retained in `reference/README.original.md`. Per-file source checksums, integration changes and omitted runtime artifacts are recorded in `source-history.json`. Original implementation history is retained by the merge.

## Integration verification

The full project suite passed 1,124 tests and 15 subtests, including two tests of the shared-client adapter and all three prompt strategies. One existing freshness check was skipped because its local snapshot was absent. Retrieval-test dependencies were supplied in a temporary verification directory; the project environment was not modified. No live model calls, frozen evaluations or holdout evaluations were run for this integration. Evidence is saved in `results/integration-check.json` and `results/integration-tests.xml`.
