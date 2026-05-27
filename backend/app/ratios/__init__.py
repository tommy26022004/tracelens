"""Financial ratio calculation (Step 4 of agent workflow).

Bank-statement-derivable metrics live here. DSR / D-E / Current Ratio /
NPM / ICR require audited financials and join later when that ingestion
path lands.
"""

from app.ratios.bank_statement_metrics import (
    BankStatementMetrics,
    compute_metrics,
)

__all__ = ["BankStatementMetrics", "compute_metrics"]
