"""Install the pinned official Qwen3 tokenizer assets for local admission checks."""
import argparse
import hashlib
import os
from pathlib import Path
import tempfile
from urllib.request import urlopen

ASSETS = {
    "tokenizer.json": "aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4",
    "tokenizer_config.json": "d5d09f07b48c3086c508b30d1c9114bd1189145b74e982a265350c923acd8101",
}


def prepare(folder):
    folder.mkdir(parents=True, exist_ok=True)
    # Verify both files before replacing either installed asset.
    with tempfile.TemporaryDirectory(prefix="qwen-tokenizer-") as temporary:
        staged = Path(temporary)
        for name, expected in ASSETS.items():
            target = folder / name
            if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
                data = target.read_bytes()
            else:
                url = f"https://huggingface.co/Qwen/Qwen3-8B/resolve/main/{name}"
                with urlopen(url, timeout=60) as response:
                    data = response.read()
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError(f"Unexpected checksum for {name}; installed files were not changed")
            (staged / name).write_bytes(data)
        for name in ASSETS:
            temporary_target = folder / f".{name}.tmp"
            temporary_target.write_bytes((staged / name).read_bytes())
            temporary_target.replace(folder / name)
    print(f"Verified tokenizer assets: {folder}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path(os.environ.get(
        "TRACKB_TOKENIZER_DIR", Path(__file__).parent / "assets/qwen3-8b")))
    prepare(parser.parse_args().directory)
