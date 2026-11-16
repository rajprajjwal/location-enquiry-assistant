"""Interpretation step.

Purpose: export ``interpret`` for the Planner and the batch runner.
Use case: ``from copilot.interpret import interpret``.
Example: ``interpret({"query": "directions pricing in India"})``.
"""

from .interpret import interpret

__all__ = ["interpret"]
