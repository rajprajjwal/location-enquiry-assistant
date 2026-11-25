"""Exercise the local UI with synthetic enquiries and a temporary database."""

import argparse
from contextlib import closing
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from copilot.case_storage import sandbox
from copilot.case_storage import cases
from copilot.case_storage.db import connect
from copilot.paths import PACKAGE_ROOT
from streamlit.testing.v1 import AppTest


def verify(*, retrieval="BM25"):
    records = []
    with TemporaryDirectory() as temp:
        db = Path(temp) / "e2e.db"
        with patch("copilot.case_storage.db.DB_PATH", db):
            app_path = PACKAGE_ROOT / "streamlit_ui/streamlit_app.py"
            ui = AppTest.from_file(str(app_path), default_timeout=150).run()
            ui.radio[0].set_value(retrieval).run()
            assert not ui.exception, ui.exception
            assert not ui.exception, ui.exception

            def button(label):
                return next(item for item in ui.button if item.label == label)

            def submit(query, expected, name, *, new_case=True):
                if new_case:
                    ui.selectbox(key="selected_case").select_index(0).run()
                ui.text_area[0].set_value(query)
                button("Run enquiry").click().run()
                assert not ui.exception, ui.exception
                case_id = ui.selectbox(key="selected_case").value
                with closing(connect(db)) as con:
                    result = cases.load_state(con, case_id)["last_result"]
                row = {
                    "check": name, "expected": expected, "status": result["status"],
                    "steps": result["step_count"], "critic": result["critic"],
                }
                row["passed"] = result["status"] == expected and result["step_count"] <= 10
                records.append(row)
                print(json.dumps(row), flush=True)
                return result

            submit("What is the direction API?", "final", "general Directions definition")
            submit("What coordinate order does the Mapbox Directions API use?", "final", "provider support")
            submit("How do I set waypoints in the Directions API?", "clarification_needed", "provider clarification")
            submit("Mapbox", "final", "provider follow-up", new_case=False)
            submit(
                "Compare Ola Maps and Google Maps Directions for 50,000 requests per month without traffic.",
                "final", "deterministic price comparison",
            )
            submit("How much would the Mapbox Directions API cost per month?", "clarification_needed", "missing monthly volume")
            submit(
                "Compare the maximum number of coordinates per Directions request for Mapbox versus Google Maps.",
                "final", "documentation limits comparison",
            )
            update = submit(
                "Update sandbox ticket TKT-123. Set status to Investigating.", "final", "sandbox proposal",
            )
            if update["status"] == "final":
                with closing(connect(db)) as con:
                    action, = cases.list_pending(con, update["case_id"])
                    assert action["type"] == "record_update"
                    assert sandbox.get(con, "TKT-123") == {}
                button("Approve").click().run()
                assert not ui.exception, ui.exception
                with closing(connect(db)) as con:
                    assert sandbox.get(con, "TKT-123") == {"status": "Investigating"}
                    assert cases.decision_log(con)[0]["decision"] == "approved"
                records.append({"check": "sandbox approval and decision log", "passed": True})
            incident = submit(
                "Production is down. Directions returns 503 for all requests.", "escalated", "incident handoff",
            )
            with closing(connect(db)) as con:
                action, = cases.list_pending(con, incident["case_id"])
                assert action["payload"]["owner"] == "Maps engineering"
                assert action["status"] == "pending"
            records.append({"check": "incident approval held", "passed": True})
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retrieval", choices=("bm25", "hybrid"), default="bm25")
    args = parser.parse_args()
    evidence = verify(retrieval="Hybrid with reranking" if args.retrieval == "hybrid" else "BM25")
    print(json.dumps({"passed": all(row["passed"] for row in evidence), "checks": evidence}, indent=2))
    raise SystemExit(not all(row["passed"] for row in evidence))
