
"""Serialize local processes sharing an institute API key.

Uses portalocker for cross-platform file locking (Windows and Linux).
"""
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
import os
import tempfile
import time

import portalocker


@contextmanager
def request_gate(base_url, api_key, *, timeout):
    """Wait within the enquiry deadline; the OS releases abandoned locks."""

    directory = Path(tempfile.gettempdir()) / "location-enquiry-model-locks"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)

    identity = sha256(
        f'{base_url.rstrip("/")}\0{api_key}'.encode()
    ).hexdigest()

    lock_path = directory / f"{identity}.lock"

    descriptor = os.open(
        lock_path,
        os.O_CREAT | os.O_RDWR,
        0o600,
    )

    lock_file = os.fdopen(descriptor, "r+b", buffering=0)

    deadline = time.monotonic() + timeout
    acquired = False

    try:
        while not acquired:
            try:
                portalocker.lock(
                    lock_file,
                    portalocker.LOCK_EX | portalocker.LOCK_NB,
                )
                acquired = True

            except portalocker.exceptions.AlreadyLocked:
                remaining = deadline - time.monotonic()

                if remaining <= 0:
                    raise TimeoutError(
                        "Enquiry deadline reached waiting for "
                        "the shared model key."
                    ) from None

                time.sleep(min(0.05, remaining))

        yield

    finally:
        try:
            if acquired:
                portalocker.unlock(lock_file)
        finally:
            lock_file.close()
