import subprocess
import sys
from pathlib import Path

from copilot.file_lock import try_lock, unlock

CHILD = """
import sys
from copilot.file_lock import try_lock
f = open(sys.argv[1], 'a')
try:
    try_lock(f)
    print('GOT')
except BlockingIOError:
    print('BLOCKED')
"""


def probe(path):
    root = Path(__file__).resolve().parents[1]
    return subprocess.run([sys.executable, "-c", CHILD, str(path)], capture_output=True, text=True, cwd=root,
                          env={**__import__("os").environ, "PYTHONPATH": str(root)}).stdout.strip()


def test_second_process_is_blocked_until_release(tmp_path):
    lock = tmp_path / "x.lock"
    with lock.open("a") as first:
        try_lock(first)
        assert probe(lock) == "BLOCKED"
        unlock(first)
    assert probe(lock) == "GOT"
