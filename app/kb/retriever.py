"""
Hybrid RAG retriever: BM25 (sparse) + FAISS dense + cross-encoder reranker.

Chunking strategies (experiment via CHUNK_STRATEGY env var):
  fixed   — 600 chars, 80 overlap  (baseline)
  small   — 300 chars, 50 overlap  (fine-grained)
  large   — 1200 chars, 150 overlap (coarse)

Retrieval pipeline:
  1. BM25 top-K  (keyword match)
  2. FAISS top-K (semantic match)
  3. RRF fusion  (Reciprocal Rank Fusion — no score normalisation needed)
  4. Cross-encoder reranker — reranks fused candidates, returns top-N
"""
import os
import math
import pickle
from pathlib import Path
from typing import Optional

from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain.schema import Document
from app.llm import get_embeddings

# ── Paths ──────────────────────────────────────────────────────────────────────
_BASE = Path(__file__).resolve().parents[2]
KB_INDEX_PATH  = Path(os.getenv("KB_INDEX_PATH",  str(_BASE / "data" / "kb_index")))
BM25_INDEX_PATH = Path(os.getenv("BM25_INDEX_PATH", str(_BASE / "data" / "bm25_index.pkl")))
CORPUS_DIR     = Path(os.getenv("CORPUS_DIR",     str(_BASE / "data" / "corpus")))
KB_SOURCE      = _BASE / "data" / "knowledge_base.txt"

# ── Chunking strategies ────────────────────────────────────────────────────────
CHUNK_STRATEGIES = {
    "fixed": {"chunk_size": 600,  "chunk_overlap": 80},
    "small": {"chunk_size": 300,  "chunk_overlap": 50},
    "large": {"chunk_size": 1200, "chunk_overlap": 150},
}

def _get_splitter(strategy: str = "fixed") -> RecursiveCharacterTextSplitter:
    cfg = CHUNK_STRATEGIES.get(strategy, CHUNK_STRATEGIES["fixed"])
    return RecursiveCharacterTextSplitter(**cfg)


# ── Document loading ───────────────────────────────────────────────────────────
def _load_corpus() -> list[Document]:
    """Load corpus dir (MD files) + legacy knowledge_base.txt."""
    docs: list[Document] = []
    if CORPUS_DIR.exists():
        for md_file in sorted(CORPUS_DIR.glob("*.md")):
            loader = TextLoader(str(md_file), encoding="utf-8")
            docs.extend(loader.load())
    if KB_SOURCE.exists():
        loader = TextLoader(str(KB_SOURCE), encoding="utf-8")
        docs.extend(loader.load())
    return docs


# ── BM25 index ─────────────────────────────────────────────────────────────────
def _tokenise(text: str) -> list[str]:
    return text.lower().split()


def build_bm25_index(chunks: list[Document]) -> dict:
    """Build BM25 index as {idf, corpus_tokens, chunks}."""
    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        return {}
    corpus_tokens = [_tokenise(c.page_content) for c in chunks]
    bm25 = BM25Okapi(corpus_tokens)
    index = {"bm25": bm25, "chunks": chunks}
    BM25_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(BM25_INDEX_PATH, "wb") as f:
        pickle.dump(index, f)
    return index


def load_bm25_index() -> Optional[dict]:
    if BM25_INDEX_PATH.exists():
        with open(BM25_INDEX_PATH, "rb") as f:
            return pickle.load(f)
    return None


# ── FAISS dense index ──────────────────────────────────────────────────────────
def build_faiss_index(chunks: list[Document]) -> FAISS:
    store = FAISS.from_documents(chunks, get_embeddings())
    KB_INDEX_PATH.mkdir(parents=True, exist_ok=True)
    store.save_local(str(KB_INDEX_PATH))
    return store


