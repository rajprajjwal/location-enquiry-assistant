# Source history: Deepshikha (7b89516), deepshikha/lbs-copilot. See copilot/enquiry_workflow/source-history.json.
"""Build and verify BM25 and Chroma using one source snapshot."""
from copilot.paths import CONFIG_DIR
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
from hashlib import sha256
import json
from math import isfinite
import os
from pathlib import Path
import tempfile
import time
from uuid import uuid4

import yaml

from ..document_ingestion.chunk import EMBED_TOKENS, model_tokens
from .bm25 import BM25Index, CHUNKS
from .embed import backend_info, embed_docs, embed_query
from .vector_store import META_KEYS, ROOT, add_chunks, client, collection_name

SOURCE_MANIFEST = CONFIG_DIR / "sources.yaml"
LOCK = ROOT / "data" / "chroma" / ".rebuild.lock"
BATCH_SIZE = 256


@contextmanager
def rebuild_lock():
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open("a") as file:
        try:
            fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("A retrieval index rebuild is already running.") from None
        yield


def stage_file(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as file:
        temporary = Path(file.name)
        try:
            file.write(content)
            if path.exists():
                os.fchmod(file.fileno(), path.stat().st_mode & 0o777)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    return temporary


def read_corpus(sources, old_chunks, raw_snapshot):
    if raw_snapshot is None:
        if old_chunks is None:
            raise ValueError("No processed corpus. Pass --raw-snapshot with a complete raw source snapshot.")
        chunks = [json.loads(line) for line in old_chunks.splitlines() if line.strip()]
        return chunks, old_chunks

    from ..document_ingestion.run_ingest import collect_chunks

    chunks, problems = collect_chunks(raw_snapshot, sources)
    if problems:
        examples = ", ".join(f"{url} ({reason})" for url, reason in problems[:5])
        raise ValueError(f"Raw snapshot has {len(problems)} missing or unreadable sources. {examples}")
    blob = "".join(json.dumps(chunk, ensure_ascii=False) + "\n" for chunk in chunks).encode()
    return chunks, blob


def validate_corpus(chunks, sources):
    expected = {source["url"] for source in sources}
    indexed = {chunk["doc_url"] for chunk in chunks}
    if not chunks or len(expected) != len(sources) or indexed != expected:
        raise ValueError(f"Source coverage mismatch: {len(expected - indexed)} missing, {len(indexed - expected)} extra.")
    if len({chunk["chunk_id"] for chunk in chunks}) != len(chunks):
        raise ValueError("Chunk IDs must be unique.")
    if not 1 <= EMBED_TOKENS <= 512:
        raise ValueError("The chunk budget must be between 1 and 512 model tokens.")

    maximum = 0
    for chunk in chunks:
        if not all(chunk.get(field) for field in ("chunk_id", "doc_url", "provider", "api", "fetched_at", "licence", "kind", "text")):
            raise ValueError(f"Missing source metadata for {chunk.get('doc_url')}.")
        count = model_tokens(chunk["text"])
        if count != chunk["n_tokens"] or count > EMBED_TOKENS:
            raise ValueError(f"Chunk {chunk['chunk_id']} fails the {EMBED_TOKENS}-token budget or recorded token count.")
        maximum = max(maximum, count)
    return maximum


def verify_index(collection, chunks):
    expected = {chunk["chunk_id"]: chunk for chunk in chunks}
    count = collection.count()
    if count != len(expected):
        raise RuntimeError(f"Dense index contains {count} of {len(expected)} expected chunks.")
    verified = set()
    for offset in range(0, count, BATCH_SIZE):
        page = collection.get(limit=BATCH_SIZE, offset=offset, include=["documents", "metadatas"])
        for cid, text, metadata in zip(page["ids"], page["documents"], page["metadatas"], strict=True):
            reference = expected.get(cid)
            if cid in verified or reference is None or text != reference["text"]:
                raise RuntimeError(f"Dense index text or ID verification failed for {cid}.")
            if any(metadata.get(key) != (reference.get(key) or "") for key in META_KEYS):
                raise RuntimeError(f"Dense citation metadata verification failed for {cid}.")
            verified.add(cid)
    if verified != expected.keys():
        raise RuntimeError("Dense index ID verification is incomplete.")


def embed_batches(collection, chunks, dimensions):
    for offset in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[offset:offset+BATCH_SIZE]
        vectors = embed_docs([chunk["text"] for chunk in batch])
        if len(vectors) != len(batch) or any(
            len(v) != dimensions or not all(isfinite(n) for n in v) or not any(v) for v in vectors
        ):
            raise RuntimeError("Embedding endpoint returned invalid vectors.")
        add_chunks(collection, batch, vectors)
        print(f"Indexed {offset + len(batch)}/{len(chunks)} chunks.", flush=True)


def publish(store, candidate, name, backup_name, old_chunks, chunk_file):
    old = store.get_collection(name) if name in {c.name for c in store.list_collections()} else None
    moved_old = promoted = swapped_chunks = False
    try:
        if old is not None:
            old.modify(name=backup_name)
            moved_old = True
        candidate.modify(name=name)
        promoted = True
        if chunk_file is not None:
            chunk_file.replace(CHUNKS)
            swapped_chunks = True
        if store.get_collection(name).id != candidate.id:
            raise RuntimeError("The live dense index did not reopen after publication.")
    except BaseException:
        if promoted:
            candidate.modify(name=backup_name + "_failed")
        if moved_old:
            old.modify(name=name)
        if swapped_chunks:
            if old_chunks is None:
                CHUNKS.unlink()
            else:
                stage_file(CHUNKS, old_chunks).replace(CHUNKS)
        raise
    return backup_name if moved_old else None


def rebuild(raw_snapshot=None, report_path=None):
    initial_sources = SOURCE_MANIFEST.read_bytes()
    sources = yaml.safe_load(initial_sources)["sources"]
    old_chunks = CHUNKS.read_bytes() if CHUNKS.exists() else None
    chunks, blob = read_corpus(sources, old_chunks, raw_snapshot)
    maximum = validate_corpus(chunks, sources)
    corpus_hash = sha256(blob).hexdigest()
    max_docs = len(sources)
    model = backend_info()
    name = collection_name()
    unique = uuid4().hex[:12]
    staged_name, backup_name = f"{name}_build_{unique}", f"{name}_previous_{unique}"

    bm25 = BM25Index(chunks)
    if bm25.bm25.corpus_size != len(chunks):
        raise RuntimeError("BM25 corpus count does not match the validated chunks.")
    probe = f"{chunks[0]['provider']} {chunks[0]['section']}"
    bm25_hits = bm25.search(probe, k=5)
    if not bm25_hits:
        # Tiny corpora can legitimately have no positive BM25 scores.
        positive_term = next((term for term, value in bm25.bm25.idf.items() if value > 0), None)
        if positive_term is not None:
            bm25_hits = bm25.search(positive_term, k=5)
            if not bm25_hits:
                raise RuntimeError("BM25 returned no hit for an indexed term with positive IDF.")

    print(f"Verified BM25 for {max_docs} documents and {len(chunks)} chunks. Building dense index.", flush=True)
    chunk_file = stage_file(CHUNKS, blob) if raw_snapshot is not None else None
    started = time.monotonic()
    store = client()
    candidate = None
    published = False
    try:
        candidate = store.create_collection(staged_name, metadata={
            "hnsw:space": "cosine", "corpus_sha256": corpus_hash, "embed_model": model["model"],
            "chunk_budget": EMBED_TOKENS,
        })
        embed_batches(candidate, chunks, model["dim"])
        verify_index(candidate, chunks)
        vector = embed_query(probe)
        if len(vector) != model["dim"] or not all(map(isfinite, vector)) or not any(vector):
            raise RuntimeError("Embedding endpoint returned an invalid query vector.")
        result = candidate.query(query_embeddings=[vector], n_results=min(5, len(chunks)), include=["metadatas"])
        dense_results = result["metadatas"][0]
        if not dense_results or not all(item.get("doc_url") for item in dense_results):
            raise RuntimeError("Dense retrieval smoke test returned no citations.")
        if (CHUNKS.read_bytes() if CHUNKS.exists() else None) != old_chunks or SOURCE_MANIFEST.read_bytes() != initial_sources:
            raise RuntimeError("The source manifest or processed corpus changed during the rebuild.")
        backup = publish(store, candidate, name, backup_name, old_chunks, chunk_file)
        published = True
    finally:
        if chunk_file is not None:
            chunk_file.unlink(missing_ok=True)
        if candidate is not None and not published:
            store.delete_collection(candidate.name)

    # Keep the previous collection available for a rollback.
    report = {
        "built_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "input": str(raw_snapshot) if raw_snapshot is not None else str(CHUNKS),
        "corpus_sha256": corpus_hash,
        "source_manifest_sha256": sha256(initial_sources).hexdigest(),
        "documents": max_docs,
        "chunks": len(chunks),
        "chunk_budget": EMBED_TOKENS,
        "max_tokens": maximum,
        "bm25_chunks_verified": bm25.bm25.corpus_size,
        "dense_chunks_verified": len(chunks),
        "dense_collection": name,
        "previous_dense_collection": backup,
        "embedding": model,
        "elapsed_ms": round((time.monotonic() - started) * 1000),
        "smoke_query": probe,
        "bm25_source_urls": [chunk["doc_url"] for chunk, _ in bm25_hits],
        "dense_source_urls": [item["doc_url"] for item in dense_results],
    }
    if report_path is not None:
        staged_report = stage_file(report_path, (json.dumps(report, indent=2) + "\n").encode())
        try:
            staged_report.replace(report_path)
        finally:
            staged_report.unlink(missing_ok=True)
    print(f"Verified BM25 and dense indexes for {max_docs} documents and {len(chunks)} chunks "
          f"at {EMBED_TOKENS} tokens. Dense dimension: {model['dim']}.", flush=True)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-snapshot", type=Path, help="Optional complete dated raw snapshot directory.")
    parser.add_argument("--report", type=Path, help="Optional JSON verification report.")
    args = parser.parse_args(argv)
    if args.report and args.report.resolve() in (CHUNKS.resolve(), SOURCE_MANIFEST.resolve()):
        parser.error("The report must use a path separate from the corpus files.")
    with rebuild_lock():
        rebuild(args.raw_snapshot, args.report)


if __name__ == "__main__":
    main()
