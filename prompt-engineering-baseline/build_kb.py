# Source history: Raj Kumar (a3ef3a6); see source-history.json.
"""
Build the knowledge base indexes (run once, or after corpus changes).

Usage:
  python build_kb.py                    # default fixed chunking
  python build_kb.py --strategy small   # 300-char chunks
  python build_kb.py --strategy large   # 1200-char chunks
  python build_kb.py --compare          # run all 3 strategies, print chunk counts
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

from app.kb.retriever import build_kb, CHUNK_STRATEGIES, _load_corpus, _get_splitter
from app.db.models import init_db


def compare_strategies():
    docs = _load_corpus()
    print(f"\nCorpus: {len(docs)} documents loaded\n")
    print(f"{'Strategy':<10} {'Chunk size':>12} {'Overlap':>10} {'Chunks':>10}")
    print("-" * 46)
    for name, cfg in CHUNK_STRATEGIES.items():
        chunks = _get_splitter(name).split_documents(docs)
        print(f"{name:<10} {cfg['chunk_size']:>12} {cfg['chunk_overlap']:>10} {len(chunks):>10}")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", default="fixed",
                        choices=list(CHUNK_STRATEGIES.keys()),
                        help="Chunking strategy to use")
    parser.add_argument("--compare", action="store_true",
                        help="Compare all chunking strategies without building")
    args = parser.parse_args()

    print("Initialising database...")
    init_db()

    if args.compare:
        compare_strategies()
        sys.exit(0)

    print(f"Building knowledge base (strategy={args.strategy})...")
    result = build_kb(strategy=args.strategy)
    chunks = result["chunks"]
    bm25   = result["bm25"]

    print(f"\n✓ FAISS index built — {len(chunks)} chunks → data/kb_index/")
    if bm25:
        print(f"✓ BM25  index built — {len(chunks)} chunks → data/bm25_index.pkl")
    else:
        print("⚠ BM25 index skipped — install rank-bm25: pip install rank-bm25")
    print(f"\nChunk strategy : {args.strategy}")
    print(f"Chunk size     : {CHUNK_STRATEGIES[args.strategy]['chunk_size']} chars")
    print(f"Chunk overlap  : {CHUNK_STRATEGIES[args.strategy]['chunk_overlap']} chars")
    print(f"Total chunks   : {len(chunks)}")
    print(f"Corpus docs    : {len(set(c.metadata.get('source','') for c in chunks))}")
