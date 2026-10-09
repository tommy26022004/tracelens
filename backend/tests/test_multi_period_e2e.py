"""End-to-end multi-account aggregation and package validation tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.agent.nodes import extract_node, parse_node, ratios_node, validate_node
from app.ingestion.chunker import Chunk
from app.ingestion.store import VectorStore
from scripts.generate_realistic_packages import generate_realistic_package


class InMemoryVectorStore(VectorStore):
    def __init__(self) -> None:
        self.chunks: list[Chunk] = []

    def upsert_chunks(self, chunks: list[Chunk]) -> int:  # type: ignore[override]
        self.chunks.extend(chunks)
        return len(chunks)


@pytest.fixture(scope="module")
def package_paths(tmp_path_factory: pytest.TempPathFactory) -> list[str]:
    package_dir = tmp_path_factory.mktemp("multi_period_package")
    generate_realistic_package(package_dir)
    return [str(path) for path in sorted(package_dir.rglob("*.pdf"))]


def _run_to_ratios(paths: list[str]) -> dict:
    inputs = {
        "application_id": "multi-period",
        "pdf_paths": paths,
        "trace": [],
        "errors": [],
    }
    parsed = parse_node(inputs)  # type: ignore[arg-type]
    extracted = extract_node({**inputs, **parsed}, store=InMemoryVectorStore())  # type: ignore[arg-type]
    state = {**inputs, **parsed, **extracted}
    validated = validate_node(state)  # type: ignore[arg-type]
    state.update(validated)
    state.update(ratios_node(state))  # type: ignore[arg-type]
    return state


def test_multi_account_cash_flow_and_year_matching(package_paths: list[str]) -> None:
    state = _run_to_ratios(package_paths)
    codes = {finding["code"] for finding in state["inconsistencies"]}
    cash_flow = state["ratios"]["package_cash_flow"]
    trend = state["ratios"]["financial_trend"]

    assert "DECLARED_INCOME_VS_DEPOSITS" not in codes
    assert not codes.intersection(
        {"MISSING_BANK_MONTHS", "DUPLICATE_DOCUMENT", "AUDITED_ACCOUNTING_EQUATION"}
    )
    assert cash_flow["account_count"] == 2
    assert cash_flow["statement_count"] == 18
    assert Decimal(str(cash_flow["annualised_credits_by_year"]["2025"])) == Decimal(
        "1800000.00"
    )
    assert trend["years"] == [2022, 2023, 2024, 2025]


def test_missing_month_is_reported_without_aborting(package_paths: list[str]) -> None:
    paths = [path for path in package_paths if not path.endswith("statement_2025_01.pdf")]
    state = _run_to_ratios(paths)
    codes = {finding["code"] for finding in state["inconsistencies"]}

    assert "MISSING_BANK_MONTHS" in codes
    assert state["package_inventory"]["failed_documents"] == 0
    assert state["ratios"]["package_cash_flow"]["covered_months"]


def test_duplicate_upload_is_flagged_and_not_double_counted(package_paths: list[str]) -> None:
    duplicate_path = next(path for path in package_paths if path.endswith("statement_2025_07.pdf"))
    state = _run_to_ratios([*package_paths, duplicate_path])
    codes = {finding["code"] for finding in state["inconsistencies"]}
    cash_flow = state["ratios"]["package_cash_flow"]

    assert "DUPLICATE_DOCUMENT" in codes
    assert cash_flow["statement_count"] == 18
    assert Decimal(str(cash_flow["annualised_credits_by_year"]["2025"])) == Decimal(
        "1800000.00"
    )
