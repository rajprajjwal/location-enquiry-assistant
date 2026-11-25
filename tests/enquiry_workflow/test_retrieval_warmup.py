"""The first timed search must not initialize a cold retrieval stack."""
from unittest.mock import Mock

from copilot.enquiry_workflow import retrieval
from copilot.rag.document_retrieval import hybrid, rerank


def test_warmup_initializes_full_hybrid_path_only_once(monkeypatch, tmp_path):
    import huggingface_hub

    cached = tmp_path/'model-file'
    cached.write_text('cached')
    monkeypatch.setattr(huggingface_hub, 'try_to_load_from_cache', lambda *a, **kw: str(cached))
    model = Mock()
    search = Mock(return_value=[{'chunk_id': 'one'}])
    monkeypatch.setattr(rerank, '_model', lambda: model)
    monkeypatch.setattr(hybrid, 'retrieve', search)
    retrieval.warm_retrieval_runtime.cache_clear()
    try:
        retrieval.warm_retrieval_runtime()
        retrieval.warm_retrieval_runtime()
        model.predict.assert_called_once()
        search.assert_called_once_with('Directions API documentation', mode='hybrid', rerank=True, k=1)
    finally:
        retrieval.warm_retrieval_runtime.cache_clear()
