"""Display every harness metric without recomputing or editing run artifacts."""
import json
from pathlib import Path
import streamlit as st
from copilot.evaluation.artifacts import load,aggregate
from copilot.evaluation.contracts import METRICS


def available_runs(root):
    found=[]
    for path in Path(root).glob('**/summary.json'):
        try:
            value=load(path.parent)
        except (ValueError,KeyError,OSError,json.JSONDecodeError):
            continue
        found.append((path.parent,value))
    return sorted(found,key=lambda item:item[0].stat().st_mtime_ns,reverse=True)


def render(root):
    st.title('Evaluation comparisons')
    st.caption('Read-only saved results. New completed runs are discovered automatically. Ratios use scored-case averages; citation precision and tool success are weighted by citation and call counts.')
    runs=available_runs(root)
    if not runs:
        st.info('No completed evaluation runs found. Run the evaluation harness first.')
        return
    choices={str(p):s for p,s in runs}
    chosen=st.selectbox('Evaluation run',list(choices),format_func=lambda p:Path(p).name,key='eval_run')
    summary=choices[chosen]
    manifest=summary['manifest']
    st.caption(f"Split: {manifest['split']} · Strategy: {manifest['binding']['strategy']} · Retrieval: {manifest['binding']['retrieval']}")
    st.warning('Answer-quality scores use automatic model judgement. Cost figures are illustrative INR estimates; actual institute endpoint charges are ₹0.')
    rows=[json.loads(l) for l in (Path(chosen)/'records.jsonl').read_text().splitlines()]
    selected=rows
    columns=st.columns(3)
    for col,key,label in zip(columns,('bucket','api','team'),('Bucket','API','Team')):
        values=sorted({r[key] for r in rows})
        with col:
            value=st.selectbox(label,['All',*values],key='eval_'+key)
        if value!='All':
            selected=[r for r in selected if r[key]==value]
    st.caption(f"{len({r['record_id'] for r in selected})} cases · {len(selected)} arm records · {sum(bool(r.get('generation_error') or r.get('judge_error')) for r in selected)} generation/judge errors")
    groups={(r['arm'],r['metric']):r for r in aggregate(selected) if r['dimension']=='overall'}
    catalog=summary['metric_catalog']
    display=[]
    for key,definition in catalog.items():
        label,unit=definition['label'],definition['unit']
        item={'Metric':label,'Unit':unit}
        values={}
        for arm in ('baseline','agent'):
            entry=groups.get((arm,key),{})
            score=entry.get('score')
            values[arm]=score
            item[arm.title()]=score
            item[arm.title()+' scored']=f"{entry.get('scored',0)}/{entry.get('cases',0)}"
        item['Agent − baseline']=values['agent']-values['baseline'] if all(v is not None for v in values.values()) else None
        display.append(item)
    st.dataframe(display,hide_index=True,use_container_width=True)
    metric=st.selectbox('Chart metric',list(catalog),format_func=lambda k:catalog[k]['label'],key='eval_metric')
    points=[{'Arm':arm,'Value':groups[arm,metric]['score']} for arm in ('baseline','agent')
            if (arm,metric) in groups and groups[arm,metric]['score'] is not None]
    if points:
        st.bar_chart(points,x='Arm',y='Value')
    else:
        st.info('This metric is not applicable or has no scored records for the selected filters.')
    with st.expander('Case scores and errors'):
        st.dataframe([{'record_id':r['record_id'],'arm':r['arm'],'bucket':r['bucket'],
                       'error':r.get('generation_error') or r.get('judge_error') or r.get('retrieval_error'),
                       **r['metrics']} for r in selected],hide_index=True)
    with st.expander('Run binding and metric definitions'):
        st.json(manifest)
        st.json(summary['metric_catalog'])
    st.download_button('Download evaluation summary',json.dumps(summary,indent=2),
                       file_name=Path(chosen).name+'-summary.json',mime='application/json')
