"""Financial ratio calculation (Step 4 of agent workflow).

Bank-statement-derivable metrics live here. DSR / D-E / Current Ratio /
NPM / ICR require audited financials and join later when that ingestion
path lands.
"""

from app.ratios.bank_statement_metrics import (
    BankStatementMetrics,
    compute_metrics,
)
from app.ratios.financial_ratios import (
    FinancialRatios,
    Ratio,
    RatioBand,
    compute_financial_ratios,
)

__all__ = [
    "BankStatementMetrics",
    "FinancialRatios",
    "Ratio",
    "RatioBand",
    "compute_metrics",
    "compute_financial_ratios",
]
