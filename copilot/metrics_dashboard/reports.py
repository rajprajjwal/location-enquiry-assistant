"""Browse saved report artifacts without executing evaluation commands."""
import json
from pathlib import Path
import streamlit as st

MAX_BYTES=5*1024*1024
EXTENSIONS={'.md','.json','.csv','.txt','.jsonl'}
EXCLUDED_PARTS={'runtime','source-snapshot','assets','chroma','private','__pycache__'}
EXCLUDED_FILES={'cases.jsonl','generations.jsonl','inputs.jsonl','gold.jsonl'}
DATA_REPORTS={'README.md','gt-review-results.csv','activity-4-freeze-audit.md',
              'activity-5-validation-audit.md','activity-5-review-queue.csv',
              'activity-5-duplicate-review.csv','activity-3-pilot-key.csv'}


def report_roots(repo):
    repo=Path(repo)
    return [repo/'results',repo/'data',*sorted((repo/'copilot').glob('*/results')),
            *sorted((repo/'eval').glob('*/results'))]


def available_reports(repo):
    found=[]
    for root in report_roots(repo):
        if not root.is_dir() or root.is_symlink():
            continue
        for path in root.rglob('*'):
            if path.is_file() and path.suffix in EXTENSIONS and path.stat().st_size<=MAX_BYTES:
                parts=path.relative_to(root).parts
                if root==Path(repo)/'data' and path.name not in DATA_REPORTS:
                    continue
                if path.name in EXCLUDED_FILES or EXCLUDED_PARTS.intersection(parts):
                    continue
                if path.resolve().is_relative_to(root.resolve()) and not any(p.startswith('.') for p in parts):
                    found.append(path)
    return sorted(found,key=lambda p:str(p.relative_to(repo)))


def read_report(repo,path):
    path=Path(path)
    if path not in available_reports(repo):
        raise ValueError('Only saved report artifacts may be opened')
    return path.read_bytes()


def render(repo):
    st.header('Saved activity reports')
    st.caption('Historical artifacts are read-only. Viewing or downloading them makes no model calls. Metrics use the configuration and review status recorded in each report.')
    query=st.text_input('Find reports',key='saved_report_search').casefold()
    paths=[p for p in available_reports(repo) if query in str(p.relative_to(repo)).casefold()]
    st.caption(f'{len(paths)} reports; individual files are limited to 5 MB. Runtime files, raw gold inputs and model caches are excluded.')
    if not paths:
        st.info('No matching saved reports.')
        return
    path=st.selectbox('Report',paths,format_func=lambda p:str(p.relative_to(repo)),key='saved_report_path')
    content=read_report(repo,path)
    st.download_button('Download report',content,file_name=path.name,key='download_saved_report')
    text=content.decode('utf-8',errors='replace')
    if path.suffix=='.md':
        st.markdown(text,unsafe_allow_html=False)
    elif path.suffix=='.json':
        try:
            st.json(json.loads(text),expanded=False)
        except json.JSONDecodeError:
            st.code(text,language='text')
    elif path.suffix=='.csv':
        import io
        import pandas as pd
        try:
            st.dataframe(pd.read_csv(io.StringIO(text)).head(1000),hide_index=True,width='stretch')
        except (pd.errors.ParserError,pd.errors.EmptyDataError):
            st.code(text,language='text')
    else:
        st.code(text,language='text')
