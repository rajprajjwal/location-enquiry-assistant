"""Paths shared by the application and its local stores."""

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent
CONFIG_DIR = PACKAGE_ROOT / "config"
RAG_ROOT = PACKAGE_ROOT / "rag"
RAG_DATA_DIR = RAG_ROOT / "data"
CASE_DATA_DIR = PACKAGE_ROOT / "case_storage" / "data"
