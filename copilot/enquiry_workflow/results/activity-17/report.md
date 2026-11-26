# Activity 17 human review acceptance

Activity 17 meets its acceptance criteria in the controlled sandbox.

| Acceptance check | Result |
|---|---:|
| Consequential actions held for review | 20/20 (100%) |
| Reviewer logged | 20/20 (100%) |
| Decision timestamp logged | 20/20 (100%) |
| Decision logged | 20/20 (100%) |
| Final applied diff logged | 20/20 (100%) |

The 20 actions include 10 sandbox record updates and 10 escalations. Decisions cover eight approvals, six edited approvals and six rejections. Rejected actions log an empty applied diff. Approved escalation diffs record the case fields changed by application. Edited proposals preserve the final reviewed content.

The verifier uses the real Streamlit interface to submit enquiries, inspect the pending queue and record review decisions. It checks the database and UI after reopening. Pending actions cannot execute, unauthorized reviewers are blocked, approvals cannot execute twice, and rejected actions make no consequential change.

The test uses synthetic enquiries, an isolated temporary database, and a synthetic authorized reviewer. Model responses and follow-up selection are controlled. Diagnostic planning is disabled to isolate the review workflow. The acceptance check measures the review queue and audit behavior.

Verification code is in copilot/enquiry_workflow/verification/verify_review.py. Run it from the repository root with the configured virtual environment and an output directory:
 
    PYTHONPATH="$PWD" .venv/bin/python copilot/enquiry_workflow/verification/verify_review.py /tmp/activity17-review

The original local case database, approved ground truth, and other activities' scores are preserved.

Seventeen related regression tests passed with the real interpretation validator. The saved verification command was rerun successfully from the repository root.
