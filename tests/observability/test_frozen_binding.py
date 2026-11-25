"""Reject changed cases and accidental holdout inputs before live acceptance."""
from copy import deepcopy

import pytest

from copilot.observability.verification.prepare_frozen import canonical_rows, validate


def test_exact_frozen_membership_and_content():
    rows = canonical_rows()
    validate(rows)
    assert len(rows) == 80
    changed = deepcopy(rows)
    changed[0]["input"]["query"] += " changed"
    with pytest.raises(ValueError, match="exactly"):
        validate(changed)
    with pytest.raises(ValueError, match="exactly"):
        validate(rows[:-1])
    changed = deepcopy(rows)
    changed[0]["split"] = "holdout"
    with pytest.raises(ValueError, match="exactly"):
        validate(changed)
