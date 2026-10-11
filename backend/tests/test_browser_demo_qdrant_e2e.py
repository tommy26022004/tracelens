"""Browser fixture → PDF parser → full graph → live Qdrant integration."""

from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path

import pytest

from app.ingestion.store import VectorStore
from tests.test_agent_full_graph import FakeLLM, _compile

pytestmark = pytest.mark.skipif(
    os.environ.get("FYP_RUN_INTEGRATION") != "1",
    reason="Integration test — set FYP_RUN_INTEGRATION=1 with Qdrant running",
)


def test_browser_demo_runs_full_graph_against_real_qdrant(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[2]
    frontend = repository / "frontend"
    package_dir = tmp_path / "browser-demo"
    subprocess.run(
        ["node", "scripts/export-demo-package.mjs", str(package_dir)],
        cwd=frontend,
        check=True,
    )
    pdf_paths = sorted(package_dir.glob("*.pdf"))
    assert [path.name for path in pdf_paths] == [
        "demo_audited_financials.pdf",
        "demo_bank_statement.pdf",
        "demo_ssm_registration.pdf",
        "demo_tax_return.pdf",
    ]

    application_id = f"browser-e2e-{uuid.uuid4()}"
    store = VectorStore()
    graph = _compile(store, FakeLLM())
    try:
        result = graph.invoke(
            {
                "application_id": application_id,
                "pdf_paths": [str(path) for path in pdf_paths],
                "original_filenames": {str(path): path.name for path in pdf_paths},
                "trace": [],
                "errors": [],
            }
        )

        assert set(kind.value for kind in result["document_kinds"].values()) == {
            "audited_financials",
            "bank_statement",
            "ssm_registration",
            "tax_return",
        }
        assert result["package_inventory"]["extracted_documents"] == 4
        assert result["package_inventory"]["failed_documents"] == 0
        assert [step.node for step in result["trace"]] == [
            "parse",
            "extract",
            "validate",
            "ratios",
            "assess_5c",
            "summarise",
        ]
        assert result["retrieval"]["status"] == "complete"
        assert result["retrieval"]["evidence"]
        assert not any(issue["code"] == "RUNNING_BALANCE" for issue in result["inconsistencies"])
    finally:
        try:
            if store._client.collection_exists("loan_documents"):
                store.delete_application(application_id)
        except Exception:
            pass
