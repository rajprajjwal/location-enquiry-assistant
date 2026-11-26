# Evaluation metrics dashboard

The dashboard compares saved baseline and agent results by bucket, API and team. It shows every metric in the harness catalog with its unit and scored denominator. Citation precision and tool success are weighted by citations and calls; other quality scores are averaged by case. Missing or inapplicable metrics remain unscored.

Install the evaluation extra described in the [harness guide](../evaluation/README.md). From the activated project environment:

```sh
python -m streamlit run copilot/metrics_dashboard/streamlit_app.py --server.address 127.0.0.1 --server.port 8503 --server.headless true --browser.gatherUsageStats false
```

Or:

```sh
python3 -m streamlit run copilot/metrics_dashboard/streamlit_app.py --server.address 127.0.0.1 --server.port 8503 --server.headless true --browser.gatherUsageStats false
```

Open http://localhost:8503. The default results root is `results/evaluation`; set `COPILOT_EVAL_RESULTS` to another directory before starting if needed. The dashboard refreshes every ten seconds, discovers newly completed runs and ignores incomplete summaries. Select a run and apply bucket, API or team filters; the metric chart uses the same saved values as the comparison table. No credentials or live model calls are required to view saved artifacts.

Generation cost is reported separately from evaluation overhead. INR figures are illustrative estimates; institute endpoint access is free. Automatic judge scores are labelled as such. The case table shows errors, and downloads include the metric definitions and run bindings. For individual workflow spans, use the enquiry trace explorer.

Select **Saved activity reports** to browse component and evaluation files in their original formats. Browsing does not run a scorer or call a model. Files larger than 5 MB and runtime files are omitted. The metric table uses the saved evaluation schema; reports with other formats are available to read without being assigned comparable scores.

For authenticated public HTTPS hosting alongside Langfuse, follow [public deployment](../observability/langfuse/PUBLIC_DEPLOYMENT.md). To move existing traces to another host, follow [historical migration](../observability/langfuse/HISTORICAL_MIGRATION.md). Saved report files are supplied by the checkout; historical Langfuse data requires the separate volume restore.
