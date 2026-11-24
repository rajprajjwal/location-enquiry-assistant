from copilot.enquiry_workflow import retrieval
from copilot.rag.document_retrieval import hybrid, rerank


def test_application_hybrid_reranks_one_passage_per_source_from_top_30(monkeypatch, tmp_path):
    manifest = tmp_path / "sources.yaml"
    manifest.write_text(
        "sources:\n"
        "- url: https://example.com/directions?version=1\n"
        "  aliases:\n"
        "  - https://example.com/old-directions\n",
        encoding="utf-8",
    )
    urls = [
        "https://example.com/old-directions#request",
        "https://EXAMPLE.com/directions/?version=1#waypoints",
        "https://example.com/directions?version=2",
        *[f"https://example.com/reference/{i}" for i in range(3, 32)],
    ]
    hits = [
        {
            "chunk_id": str(i), "doc_url": url, "title": f"Reference {i}",
            "fetched_at": "2026-11-22T00:00:00+00:00", "text": f"Passage {i}", "kind": "html",
        }
        for i, url in enumerate(urls)
    ]
    monkeypatch.setattr(hybrid, "SOURCE_MANIFEST", manifest)
    monkeypatch.setattr(retrieval, "retrieval_setup_issues", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(hybrid, "bm25_search", lambda _q, _filters: hits[16:])
    monkeypatch.setattr(hybrid, "dense_search", lambda _q, _filters: hits[:16])
    reranked = []

    def capture(_query, candidates, top_k):
        reranked.extend(candidates)
        return [{**item, "score": 1 / (n + 1)} for n, item in enumerate(candidates[:top_k])]

    monkeypatch.setattr(rerank, "rerank", capture)
    hybrid._source_aliases.cache_clear()
    try:
        result = retrieval.rag_document_search().search("How do I set waypoints?")
    finally:
        hybrid._source_aliases.cache_clear()

    fused_top = hybrid.rrf([hits[16:], hits[:16]])[:30]
    expected = [item["chunk_id"] for item in fused_top if item["chunk_id"] != "1"]
    assert [item["chunk_id"] for item in reranked] == expected
    assert len(reranked) == 29
    assert [item["document_id"] for item in result] == expected[:5]
    assert next(item for item in result if item["document_id"] == "0")["source_url"] == urls[0]
    assert {item["document_id"] for item in result} >= {"0", "2"}
