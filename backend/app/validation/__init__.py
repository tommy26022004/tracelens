"""Cross-document and intra-document validation (Step 3 of agent workflow).

Deterministic checks live here. The agent's validate node calls
`run_checks(statements)` and gets back a list of `Inconsistency`
records, each citing the chunk(s) that triggered it.
"""

from app.validation.checks import (
    Inconsistency,
    Severity,
    run_checks,
)
from app.validation.cross_doc import run_cross_doc_checks

__all__ = ["Inconsistency", "Severity", "run_checks", "run_cross_doc_checks"]
