"""Install the test-only validation fake, unless the real package is on the path.

Set ``INTERPRET_VALIDATION=real`` and ``INTERPRET_REAL_ROOT`` to the validation
worktree when comparing against ``copilot.validation`` from that branch.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if os.environ.get("INTERPRET_VALIDATION") == "real":
    real_root = os.environ["INTERPRET_REAL_ROOT"]
    sys.path.insert(0, real_root)
else:
    from copilot.interpret import seam
    from tests.support.fake_contract import install

    install(seam)
