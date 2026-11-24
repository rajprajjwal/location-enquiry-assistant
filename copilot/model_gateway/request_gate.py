"""Serialize local processes sharing an institute API key."""
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
import fcntl
import os
import tempfile
import time


@contextmanager
def request_gate(base_url, api_key, *, timeout):
    """Wait within the enquiry deadline; the OS releases abandoned locks."""
    directory = Path(tempfile.gettempdir()) / 'location-enquiry-model-locks'
    directory.mkdir(mode=0o700, exist_ok=True)
    identity = sha256(f'{base_url.rstrip("/")}\0{api_key}'.encode()).hexdigest()
    descriptor = os.open(directory / f'{identity}.lock', os.O_CREAT | os.O_RDWR, 0o600)
    deadline = time.monotonic() + timeout
    acquired = False
    try:
        while not acquired:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except BlockingIOError:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('Enquiry deadline reached waiting for the shared model key.') from None
                time.sleep(min(0.05, remaining))
        yield
    finally:
        if acquired:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)
