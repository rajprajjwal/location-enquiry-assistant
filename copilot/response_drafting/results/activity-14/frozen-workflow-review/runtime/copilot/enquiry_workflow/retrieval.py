"""Adapt ranked RAG passages to the shared document search tool."""

from importlib.util import find_spec
from pathlib import Path

from copilot.registered_tools.tool_registry import DocumentSearchTool

from .routing import broad_provider_search


class RetrievalUnavailable(RuntimeError):
    """A user-facing retrieval error with no credential or response details."""


def retrieval_setup_issues(mode: str = "hybrid", *, rerank: bool = True) -> list[str]:
    """Check local prerequisites without creating an index or contacting an endpoint."""
    from copilot.rag.document_indexing.embed import backend
    from copilot.rag.document_indexing.vector_store import ROOT
    from copilot.settings import settings

    issues = []
    if mode in {"hybrid", "dense"}:
        if find_spec("chromadb") is None:
            issues.append("Install the hybrid retrieval dependencies (ChromaDB is missing).")
        backend_name = backend()
        if backend_name == "endpoint":
            missing = [
                name for name, value in (
                    ("EMBED_BASE_URL", settings.embed_base_url),
                    ("EMBED_API_KEY", settings.embed_api_key),
                ) if not value.strip()
            ]
            if missing:
                issues.append(f"Set {' and '.join(missing)} for the embedding endpoint.")
            if settings.embed_ca_bundle and not Path(settings.embed_ca_bundle).is_file():
                issues.append("Point EMBED_CA_BUNDLE to the embedding service CA certificate.")
        elif backend_name != "local":
            issues.append("Set EMBED_BACKEND to endpoint or local.")
        if not (ROOT / "data" / "chroma" / "chroma.sqlite3").is_file():
            issues.append("Build the dense index with python -m copilot.rag.document_indexing.build_index.")
    if (rerank or (mode in {"hybrid", "dense"} and backend() == "local")) and (
        find_spec("sentence_transformers") is None
    ):
        issues.append("Install the hybrid retrieval dependencies (sentence-transformers is missing).")
    return issues


def rag_document_search(
    *, mode: str = "hybrid", rerank: bool = True
) -> DocumentSearchTool:
    """Build the real search adapter. Use BM25 for offline development."""
    if mode not in {"hybrid", "bm25", "dense"}:
        raise ValueError(f"Unknown retrieval mode: {mode}")

    def search(query: str) -> list[dict]:
        from copilot.rag.document_indexing.embed import EmbeddingError
        from copilot.rag.document_retrieval.hybrid import retrieve

        from .reference_search import supplemental_passages
        from copilot.rag.document_retrieval.query_analyzer import detect

        if mode != "bm25" or rerank:
            issues = retrieval_setup_issues(mode, rerank=rerank)
            if issues:
                raise RetrievalUnavailable("Hybrid retrieval is unavailable. " + " ".join(issues))
        providers = detect(query)["providers"]
        discovery = broad_provider_search(query)
        filters = {"provider": providers[0]} if len(providers) == 1 and not discovery else None
        try:
            hits = retrieve(query, filters=filters, k=5, mode=mode, rerank=rerank, route=filters is None and not discovery)
            extra = supplemental_passages(query, [] if discovery else providers, hits)
            if extra:
                floor = min((hit["score"] for hit in hits), default=0)
                # Keep required reference sections within the tool's seven-hit budget.
                extra_ids = {hit["chunk_id"] for hit in extra}
                hits = [hit for hit in hits if hit["chunk_id"] not in extra_ids][:7 - len(extra)]
                hits.extend({**hit, "score": floor - 1} for hit in extra)
        except EmbeddingError as exc:
            raise RetrievalUnavailable(
                "The embedding service did not return usable vectors. Check its URL, credentials and certificate."
            ) from exc
        except Exception as exc:
            if mode == "bm25" and not rerank:
                raise
            raise RetrievalUnavailable(
                "Hybrid retrieval could not run. Check the dense index for the selected backend "
                "and that the reranker model can load. Use BM25 while you check setup."
            ) from exc
        return [
            {
                "document_id": hit["chunk_id"],
                "document_title": hit.get("title") or "Documentation",
                "source_url": hit["doc_url"],
                "retrieved_date": hit["fetched_at"],
                "relevant_passage": hit["text"],
                "relevance_score": hit["score"],
                "document_type": hit.get("kind") or "reference",
            }
            for hit in hits
            if hit.get("doc_url") and hit.get("fetched_at") and hit.get("text")
        ]

    def scoped_search(scope):
        from copilot.rag.document_indexing.bm25 import load_chunks
        from .comparison_evidence import reference_hits

        matches = reference_hits(scope, load_chunks(), url_key="doc_url", text_key="text")
        return [
            {"document_id": f"{chunk['chunk_id']}:{name}", "document_title": chunk.get("title") or "Documentation",
             "source_url": chunk["doc_url"], "retrieved_date": chunk["fetched_at"],
             "relevant_passage": chunk["text"], "relevance_score": 1.0}
            for name, (chunk, _) in matches.items()
        ]

    return DocumentSearchTool(search_function=search, scoped_search=scoped_search)
