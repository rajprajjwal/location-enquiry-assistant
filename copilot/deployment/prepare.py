"""Download required model assets into the configured local caches."""
import argparse
import os
from pathlib import Path

from copilot.model_gateway.prepare_tokenizer import prepare


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("bm25", "hybrid"), default="hybrid")
    args = parser.parse_args(argv)
    from copilot.model_gateway import prepare_tokenizer
    prepare(Path(os.environ.get("TRACKB_TOKENIZER_DIR", Path(prepare_tokenizer.__file__).parent / "assets/qwen3-8b")))
    if args.mode == "hybrid":
        from huggingface_hub import snapshot_download
        from transformers import AutoTokenizer
        from copilot.rag.model_assets import (
            CHUNK_TOKENIZER, CHUNK_TOKENIZER_REVISION, RERANK_MODEL, RERANK_REVISION,
        )
        AutoTokenizer.from_pretrained(CHUNK_TOKENIZER, revision=CHUNK_TOKENIZER_REVISION)
        snapshot_download(RERANK_MODEL, revision=RERANK_REVISION, allow_patterns=[
            "config.json", "model.safetensors", "sentencepiece.bpe.model",
            "special_tokens_map.json", "tokenizer.json", "tokenizer_config.json",
        ])
        print("Verified chunk tokenizer and downloaded pinned reranker assets.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
