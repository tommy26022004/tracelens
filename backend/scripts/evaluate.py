"""Unified evaluation runner for the FYP system.

Runs the four proposal-mandated metrics end-to-end against synthetic
ground truth and prints a human-readable report. Intended to be run
just before submission to populate the evaluation section of the FYP
final report.

Usage:
    python -m scripts.evaluate                  # default 3 latency runs
    python -m scripts.evaluate --runs 5         # more latency samples
    python -m scripts.evaluate --json out.json  # also dump machine-readable

Requires:
- Qdrant running (docker compose up -d qdrant)
- GEMINI_API_KEY in backend/.env (otherwise stub embeddings + LLM are
  used — see fakes; faithfulness then degrades to a tautology)
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.agent.graph import compile_graph
from app.evaluation.extraction_accuracy import (
    score_audited_financials,
    score_bank_statement,
    score_ssm_registration,
    score_tax_return,
)
from app.evaluation.faithfulness import score_faithfulness
from app.evaluation.latency import time_graph_run
from app.explainability.summary import RiskSummary
from app.ingestion.financials_extractor import extract_audited_financials
from app.ingestion.financials_synthetic import FinancialsGeneratorConfig
from app.ingestion.financials_synthetic import generate as generate_financials
from app.ingestion.parser import parse_pdf
from app.ingestion.ssm_extractor import extract_ssm_registration
from app.ingestion.ssm_synthetic import SSMGeneratorConfig
from app.ingestion.ssm_synthetic import generate as generate_ssm
from app.ingestion.store import COLLECTION_NAME, VectorStore
from app.ingestion.synthetic import GeneratorConfig
from app.ingestion.synthetic import generate as generate_bank
from app.ingestion.tax_extractor import extract_tax_return
from app.ingestion.tax_synthetic import TaxReturnGeneratorConfig
from app.ingestion.tax_synthetic import generate as generate_tax
from app.ingestion.types import (
    AuditedFinancials,
    BankStatement,
    SSMRegistration,
    TaxReturn,
)
from app.ingestion.extractor import extract_bank_statement


def _reset_qdrant() -> None:
    store = VectorStore()
    if store._client.collection_exists(COLLECTION_NAME):  # noqa: SLF001
        store._client.delete_collection(COLLECTION_NAME)  # noqa: SLF001


def _build_samples(out_dir: Path) -> dict[str, tuple[Path, Path]]:
    """Generate one PDF + ground truth per document kind."""
    bank_pdf, bank_gt = generate_bank(GeneratorConfig(seed=21, n_transactions=14), out_dir)
    ssm_pdf, ssm_gt = generate_ssm(SSMGeneratorConfig(seed=21), out_dir)
    fin_pdf, fin_gt = generate_financials(FinancialsGeneratorConfig(seed=21), out_dir)
    tax_pdf, tax_gt = generate_tax(TaxReturnGeneratorConfig(), out_dir)
    return {
        "bank_statement": (bank_pdf, bank_gt),
        "ssm_registration": (ssm_pdf, ssm_gt),
        "audited_financials": (fin_pdf, fin_gt),
        "tax_return": (tax_pdf, tax_gt),
    }


def _run_extraction_accuracy(samples: dict[str, tuple[Path, Path]]) -> dict[str, Any]:
    reports: dict[str, Any] = {}

    bank_pdf, bank_gt = samples["bank_statement"]
    expected_bank = BankStatement.model_validate_json(bank_gt.read_text())
    actual_bank = extract_bank_statement(parse_pdf(bank_pdf))
    reports["bank_statement"] = score_bank_statement(expected_bank, actual_bank)

    ssm_pdf, ssm_gt = samples["ssm_registration"]
    expected_ssm = SSMRegistration.model_validate_json(ssm_gt.read_text())
    actual_ssm = extract_ssm_registration(parse_pdf(ssm_pdf))
    reports["ssm_registration"] = score_ssm_registration(expected_ssm, actual_ssm)

    fin_pdf, fin_gt = samples["audited_financials"]
    expected_fin = AuditedFinancials.model_validate_json(fin_gt.read_text())
    actual_fin = extract_audited_financials(parse_pdf(fin_pdf))
    reports["audited_financials"] = score_audited_financials(expected_fin, actual_fin)

    tax_pdf, tax_gt = samples["tax_return"]
    expected_tax = TaxReturn.model_validate_json(tax_gt.read_text())
    actual_tax = extract_tax_return(parse_pdf(tax_pdf))
    reports["tax_return"] = score_tax_return(expected_tax, actual_tax)
    return reports


def _gather_allowed_chunk_ids(state: dict[str, Any]) -> list[str]:
    allowed: list[str] = []
    for stmt, doc_id in zip(
        state.get("statements", []),
        [d for d, k in state.get("document_kinds", {}).items() if k.value == "bank_statement"],
        strict=False,
    ):
        allowed.append(f"{doc_id}:summary:0")
        allowed.extend(f"{doc_id}:transaction:{i}" for i in range(len(stmt.transactions)))
    for ssm, doc_id in zip(
        state.get("ssm_registrations", []),
        [d for d, k in state.get("document_kinds", {}).items() if k.value == "ssm_registration"],
        strict=False,
    ):
        allowed.append(f"{doc_id}:summary:0")
        allowed.extend(f"{doc_id}:director:{i}" for i in range(len(ssm.directors)))
    for fin, doc_id in zip(
        state.get("audited_financials", []),
        [d for d, k in state.get("document_kinds", {}).items() if k.value == "audited_financials"],
        strict=False,
    ):
        allowed.append(f"{doc_id}:summary:0")
        allowed.extend(f"{doc_id}:period:{i}" for i in range(len(fin.periods)))
    for _tax, doc_id in zip(
        state.get("tax_returns", []),
        [d for d, k in state.get("document_kinds", {}).items() if k.value == "tax_return"],
        strict=False,
    ):
        allowed.append(f"{doc_id}:summary:0")
    return allowed


def _run_full_pipeline_and_score(samples: dict[str, tuple[Path, Path]]) -> dict[str, Any]:
    """Drive the full graph once and score faithfulness + per-step latency."""
    pdf_paths = [str(p) for (p, _) in samples.values()]
    graph = compile_graph()
    state = graph.invoke(
        {
            "application_id": "eval-full",
            "pdf_paths": pdf_paths,
            "trace": [],
            "errors": [],
        },
        config={"configurable": {"thread_id": "eval-faithfulness"}},
    )

    summary_payload = state.get("risk_summary")
    faithfulness = None
    if summary_payload:
        summary = RiskSummary.model_validate_json(summary_payload)
        allowed = _gather_allowed_chunk_ids(state)
        faithfulness = score_faithfulness(summary, allowed)

    trace = state.get("trace", [])
    per_node_ms = {
        s.node: (s.finished_at - s.started_at).total_seconds() * 1000 for s in trace
    }
    return {
        "state_summary": {
            "document_count": len(state.get("document_ids", [])),
            "inconsistency_count": len(state.get("inconsistencies", [])),
            "error_count": len(state.get("errors", [])),
        },
        "faithfulness": faithfulness,
        "per_node_ms": per_node_ms,
        "trace_total_ms": sum(per_node_ms.values()),
    }


def _print_report(report: dict[str, Any]) -> None:
    print("=" * 70)
    print("FYP EVALUATION REPORT")
    print(f"Generated: {report['generated_at']}")
    print("=" * 70)

    print("\n[1] EXTRACTION ACCURACY")
    print("-" * 70)
    accuracies = []
    for kind, r in report["extraction_accuracy"].items():
        accuracies.append(r.accuracy)
        print(
            f"  {kind:24} {r.fields_matched:4}/{r.fields_total:<4} fields "
            f"({r.accuracy*100:6.2f}%) "
            + ("PASS (>90%)" if r.accuracy >= 0.9 else "FAIL")
        )
        for mm in r.mismatches[:3]:
            print(f"      mismatch: {mm.field} expected={mm.expected!r} actual={mm.actual!r}")
    overall = sum(accuracies) / len(accuracies) if accuracies else 0.0
    print(f"  {'overall avg':24} {overall*100:6.2f}%")

    print("\n[2] CITATION FAITHFULNESS")
    print("-" * 70)
    faith = report["pipeline_run"].get("faithfulness")
    if faith is None:
        print("  No summary produced — skipped.")
    else:
        print(f"  Citations valid:        {faith.citations_valid}/{faith.citations_total} "
              f"({faith.faithfulness*100:.1f}%)")
        if faith.invalid_citations:
            print(f"  Invalid (hallucinated): {faith.invalid_citations}")
        print(f"  Sentence coverage:      {faith.sentence_citation_coverage*100:.1f}%")
        print(
            "  "
            + ("PASS (0 hallucinations)" if not faith.invalid_citations else "FAIL")
        )

    print("\n[3] LATENCY")
    print("-" * 70)
    lat = report["latency"]
    print(f"  End-to-end p50:  {lat.total_ms_p50/1000:6.2f}s")
    print(f"  End-to-end p95:  {lat.total_ms_p95/1000:6.2f}s")
    print(f"  Per-node p50:")
    for node, ms in lat.per_node_ms_p50.items():
        print(f"    {node:10} {ms/1000:6.2f}s")
    print(
        "  "
        + ("PASS (<180s)" if lat.total_ms_p95 < 180_000 else "FAIL")
    )

    print("\n[4] USABILITY (SUS)")
    print("-" * 70)
    print("  Run the SUS questionnaire with at least 5 loan-officer participants.")
    print("  Score each response with `app.evaluation.sus.score_sus_responses`.")
    print("  Target: mean SUS score > 70 ('Good').")
    print("=" * 70)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run FYP evaluation harness")
    parser.add_argument(
        "--runs", type=int, default=3, help="Number of latency runs (default 3)"
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="Also write the machine-readable report to this path",
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        _reset_qdrant()
        samples = _build_samples(out)
        extraction = _run_extraction_accuracy(samples)
        pipeline = _run_full_pipeline_and_score(samples)
        graph = compile_graph()
        latency = time_graph_run(
            graph,
            [str(p) for (p, _) in samples.values()],
            runs=args.runs,
        )

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "extraction_accuracy": extraction,
            "pipeline_run": pipeline,
            "latency": latency,
        }

    _print_report(report)

    if args.json:
        # Pydantic models inside need explicit serialisation.
        json_payload = {
            "generated_at": report["generated_at"],
            "extraction_accuracy": {
                k: v.model_dump(mode="json") for k, v in extraction.items()
            },
            "pipeline_run": {
                "state_summary": pipeline["state_summary"],
                "faithfulness": pipeline["faithfulness"].model_dump(mode="json")
                if pipeline["faithfulness"]
                else None,
                "per_node_ms": pipeline["per_node_ms"],
                "trace_total_ms": pipeline["trace_total_ms"],
            },
            "latency": latency.model_dump(mode="json"),
        }
        args.json.write_text(json.dumps(json_payload, indent=2, default=str))
        print(f"\nMachine-readable report written to: {args.json}")

    # Exit 0 only if all hard thresholds pass.
    accuracies = [r.accuracy for r in extraction.values()]
    overall_acc = statistics.mean(accuracies) if accuracies else 0.0
    faith = pipeline.get("faithfulness")
    faithfulness_ok = faith is None or not faith.invalid_citations
    latency_ok = latency.total_ms_p95 < 180_000
    accuracy_ok = overall_acc >= 0.9
    return 0 if (faithfulness_ok and latency_ok and accuracy_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
