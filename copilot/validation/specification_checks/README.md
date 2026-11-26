# Standalone specification checks

The checker maps a compatible GT workbook to the output schemas, then checks vocabulary, approval rules, required fields and the output token budget. It reads the workbook and writes validation artifacts separately.

From the repository root, run the historical C1 check with a compatible GT v2.5 workbook:

```bash
.venv/bin/python3 -m copilot.validation.specification_checks.validate_spec /path/to/gt_v2_5.xlsx --out-dir /tmp/c1
```

The command writes the report to `copilot/validation/specification_checks/validator-report.md` under the chosen output directory. The [saved C1 report](validator-report.md) records the original 532-record run, including the 80 frozen cases and the approval negative tests.