def load_faiss_index() -> FAISS:
    if KB_INDEX_PATH.exists():
        return FAISS.load_local(
            str(KB_INDEX_PATH), get_embeddings(),
            allow_dangerous_deserialization=True
        )
    docs = _load_corpus()
    strategy = os.getenv("CHUNK_STRATEGY", "fixed")
    chunks = _get_splitter(strategy).split_documents(docs)
    return build_faiss_index(chunks)


# ── Full KB build (both indexes) ───────────────────────────────────────────────
def build_kb(strategy: str = "fixed") -> dict:
    docs = _load_corpus()
    chunks = _get_splitter(strategy).split_documents(docs)
    print(f"  Loaded {len(docs)} documents → {len(chunks)} chunks (strategy={strategy})")
    faiss_store = build_faiss_index(chunks)
    bm25_index  = build_bm25_index(chunks)
    return {"faiss": faiss_store, "bm25": bm25_index, "chunks": chunks}


# ── Reciprocal Rank Fusion ─────────────────────────────────────────────────────
def _rrf_fuse(
    dense_results: list[tuple[Document, float]],
    bm25_results:  list[tuple[Document, float]],
    k: int = 60,
) -> list[tuple[Document, float]]:
    """Fuse two ranked lists using RRF. Returns merged list sorted by RRF score desc."""
    scores: dict[str, float] = {}
    docs:   dict[str, Document] = {}

    for rank, (doc, _) in enumerate(dense_results):
        key = doc.page_content[:80]
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
        docs[key] = doc

    for rank, (doc, _) in enumerate(bm25_results):
        key = doc.page_content[:80]
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
        docs[key] = doc

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [(docs[key], score) for key, score in ranked]


# ── Cross-encoder reranker ─────────────────────────────────────────────────────
def _rerank(
    query: str,
    candidates: list[tuple[Document, float]],
    top_n: int,
) -> list[tuple[Document, float]]:
    """Rerank candidates with cross-encoder. Falls back to RRF order if unavailable."""
    try:
        from sentence_transformers import CrossEncoder
        model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        pairs = [(query, doc.page_content) for doc, _ in candidates]
        ce_scores = model.predict(pairs)
        reranked = sorted(
            zip([d for d, _ in candidates], ce_scores),
            key=lambda x: x[1], reverse=True
        )
        return [(doc, float(score)) for doc, score in reranked[:top_n]]
    except Exception:
        return candidates[:top_n]


# ── Singletons ─────────────────────────────────────────────────────────────────
_faiss_store: Optional[FAISS] = None
_bm25_index:  Optional[dict]  = None


def _get_stores():
    global _faiss_store, _bm25_index
    if _faiss_store is None:
        _faiss_store = load_faiss_index()
    if _bm25_index is None:
        _bm25_index = load_bm25_index()
    return _faiss_store, _bm25_index


# ── Public retrieve function ───────────────────────────────────────────────────
def retrieve(query: str, k: int = 4) -> list[dict]:
    """
    Hybrid retrieval: BM25 + FAISS → RRF fusion → cross-encoder rerank → top-k.
    Falls back to dense-only if BM25 index unavailable.
    """
    faiss_store, bm25_index = _get_stores()

    # 1. Dense retrieval
    fetch_k = k * 3
    dense_results = faiss_store.similarity_search_with_score(query, k=fetch_k)

    # 2. BM25 retrieval
    bm25_results: list[tuple[Document, float]] = []
    if bm25_index:
        try:
            tokens = _tokenise(query)
            bm25_scores = bm25_index["bm25"].get_scores(tokens)
            top_idx = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[:fetch_k]
            bm25_results = [(bm25_index["chunks"][i], float(bm25_scores[i])) for i in top_idx]
        except Exception:
            pass

    # 3. RRF fusion
    if bm25_results:
        fused = _rrf_fuse(dense_results, bm25_results)
    else:
        fused = dense_results

    # 4. Rerank
    reranked = _rerank(query, fused, top_n=k)

    return [
        {
            "content": doc.page_content,
            "source":  doc.metadata.get("source", "KB"),
            "score":   float(score),
        }
        for doc, score in reranked
    ]
