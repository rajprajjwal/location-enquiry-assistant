"""Resolve standard Google driving coverage from the approved country table."""

from functools import lru_cache
import json
from pathlib import Path
import re

_GOOGLE_COVERAGE = "https://developers.google.com/maps/coverage"
_DRIVING_COLUMN = "Driving Directions / Snap to Roads"
_SOURCE_FILE = Path(__file__).resolve().parents[2] / "copilot/config/directions-coverage-sources.json"
_SPECIAL_ROUTING = re.compile(
    r"\b(?:two[- ]wheel\w*|motorcycl\w*|traffic[- ]aware|with live traffic|with traffic|transit|"
    r"walking|cycling|bik(?:e|ing)|pedestrian|trucks?|electric|EV|eco[- ]friendly|tolls?)\b", re.I,
)


def _cells(line):
    return [cell.strip() for cell in line.strip("|").split("|")]


@lru_cache(maxsize=1)
def _google_table():
    from copilot.rag.document_indexing.bm25 import load_chunks

    try:
        chunks = load_chunks()
    except FileNotFoundError:
        return None, {}, {}
    lines = [line.strip() for chunk in chunks if chunk["doc_url"] == _GOOGLE_COVERAGE
             for line in chunk["text"].splitlines() if line.lstrip().startswith("|")]
    header = next((line for line in lines if _DRIVING_COLUMN in line and "Country/Region" in line), None)
    if header is None:
        return None, {}, {}
    columns = _cells(header)
    country_column = columns.index("Country/Region")
    driving_column = columns.index(_DRIVING_COLUMN)
    legends, rows = {}, {}
    for line in lines:
        cells = _cells(line)
        if len(cells) == 2 and cells[0] in {"⬤", "◯", "—"}:
            legends.setdefault(cells[0], line)
        if len(cells) == len(columns) and re.fullmatch(r"[A-Z]{2}", cells[0]):
            rows.setdefault(cells[country_column].casefold(), set()).add((cells[driving_column], line))
    return header, rows, legends


def google_driving_coverage(provider, requirements, original):
    """Pair the exact archived country row with its original column and legend."""
    if (provider != "Google Maps Platform" or requirements["api"] != "directions"
            or re.search(r"\blegacy\b", original, re.I) or _SPECIAL_ROUTING.search(original)):
        return None
    header, rows, legends = _google_table()
    region = requirements["region"].strip()
    matches = rows.get(region.casefold(), ())
    if len(matches) != 1 or not header:
        return None
    (marker, row), = matches
    if marker not in {"⬤", "◯"} or marker not in legends:
        return None
    if not _SOURCE_FILE.is_file():
        return None

    source = json.loads(_SOURCE_FILE.read_text(encoding="utf-8"))["google_routes_regional_availability"]
    quality = "good" if marker == "⬤" else "approximate"
    return {
        "status": "verified",
        "findings": [
            {"url": source["url"], "span": source["span"]},
            {"url": _GOOGLE_COVERAGE, "span": header},
            {"url": _GOOGLE_COVERAGE, "span": row},
            {"url": _GOOGLE_COVERAGE, "span": legends[marker]},
        ],
        "reason": None,
        "summary": f"Google documents standard driving coverage in {region} with {quality} data availability.",
    }
