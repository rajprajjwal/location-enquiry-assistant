from contextlib import closing

import pytest

from copilot.case_storage import cases, handlers
from copilot.case_storage.db import connect


@pytest.mark.parametrize("decision", ["approve", "edit", "reject"])
def test_escalation_decision_records_the_applied_diff(tmp_path, monkeypatch, decision):
    reviewer = "test_reviewer"
    monkeypatch.setattr(cases, "_approvers_cfg", lambda: {
        "approvers": [{"name": reviewer, "can_approve": "all"}],
    })
    db = tmp_path / "review.db"
    with closing(connect(db)) as con:
        cid = cases.create_case(con)
        payload = {"owner": "Maps engineering", "severity": "SEV1", "summary": "Production outage."}
        aid = cases.request_approval(con, cid, "escalation", payload)
        assert cases.get_case(con, cid)["owner"] is None
        with pytest.raises(ValueError, match="only an approved"):
            cases.apply_approved(con, aid, lambda _: pytest.fail("pending action executed"))
        if decision == "reject":
            handlers.reject(con, aid, approver=reviewer, note="No incident.")
        else:
            edited = {**payload, "summary": "Confirmed production outage."} if decision == "edit" else None
            handlers.approve_and_apply(con, aid, approver=reviewer, edited_payload=edited)
    with closing(connect(db)) as con:
        audit, = cases.decision_log(con)
        assert audit["reviewer"] == reviewer and audit["decided_at"]
        assert isinstance(audit["final_diff"], dict)
        if decision == "reject":
            assert audit["decision"] == "rejected"
            assert audit["final_diff"] == {}
            assert audit["applied_at"] is None
            assert cases.get_case(con, cid)["owner"] is None
        else:
            assert audit["decision"] == "approved" and audit["applied_at"]
            final = cases.get_case(con, cid)
            for field, diff in audit["final_diff"].items():
                assert final[field] == diff["new"]
            assert audit["final_diff"]["status"] == {"old": "approved_pending_apply", "new": "escalated"}
            if decision == "edit":
                assert audit["edited"]
                assert audit["final"]["summary"] == "Confirmed production outage."
            with pytest.raises(ValueError, match="already applied"):
                cases.apply_approved(con, aid, lambda _: pytest.fail("duplicate execution"))
