# Evaluation metrics dashboard

Read the evaluation harness artifacts and compare baseline with agent by bucket, API and team. Every metric in the harness catalog appears with its unit and scored denominator. Citation and tool success use citation/call weights; other quality scores are case averages. Missing or inapplicable metrics remain unscored.

Install the evaluation extra described in the [harness guide](../evaluation/README.md). From the activated project environment:

```sh
python -m streamlit run copilot/metrics_dashboard/streamlit_app.py --server.address 127.0.0.1 --server.port 8503 --server.headless true --browser.gatherUsageStats false
```

Or:

```sh
python3 -m streamlit run copilot/metrics_dashboard/streamlit_app.py --server.address 127.0.0.1 --server.port 8503 --server.headless true --browser.gatherUsageStats false
```

Open http://localhost:8503. The default results root is `results/evaluation`; set `COPILOT_EVAL_RESULTS` to another directory before starting if needed. The dashboard refreshes every ten seconds, discovers newly completed runs and ignores incomplete summaries. Select a run and apply bucket, API or team filters; the metric chart uses the same saved values as the comparison table. No credentials or live model calls are required to view saved artifacts.

Generation cost and evaluation overhead are separate. INR costs are illustrative reporting estimates; actual institute endpoint access is free. Automatic judge scores remain explicitly labelled. The case table exposes errors, and the download retains full metric definitions and run bindings. This dashboard is separate from the enquiry trace explorer, which shows individual workflow spans.

Select **Saved activity reports** to browse existing component and evaluation artifacts in their original formats. This view reads report folders only; it never starts a scorer or model client. Large files above 5 MB and runtime files are omitted. The evaluation metric table continues to use the saved metric schema and does not manufacture comparable scores for other report formats.

For authenticated public HTTPS hosting alongside Langfuse, follow [public deployment](../observability/langfuse/PUBLIC_DEPLOYMENT.md). To move existing traces to another host, follow [historical migration](../observability/langfuse/HISTORICAL_MIGRATION.md). Saved report files are supplied by the checkout; historical Langfuse data requires the separate volume restore.
