# Diagnostic incident evidence

The diagnostic gate now reuses the shared incident rules after validating customer assertions,
negation and resolution. Reported credit exhaustion with a stopped service collects an account
reference when restoration is requested. Incorrect autocomplete output collects the exact query
and returned prediction. Explicit credential exposure collects timing and unusual usage.

These changes affect suggested evidence collection. They do not change the selected route,
owner, pending reply, approval or action proposal. Ownership and escalation configuration were
unchanged when the source hashes were captured.

- 95 focused automated tests passed.
- The existing 52 working diagnostic inputs retained identical policy menus and fixture controls.
- No live model calls, frozen cases or holdout cases were used in this isolated regression.

The regression uses a fixed model proposal and an escalation fixture. It checks policy and
control preservation; it does not measure live route accuracy or answer F1.

From the repository root:

```sh
.venv/bin/python -B copilot/response_drafting/results/activity-14/workflow-review/diagnostic-incident-fix/reproduce.py
```

The script verifies the reviewed source and input hashes. It writes a separate reproduced
result, preserving the original report. `scope-hashes.json` contains the source lock and the
three incident examples; `working52-policy-regression.json` contains the original paired check.
Source snapshots and `inputs52.json` make the scope reviewable locally.
