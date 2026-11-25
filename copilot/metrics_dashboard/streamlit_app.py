"""Start the automatically refreshing evaluation dashboard."""
import os
from pathlib import Path
import streamlit as st
from copilot.paths import REPO_ROOT
from copilot.metrics_dashboard.viewer import render

st.set_page_config(page_title='Evaluation comparisons',layout='wide')

@st.fragment(run_every=10)
def dashboard():
    render(Path(os.environ.get('COPILOT_EVAL_RESULTS',REPO_ROOT/'results/evaluation')))

dashboard()
