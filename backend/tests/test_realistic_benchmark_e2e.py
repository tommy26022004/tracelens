"""End-to-end acceptance test for the three realistic workload scenarios."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.benchmark_realistic_packages import run_benchmark
from tests.test_agent_full_graph import FakeLLM, FakeVectorStore, _compile


@pytest.fixture(scope="module")
def benchmark_output(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, list[dict]]:
    output = tmp_path_factory.mktemp("realistic_benchmark")
    return output, run_benchmark(output)


def test_three_realistic_workloads_meet_acceptance(
    benchmark_output: tuple[Path, list[dict]],
) -> None:
    _, results = benchmark_output

    assert len(results) == 3
    assert sum(result["processed_pages"] for result in results) >= 1000
    for result in results:
        assert result["uploaded_files"] == 32
        assert result["extraction_success_rate"] == 1.0
        assert result["finding_precision"] == 1.0
        assert result["finding_recall"] == 1.0
        assert result["recoverable_errors"] == 0
        assert result["pages_per_second"] > 0


def test_realistic_package_completes_full_six_node_graph(
    benchmark_output: tuple[Path, list[dict]],
) -> None:
    output, _ = benchmark_output
    package_dir = output / "realistic_01"
    paths = [str(path) for path in sorted(package_dir.rglob("*.pdf"))]
    graph = _compile(FakeVectorStore(), FakeLLM())

    result = graph.invoke(
        {
            "application_id": "realistic-full-graph",
            "pdf_paths": paths,
            "trace": [],
            "errors": [],
        }
    )

    assert [step.node for step in result["trace"]] == [
        "parse",
        "extract",
        "validate",
        "ratios",
        "assess_5c",
        "summarise",
    ]
    assert result["risk_summary"]
    assert result["package_inventory"]["total_documents"] == 32
    assert result["package_inventory"]["total_pages"] == 337


def test_realistic_package_warnings_reach_final_assessment(
    benchmark_output: tuple[Path, list[dict]],
) -> None:
    output, _ = benchmark_output
    paths = [str(path) for path in sorted((output / "realistic_02").rglob("*.pdf"))]
    paths = [path for path in paths if not path.endswith("statement_2025_01.pdf")]
    paths.append(next(path for path in paths if path.endswith("statement_2025_07.pdf")))
    provider = FakeLLM()
    result = _compile(FakeVectorStore(), provider).invoke(
        {"application_id": "realistic-warnings", "pdf_paths": paths, "trace": [], "errors": []}
    )
    assert result["package_inventory"]["total_documents"] == 32
    for prompt, _ in provider.calls:
        assert "DUPLICATE_DOCUMENT" in prompt
        assert "MISSING_BANK_MONTHS" in prompt
        assert "package_cash_flow" in prompt
    summary = json.loads(result["risk_summary"])
    assert "DUPLICATE_DOCUMENT" in summary["body"]
    assert "MISSING_BANK_MONTHS" in summary["body"]
    assert any(
        "MISSING_BANK_MONTHS" in flag
        for flag in result["five_c"]["character"]["flags_for_human_review"]
    )
