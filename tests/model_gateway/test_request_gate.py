"""A shared key queues locally without blocking unrelated keys."""
import subprocess
import sys
from uuid import uuid4

import pytest

from copilot.model_gateway.request_gate import request_gate


def test_another_process_cannot_use_a_busy_key():
    key = 'test-' + uuid4().hex
    program = '''from copilot.model_gateway.request_gate import request_gate
import sys
try:
 with request_gate('https://example.test/v1',sys.argv[1],timeout=0):pass
except TimeoutError:raise SystemExit(0)
raise SystemExit(1)
'''
    with request_gate('https://example.test/v1',key,timeout=1):
        result = subprocess.run([sys.executable,'-c',program,key],check=False)
    assert result.returncode == 0


def test_other_keys_do_not_wait_for_an_unrelated_request():
    with request_gate('https://example.test/v1','test-key-one',timeout=1):
        with request_gate('https://example.test/v1','test-key-two',timeout=0):
            pass


def test_failure_releases_the_model_slot():
    key = 'test-' + uuid4().hex
    with pytest.raises(ValueError):
        with request_gate('https://example.test/v1',key,timeout=0):
            raise ValueError('failed request')
    with request_gate('https://example.test/v1/',key,timeout=0):
        pass
