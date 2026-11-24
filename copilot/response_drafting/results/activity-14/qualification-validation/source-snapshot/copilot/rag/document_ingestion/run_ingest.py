# Source history: Deepshikha (ebb39df), deepshikha/lbs-copilot. See copilot/enquiry_workflow/source-history.json.
"""Parse + chunk the latest raw snapshot -> data/processed/chunks.jsonl."""
from copilot.paths import CONFIG_DIR, RAG_ROOT
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

from .chunk import chunk_document
from .fetch import slug
from .parse_html import parse_html
from .parse_openapi import parse_openapi
from .parse_stackoverflow import parse_stackoverflow

ROOT = RAG_ROOT


def parse_source(s: dict, text: str):
    """Parse one fetched source -> (title, sections, effective_date). Shared by the full ingest and the freshness tooling."""
    if s["kind"] == "stackoverflow":
        title, sections, extra = parse_stackoverflow(json.loads(text))
        return title, sections, extra["effective_date"]
    if s["kind"] == "openapi":
        title, sections = parse_openapi(text)
        return title, sections, None
    title, sections = parse_html(text)
    return title, sections, None


def collect_chunks(rawdir: Path, sources: list[dict]) -> tuple[list[dict], list[tuple[str, str]]]:
    """Parse a dated snapshot without writing any live retrieval files."""
    fetched = {}
    for line in (rawdir / "manifest.jsonl").read_text(encoding="utf-8-sig").splitlines():
        m = json.loads(line)
        if m["status"] == "ok":
            fetched[m["url"]] = m["fetched_at"]

    all_chunks, problems = [], []
    for s in sources:
        url = s["url"]
        ext = {"stackoverflow": "json", "openapi": "yaml"}.get(s["kind"], "html")
        path = rawdir / f"{slug(url)}.{ext}"
        if not path.exists() or not fetched.get(url):
            problems.append((url, "missing successful raw snapshot"))
            continue
        meta = {**s, "fetched_at": fetched[url], "effective_date": None}
        try:
            title, sections, meta["effective_date"] = parse_source(s, path.read_text(encoding="utf-8"))
            ch = chunk_document(meta, title or url, sections)
        except Exception as e:  # noqa: BLE001
            problems.append((url, f"{type(e).__name__}: {e}"))
            continue
        if not ch:
            problems.append((url, "0 chunks"))
            continue
        all_chunks.extend(ch)
    return all_chunks, problems


def main(day: str | None = None) -> None:
    raw_root = ROOT / "data" / "raw"
    day = day or sorted(p.name for p in raw_root.iterdir() if p.is_dir())[-1]
    sources = yaml.safe_load((CONFIG_DIR / "sources.yaml").read_text(encoding="utf-8"))["sources"]
    all_chunks, problems = collect_chunks(raw_root / day, sources)
    if problems:
        for url, reason in problems:
            print("PROBLEM", url, reason)
        sys.exit(1)

    out = ROOT / "data" / "processed"
    out.mkdir(parents=True, exist_ok=True)
    with (out / "chunks.jsonl").open("w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    by_kind = Counter(c["kind"] for c in all_chunks)
    toks = [c["n_tokens"] for c in all_chunks]
    documents = len({chunk["doc_url"] for chunk in all_chunks})
    print(f"{len(all_chunks)} chunks from {documents}/{len(sources)} docs  {dict(by_kind)}")
    print(f"tokens/chunk: min {min(toks)} median {sorted(toks)[len(toks)//2]} max {max(toks)}")


if __name__ == "__main__":
    main()
