"""End-to-end package grouping and completeness test."""

from __future__ import annotations

import pytest

from app.agent.nodes import extract_node, parse_node
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
def inventory_state(tmp_path_factory: pytest.TempPathFactory) -> dict:
    package_dir = tmp_path_factory.mktemp("inventory_package")
    generate_realistic_package(package_dir)
    inputs = {
        "application_id": "realistic-inventory",
        "pdf_paths": [str(path) for path in sorted(package_dir.rglob("*.pdf"))],
        "trace": [],
        "errors": [],
    }
    parsed = parse_node(inputs)  # type: ignore[arg-type]
    extracted = extract_node({**inputs, **parsed}, store=InMemoryVectorStore())  # type: ignore[arg-type]
    return {**inputs, **parsed, **extracted}


def test_realistic_package_groups_all_documents(inventory_state: dict) -> None:
    inventory = inventory_state["package_inventory"]

    assert inventory["total_documents"] == 32
    assert inventory["total_pages"] == 337
    assert inventory["extracted_documents"] == 32
    assert inventory["failed_documents"] == 0
    assert inventory["complete"] is True
    assert inventory["missing_core_kinds"] == []
    assert inventory["missing_bank_months"] == []
    assert inventory["duplicate_document_ids"] == []


def test_inventory_groups_accounts_years_and_supporting_kinds(inventory_state: dict) -> None:
    inventory = inventory_state["package_inventory"]

    assert len(inventory["bank_coverage_by_account"]) == 2
    assert sorted(len(months) for months in inventory["bank_coverage_by_account"].values()) == [
        6,
        12,
    ]
    assert inventory["financial_years"] == [2023, 2024, 2025]
    assert inventory["documents_by_kind"] == {
        "audited_financials": 3,
        "bank_statement": 18,
        "cash_flow_forecast": 1,
        "facility_statement": 2,
        "management_accounts": 4,
        "ssm_registration": 1,
        "tax_return": 3,
    }
    assert not [error for error in inventory_state["errors"] if error.node == "extract"]
