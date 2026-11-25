"""Setup failures must stop live probes without exposing credentials."""
import json

import pytest

from copilot.deployment.check import verify
from copilot.case_storage import db
from copilot.model_gateway import client, token_counting


@pytest.fixture
def local_setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "cases.db")
    monkeypatch.setattr(token_counting, "count_text", lambda text: 2)
    monkeypatch.setattr(client, "LLMClient", lambda: object())


def test_missing_credentials_block_live_checks_and_hide_error_details(local_setup, monkeypatch):
    def missing():
        raise client.ConfigError("private example credential")
    monkeypatch.setattr(client, "LLMClient", missing)
    result = verify("bm25", live=True)
    assert not result["passed"]
    assert next(r for r in result["checks"] if r["check"] == "chat_configuration")["error_type"] == "ConfigError"
    assert not any(r["check"].startswith("live_") for r in result["checks"])
    assert "private example credential" not in json.dumps(result)


def test_missing_tokenizer_blocks_readiness(local_setup, monkeypatch):
    def missing(text):
        raise ValueError("missing pinned assets")
    monkeypatch.setattr(token_counting, "count_text", missing)
    result = verify("bm25")
    assert not result["passed"]
    assert not next(r for r in result["checks"] if r["check"] == "chat_tokenizer")["passed"]


def test_bm25_setup_does_not_require_dense_index_or_reranker(local_setup):
    result = verify("bm25")
    assert result["passed"]
    names = {r["check"] for r in result["checks"]}
    assert "case_storage" in names and "bm25_corpus" in names
    assert "dense_index" not in names and "reranker_assets" not in names
