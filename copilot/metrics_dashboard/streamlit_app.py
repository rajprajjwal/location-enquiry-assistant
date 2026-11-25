"""Start the automatically refreshing evaluation dashboard."""
import os
from pathlib import Path
import streamlit as st
from copilot.paths import REPO_ROOT
from copilot.metrics_dashboard.viewer import render

st.set_page_config(page_title='Evaluation comparisons',layout='wide')

@st.fragment(run_every=10)
def dashboard():
    target=os.environ.get('COPILOT_LANGFUSE_URL','')
    if target.startswith('https://'):
        st.link_button('Open Langfuse traces',target)
    view=st.radio('View',['Evaluation metrics','Saved activity reports'],horizontal=True,key='reports_view')
    if view=='Saved activity reports':
        from copilot.metrics_dashboard.reports import render as render_reports
        render_reports(Path(os.environ.get('COPILOT_REPORTS_ROOT',REPO_ROOT)))
    else:
        render(Path(os.environ.get('COPILOT_EVAL_RESULTS',REPO_ROOT/'results/evaluation')))

dashboard()
