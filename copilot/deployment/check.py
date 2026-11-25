"""Check local prerequisites and optionally probe the live services."""
import argparse
from contextlib import closing
import hashlib
import importlib
import json
import os
from pathlib import Path


def verify(mode="hybrid", *, live=False):
    checks = []

    def check(name, action):
        try:
            detail = action()
            checks.append({"check": name, "passed": True, "detail": detail})
        except Exception as error:
            # Credentials and service response bodies never enter the report.
            checks.append({"check": name, "passed": False, "error_type": type(error).__name__})

    def dependencies():
        modules = ["streamlit", "yaml", "bs4", "lxml", "rank_bm25", "openai", "langgraph.graph"]
        if mode == "hybrid":
            modules += ["chromadb", "sentence_transformers", "transformers"]
        for module in modules:
            importlib.import_module(module)
        return modules

    check("dependencies", dependencies)

    def tokenizer():
        from copilot.model_gateway.token_counting import count_text
        assert count_text("Setup check") > 0
        return "Pinned Qwen tokenizer verified"

    check("chat_tokenizer", tokenizer)

    def chat_config():
        from copilot.model_gateway.client import LLMClient
        LLMClient()
        return "Chat credentials and CA loaded; no request sent"

    check("chat_configuration", chat_config)

    def storage():
        from copilot.case_storage.db import connect, DB_PATH
        with closing(connect(DB_PATH)) as con:
            assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        return "Local case database is writable and valid"

    check("case_storage", storage)

    def reviewers():
        from copilot.case_storage.cases import approver_names
        assert approver_names(), "Configure at least one authorized reviewer"
        return "Reviewer list configured; selector does not authenticate identities"

    check("reviewers", reviewers)

    def corpus():
        from copilot.rag.document_indexing.bm25 import load_chunks, BM25Index
        chunks = load_chunks()
        assert chunks and BM25Index(chunks).search("Directions API", k=5)
        return {"chunks": len(chunks), "documents": len({c["doc_url"] for c in chunks})}

    check("bm25_corpus", corpus)
    if mode == "hybrid":
        def embedding_config():
            from copilot.settings import settings
            assert settings.embed_backend == "endpoint", "Use the institute embedding endpoint"
            assert settings.embed_base_url and settings.embed_api_key
            if settings.embed_ca_bundle:
                assert Path(settings.embed_ca_bundle).is_file()
            return "Embedding credentials configured"

        check("embedding_configuration", embedding_config)

        def dense_index():
            from copilot.rag.document_indexing.vector_store import get_collection
            from copilot.rag.document_indexing.bm25 import CHUNKS, load_chunks
            from copilot.rag.document_indexing.embed import backend_info
            col = get_collection()
            assert col.count() == len(load_chunks())
            assert col.metadata["corpus_sha256"] == hashlib.sha256(CHUNKS.read_bytes()).hexdigest()
            assert col.metadata["embed_model"] == backend_info()["model"]
            assert col.metadata["chunk_budget"] == 480
            return "Dense count, corpus checksum, model and chunk budget match"

        check("dense_index", dense_index)

        def model_cache():
            from huggingface_hub import try_to_load_from_cache
            from copilot.rag.model_assets import RERANK_MODEL, RERANK_REVISION
            required = ["model.safetensors", "config.json", "tokenizer_config.json", "tokenizer.json"]
            for filename in required:
                cached = try_to_load_from_cache(RERANK_MODEL, filename, revision=RERANK_REVISION)
                assert isinstance(cached, str) and Path(cached).is_file()
            return "Pinned reranker files cached"

        check("reranker_assets", model_cache)

    if live and all(row["passed"] for row in checks):
        def model_smoke():
            from copilot.model_gateway.client import LLMClient
            from copilot.model_gateway.endpoint_checks import smoke
            rows = smoke(LLMClient(timeout=30))
            assert all(row["passed"] for row in rows), "One or more model probes failed"
            return {row["probe"]: row["passed"] for row in rows}

        check("live_chat_json_tools", model_smoke)
        if mode == "hybrid":
            def retrieval():
                from copilot.rag.document_retrieval.hybrid import retrieve
                queries = [
                    "What coordinate order does Mapbox Directions use?",
                    "How does Google Distance Matrix bill origin destination elements?",
                    "How do Google Autocomplete session tokens work?",
                    "How do I reverse geocode coordinates using Ola Maps?",
                ]
                for query in queries:
                    hits = retrieve(query, mode="hybrid", rerank=True, k=5)
                    assert hits and all(hit.get("doc_url") and hit.get("text") for hit in hits)
                return {"synthetic_queries": len(queries), "reranking": True}

            check("live_hybrid_reranking", retrieval)
    return {"passed": all(row["passed"] for row in checks), "mode": mode, "live_requested": live,
            "checks": checks, "frozen_or_holdout_used": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("bm25", "hybrid"), default="hybrid")
    parser.add_argument("--live", action="store_true", help="Probe live chat and retrieval after local checks pass.")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    result = verify(args.mode, live=args.live)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
