"""Independent ranked retrieval diagnostics, separate from answer quality."""
import re
import unicodedata
from copilot.rag.document_retrieval.hybrid import _source_aliases, _source_url_key


def normalize(text):
    return ' '.join(unicodedata.normalize('NFKC',text).translate(str.maketrans(
        {'‘':"'",'’':"'",'“':'"','”':'"','`':None,'|':' ','\u200b':None,'\u00ad':None})).casefold().split()).strip('"')


def canonical(url):
    key = _source_url_key(url)
    return _source_aliases().get(key,key)


def score(hits, citations):
    sources = {canonical(c['url']) for c in citations}
    labels = {(canonical(c['url']),normalize(c['span'])) for c in citations
              if c.get('quote_or_summary') != 'summary' and normalize(c['span'])}
    spans, urls, first = set(), set(), None
    results = {}
    for rank,hit in enumerate(hits[:10],1):
        url = canonical(hit.get('doc_url',hit.get('source_url','')))
        text = normalize(hit.get('text',hit.get('relevant_passage','')))
        urls.add(url)
        matched = {label for label in labels if label[0]==url and re.search(r'(?<!\w)'+re.escape(label[1])+r'(?!\w)',text)}
        spans |= matched
        if matched and first is None:
            first = rank
        if rank in (1,5,10):
            results[f'span_recall_at_{rank}'] = len(spans)/len(labels) if labels else None
            results[f'source_recall_at_{rank}'] = len(urls & sources)/len(sources) if sources else None
    for k in (1,5,10):
        results.setdefault(f'span_recall_at_{k}',len(spans)/len(labels) if labels else None)
        results.setdefault(f'source_recall_at_{k}',len(urls & sources)/len(sources) if sources else None)
    return {**results,'span_mrr':1/first if first else 0 if labels else None,
            'verbatim_labels':len(labels),'summary_labels':sum(c.get('quote_or_summary')=='summary' for c in citations)}


def probe(context,mode):
    from copilot.rag.document_retrieval.hybrid import retrieve
    from copilot.rag.document_retrieval.query_analyzer import detect
    from copilot.enquiry_workflow.routing import broad_provider_search
    query = '\n'.join([turn['text'] for turn in context['history'] if turn['role']=='user']+[context['query']])
    providers = detect(query)['providers']
    discovery = broad_provider_search(query)
    filters = {'provider':providers[0]} if len(providers)==1 and not discovery else None
    return retrieve(query,filters=filters,k=10,mode=mode,rerank=mode=='hybrid',route=filters is None and not discovery)
