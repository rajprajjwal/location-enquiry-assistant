"""Audit source metadata and document similarity for Activity 7."""
from copilot.paths import CONFIG_DIR, RAG_ROOT
import argparse
from collections import defaultdict
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import re

from datasketch import MinHash
import numpy as np
import yaml

ROOT = RAG_ROOT
CHUNKS = ROOT / "data" / "processed" / "chunks.jsonl"
SOURCES = CONFIG_DIR / "sources.yaml"
HIGH_SIMILARITY = 0.82
SCREENING_THRESHOLD = 0.62
NUM_PERMUTATIONS = 64
SEED = 50082


def shingles(text: str) -> set[tuple[str, ...]]:
    words = re.findall(r"\w+", text.casefold())
    return {tuple(words[i:i + 5]) for i in range(len(words) - 4)}


def find_duplicates(documents: dict[str, str]) -> tuple[list[dict], int, int]:
    urls = list(documents)
    grams = [shingles(documents[url]) for url in urls]
    sketches = []
    for items in grams:
        sketch = MinHash(num_perm=NUM_PERMUTATIONS, seed=SEED)
        sketch.update_batch(" ".join(gram).encode() for gram in items)
        sketches.append(sketch.hashvalues)
    fingerprints = np.stack(sketches)
    parent = list(range(len(urls)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    candidates = 0
    matches = []
    for i, left in enumerate(grams):
        estimates = (fingerprints[i+1:] == fingerprints[i]).mean(axis=1)
        for j in range(i+1, len(grams)):
            right = grams[j]
            if not left or not right:
                continue
            estimate = float(estimates[j-i-1])
            candidates += estimate >= SCREENING_THRESHOLD
            # Compare every pair whose set sizes allow it to reach the exact threshold.
            if min(len(left), len(right)) / max(len(left), len(right)) < HIGH_SIMILARITY:
                continue
            intersection = len(left & right)
            exact = intersection / (len(left) + len(right) - intersection)
            if exact >= HIGH_SIMILARITY:
                matches.append({"first_url": urls[i], "second_url": urls[j], "jaccard": round(exact,5),
                                "estimated_minhash_jaccard": round(estimate,5)})
                parent[root(j)] = root(i)
    return matches, candidates, len({root(i) for i in range(len(urls))})


def audit_corpus(chunks_path: Path = CHUNKS, sources_path: Path = SOURCES) -> dict:
    blob = chunks_path.read_bytes()
    source_data = sources_path.read_bytes()
    sources = yaml.safe_load(source_data)["sources"]
    manifest = {entry["url"]: entry for entry in sources}
    grouped = defaultdict(list)
    empty_meta = 0
    for line in blob.splitlines():
        if not line.strip():
            continue
        chunk = json.loads(line)
        grouped[chunk["doc_url"]].append(chunk["text"].partition("\n\n")[2])
        if not all(chunk.get(key) for key in ("doc_url", "kind", "licence", "fetched_at")):
            empty_meta += 1
    if not sources or len(manifest) != len(sources) or set(grouped) != manifest.keys():
        raise ValueError("Expected one source entry per document and complete chunk coverage.")
    documents = {url: " ".join(content) for url, content in grouped.items()}
    matches, candidates, distinct = find_duplicates(documents)
    involved = {row[key] for row in matches for key in ("first_url", "second_url")}
    return {
        "documents": len(manifest),
        "chunks_missing_required_source_metadata": empty_meta,
        "non_here_documents": sum(s["provider"] != "HERE" for s in sources),
        "similarity_method": "datasketch MinHash on five-word shingles, with exhaustive size-compatible exact Jaccard verification",
        "minhash_version": version("datasketch"),
        "minhash_permutations": NUM_PERMUTATIONS,
        "minhash_seed": SEED,
        "screening_threshold": SCREENING_THRESHOLD,
        "high_similarity_threshold": HIGH_SIMILARITY,
        "minhash_candidate_pairs": int(candidates),
        "confirmed_near_duplicate_pairs": len(matches),
        "documents_involved_in_near_duplicates": len(involved),
        "document_involvement_rate": len(involved) / len(manifest),
        "extra_documents_in_duplicate_groups": len(manifest) - distinct,
        "effective_distinct_documents": distinct,
        "pairs": matches,
        "corpus_sha256": sha256(blob).hexdigest(),
        "source_manifest_sha256": sha256(source_data).hexdigest(),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks", type=Path, default=CHUNKS)
    parser.add_argument("--sources", type=Path, default=SOURCES)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    if args.report and args.report.resolve() in (args.chunks.resolve(), args.sources.resolve()):
        parser.error("The report path must be separate from the corpus files.")
    result = audit_corpus(args.chunks, args.sources)
    if args.report:
        args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "pairs"}, indent=2))


if __name__ == "__main__":
    main()
