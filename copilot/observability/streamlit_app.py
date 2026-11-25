"""Inspect the trace database from a verification run."""
from contextlib import closing
import os
from pathlib import Path
import sqlite3

import streamlit as st

from copilot.observability.viewer import render
from copilot.case_storage.db import DB_PATH

st.set_page_config(page_title="Enquiry trace explorer", layout="wide")
st.title("Enquiry trace explorer")
path = Path(os.environ.get("COPILOT_TRACE_DB", DB_PATH)).expanduser().resolve()
if not path.is_file():
    st.info("Set COPILOT_TRACE_DB to an existing enquiry or verification trace database.")
    st.stop()
with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as con:
    con.row_factory = sqlite3.Row
    try:
        available, _ = render(con)
        if not available:
            st.info("This database has no instrumented enquiries.")
    except sqlite3.OperationalError:
        st.error("This database does not contain the observability schema. Choose a completed trace-verification run.")
