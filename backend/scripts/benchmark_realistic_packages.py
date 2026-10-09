"""Generate and benchmark three realistic SME workload scenarios offline."""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path
from time import perf_counter

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.nodes import extract_node, parse_node, ratios_node, validate_node  # noqa: E402
from app.ingestion.chunker import Chunk  # noqa: E402
from app.ingestion.multi_year_financials import (  # noqa: E402
    FinancialYearSnapshot,
    MultiYearCoherentFinancials,
    build_default_multi_year_financials,
)
from app.ingestion.package_manifest import (  # noqa: E402
    RealisticPackageManifest,
    default_realistic_package_manifest,
)
from app.ingestion.store import VectorStore  # noqa: E402
from scripts.generate_realistic_packages import generate_realistic_package  # noqa: E402


class BenchmarkVectorStore(VectorStore):
    def __init__(self) -> None:
        self.chunk_count = 0

    def upsert_chunks(self, chunks: list[Chunk]) -> int:  # type: ignore[override]
        self.chunk_count += len(chunks)
        return len(chunks)


def _manifest(package_id: str, title: str, expected: list[str]) -> RealisticPackageManifest:
    base = default_realistic_package_manifest()
    return base.model_copy(
        update={"package_id": package_id, "title": title, "expected_findings": expected}
    )


def _tax_mismatch_profile() -> MultiYearCoherentFinancials:
    profile = build_default_multi_year_financials()
    years = []
    for snapshot in profile.years:
        if snapshot.year == 2025:
            years.append(
                FinancialYearSnapshot(
                    financial_period=snapshot.financial_period,
                    tax_gross_business_income=Decimal("1500000.00"),
                    tax_chargeable_income=snapshot.tax_chargeable_income,
                    tax_payable=snapshot.tax_payable,
                )
            )
        else:
            years.append(snapshot)
    return profile.model_copy(update={"years": years})


def generate_benchmark_packages(output_root: Path) -> list[tuple[Path, list[str]]]:
    scenarios = [
        (
            "realistic_01",
            build_default_multi_year_financials(),
            _manifest("realistic_01", "Healthy complete workload", []),
        ),
        (
            "realistic_02",
            build_default_multi_year_financials(),
            _manifest(
                "realistic_02",
                "Missing month and duplicate document workload",
                ["MISSING_BANK_MONTHS", "DUPLICATE_DOCUMENT"],
            ),
        ),
        (
            "realistic_03",
            _tax_mismatch_profile(),
            _manifest(
                "realistic_03",
                "Tax versus audited revenue mismatch workload",
                ["AUDITED_VS_TAX_REVENUE"],
            ),
        ),
    ]
    generated: list[tuple[Path, list[str]]] = []
    for package_id, profile, manifest in scenarios:
        package_dir = output_root / package_id
        generate_realistic_package(package_dir, profile, manifest)
        paths = [str(path) for path in sorted(package_dir.rglob("*.pdf"))]
        if package_id == "realistic_02":
            paths = [path for path in paths if not path.endswith("statement_2025_01.pdf")]
            duplicate = next(path for path in paths if path.endswith("statement_2025_07.pdf"))
            paths.append(duplicate)
            (package_dir / "UPLOAD_PROTOCOL.json").write_text(
                json.dumps(
                    {
                        "omit": "bank/operating_account/statement_2025_01.pdf",
                        "duplicate": Path(duplicate).relative_to(package_dir).as_posix(),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        generated.append((package_dir, paths))
    return generated


def _score(expected: set[str], actual: set[str]) -> tuple[float, float]:
    true_positive = len(expected & actual)
    precision = true_positive / len(actual) if actual else (1.0 if not expected else 0.0)
    recall = true_positive / len(expected) if expected else (1.0 if not actual else 0.0)
    return precision, recall


def benchmark_package(package_dir: Path, pdf_paths: list[str]) -> dict:
    manifest = RealisticPackageManifest.model_validate_json(
        (package_dir / "package_manifest.json").read_text(encoding="utf-8")
    )
    inputs = {
        "application_id": manifest.package_id,
        "pdf_paths": pdf_paths,
        "trace": [],
        "errors": [],
    }
    started = perf_counter()
    parsed = parse_node(inputs)  # type: ignore[arg-type]
    store = BenchmarkVectorStore()
    extracted = extract_node({**inputs, **parsed}, store=store)  # type: ignore[arg-type]
    state = {**inputs, **parsed, **extracted}
    state.update(validate_node(state))  # type: ignore[arg-type]
    state.update(ratios_node(state))  # type: ignore[arg-type]
    duration = perf_counter() - started
    actual_codes = {finding["code"] for finding in state["inconsistencies"]}
    expected_codes = set(manifest.expected_findings)
    precision, recall = _score(expected_codes, actual_codes)
    inventory = state["package_inventory"]
    return {
        "package_id": manifest.package_id,
        "uploaded_files": len(pdf_paths),
        "processed_pages": inventory["total_pages"],
        "duration_seconds": round(duration, 3),
        "pages_per_second": round(inventory["total_pages"] / duration, 2),
        "extraction_success_rate": round(
            inventory["extracted_documents"] / inventory["total_documents"], 4
        ),
        "chunks_indexed": store.chunk_count,
        "expected_findings": sorted(expected_codes),
        "actual_findings": sorted(actual_codes),
        "finding_precision": round(precision, 4),
        "finding_recall": round(recall, 4),
        "recoverable_errors": len(state["errors"]),
    }


def run_benchmark(output_root: Path) -> list[dict]:
    results = [
        benchmark_package(package_dir, paths)
        for package_dir, paths in generate_benchmark_packages(output_root)
    ]
    (output_root / "benchmark_results.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=REPOSITORY_ROOT / "data" / "realistic_scenarios",
    )
    arguments = parser.parse_args()
    results = run_benchmark(arguments.output)
    print("Package | Files | Pages | Seconds | Pages/s | Extract | Precision | Recall")
    for result in results:
        print(
            f"{result['package_id']} | {result['uploaded_files']} | "
            f"{result['processed_pages']} | {result['duration_seconds']} | "
            f"{result['pages_per_second']} | {result['extraction_success_rate']:.0%} | "
            f"{result['finding_precision']:.0%} | {result['finding_recall']:.0%}"
        )


if __name__ == "__main__":
    main()
