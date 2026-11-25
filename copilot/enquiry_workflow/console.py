"""Run a local enquiry through the same case service used by the UI."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sys

from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

from copilot.case_storage.db import connect, DB_PATH
from copilot.enquiry_workflow.cases import run_case
from copilot.enquiry_workflow.retrieval import rag_document_search, warm_retrieval_runtime


class EnquiryRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    query: str = Field(min_length=1)
    case_id: str | None = None
    customer: str | None = None
    customer_status: Literal['existing', 'new'] | None = None
    retrieval: Literal['bm25', 'hybrid'] = 'bm25'


def query_local(request, *, database=DB_PATH, client=None, search=None):
    """Keep case IDs for follow-ups and keep all actions in the sandbox."""
    request = EnquiryRequest.model_validate(request)
    if search is None:
        if request.retrieval == 'hybrid':
            warm_retrieval_runtime()
        search = rag_document_search(mode=request.retrieval, rerank=request.retrieval == 'hybrid')
    with closing(connect(database)) as con:
        result = run_case(con, request.query, case_id=request.case_id, customer=request.customer,
                          confirmed_customer_status=request.customer_status, client=client, search=search)
    return {'case_id': result['case_id'], 'trace_id': result['trace_id'], 'status': result['status'],
            'customer_response': result['customer_response']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, help='JSON request file; otherwise read JSON from stdin.')
    parser.add_argument('--output', type=Path, help='Save the response as JSON.')
    options = parser.parse_args()
    request = json.loads(options.request.read_text() if options.request else sys.stdin.read())
    result = query_local(request)
    text = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
    if options.output:
        options.output.write_text(text)
    else:
        print(text, end='', flush=True)


if __name__ == '__main__':
    main()
