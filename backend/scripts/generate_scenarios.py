"""Generate ten coherent synthetic SME loan-application packages.

Run from the repository root:
    python backend/scripts/generate_scenarios.py
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pymupdf

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ingestion.coherent_financials import CoherentFinancials  # noqa: E402
from app.ingestion.financials_synthetic import (  # noqa: E402
    FinancialsGeneratorConfig,
)
from app.ingestion.financials_synthetic import (  # noqa: E402
    generate as generate_financials,
)
from app.ingestion.ssm_synthetic import (  # noqa: E402
    SSMGeneratorConfig,
)
from app.ingestion.ssm_synthetic import (  # noqa: E402
    generate as generate_ssm,
)
from app.ingestion.synthetic import GeneratorConfig  # noqa: E402
from app.ingestion.synthetic import generate as generate_bank  # noqa: E402
from app.ingestion.tax_synthetic import (  # noqa: E402
    TaxReturnGeneratorConfig,
)
from app.ingestion.tax_synthetic import (  # noqa: E402
    generate as generate_tax,
)


def _profile(
    scenario_id: int,
    title: str,
    expected_codes: list[str],
    expected_risk: str,
    **changes: object,
) -> tuple[CoherentFinancials, dict[str, Any]]:
    base = CoherentFinancials(scenario_id=scenario_id)
    profile = base.with_changes(**changes)
    metadata = {
        "scenario_id": scenario_id,
        "title": title,
        "expected_inconsistency_codes": expected_codes,
        "expected_risk_profile": expected_risk,
    }
    return profile, metadata


def build_scenarios() -> list[tuple[CoherentFinancials, dict[str, Any]]]:
    return [
        _profile(1, "Healthy SME - baseline", [], "healthy"),
        _profile(
            2,
            "Healthy SME - alternate company",
            [],
            "healthy",
            company_name="BETA INDUSTRIAL SUPPLIES SDN BHD",
            bank_account_holder="BETA INDUSTRIAL SUPPLIES SDN BHD",
            audited_company_name="BETA INDUSTRIAL SUPPLIES SDN BHD",
            tax_company_name="BETA INDUSTRIAL SUPPLIES SDN BHD",
            registration_number="202202009876 (1456789-V)",
            account_number="564433221100",
            tax_reference_number="C 9988776655",
            incorporation_date=date(2022, 6, 10),
        ),
        _profile(
            3,
            "Single inconsistency - bank holder mismatch",
            ["HOLDER_SSM_MISMATCH"],
            "review_required",
            bank_account_holder="BETA MERCHANTS SDN BHD",
        ),
        _profile(
            4,
            "Two inconsistencies - audited identity and bank income",
            ["FINANCIALS_SSM_MISMATCH", "DECLARED_INCOME_VS_DEPOSITS"],
            "review_required",
            audited_company_name="GAMMA TRADING SDN BHD",
            bank_credit_multiplier=Decimal("0.55"),
        ),
        _profile(
            5,
            "Borderline SME - weak liquidity but consistent",
            [],
            "borderline_liquidity",
            trade_receivables=Decimal("90000.00"),
            cash_and_bank=Decimal("45000.00"),
            inventories=Decimal("70000.00"),
            retained_earnings=Decimal("-175000.00"),
        ),
        _profile(
            6,
            "Borderline SME - weak debt service but consistent",
            [],
            "borderline_debt_service",
            finance_costs=Decimal("250000.00"),
            tax_expense=Decimal("0.00"),
            short_term_borrowings=Decimal("300000.00"),
            long_term_borrowings=Decimal("520000.00"),
            retained_earnings=Decimal("-180000.00"),
        ),
        _profile(
            7,
            "Multiple inconsistencies - identity and declarations",
            [
                "HOLDER_SSM_MISMATCH",
                "DECLARED_INCOME_VS_DEPOSITS",
                "AUDITED_VS_TAX_REVENUE",
                "FINANCIALS_SSM_MISMATCH",
            ],
            "high_review_priority",
            bank_account_holder="DELTA SERVICES SDN BHD",
            audited_company_name="OMEGA DISTRIBUTION SDN BHD",
            tax_gross_business_income=Decimal("1200000.00"),
            bank_credit_multiplier=Decimal("1.45"),
        ),
        _profile(
            8,
            "High-risk SME - weak ratios and multiple inconsistencies",
            [
                "HOLDER_SSM_MISMATCH",
                "DECLARED_INCOME_VS_DEPOSITS",
                "AUDITED_VS_TAX_REVENUE",
                "FINANCIALS_SSM_MISMATCH",
            ],
            "high_risk",
            bank_account_holder="UNKNOWN MERCHANT ENTERPRISE",
            audited_company_name="ZETA GLOBAL SDN BHD",
            tax_gross_business_income=Decimal("1200000.00"),
            bank_credit_multiplier=Decimal("0.45"),
            trade_receivables=Decimal("70000.00"),
            cash_and_bank=Decimal("25000.00"),
            inventories=Decimal("45000.00"),
            finance_costs=Decimal("270000.00"),
            short_term_borrowings=Decimal("380000.00"),
            long_term_borrowings=Decimal("650000.00"),
            retained_earnings=Decimal("-930000.00"),
            tax_expense=Decimal("0.00"),
        ),
        _profile(
            9,
            "Tax versus audited revenue mismatch",
            ["AUDITED_VS_TAX_REVENUE"],
            "review_required",
            tax_gross_business_income=Decimal("1550000.00"),
            bank_credit_multiplier=Decimal("1.16"),
        ),
        _profile(
            10,
            "Missing supporting data in tax return",
            [],
            "incomplete_documentation",
            missing_fields=("tax.capital_allowance_schedule", "tax.authorized_signatory"),
        ),
    ]


def _json_default(value: object) -> object:
    if isinstance(value, (Decimal, date)):
        return str(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    raise TypeError(f"Cannot serialise {type(value).__name__}")


def _page_count(path: Path) -> int:
    with pymupdf.open(path) as document:
        return document.page_count


def generate_all(output_root: Path) -> list[dict[str, Any]]:
    output_root.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, Any]] = []
    for profile, metadata in build_scenarios():
        scenario_dir = output_root / f"scenario_{profile.scenario_id:02d}"
        scenario_dir.mkdir(parents=True, exist_ok=True)

        bank_pdf, _ = generate_bank(
            GeneratorConfig(
                period_start=profile.statement_start,
                opening_balance=profile.opening_bank_balance,
                account_holder=profile.bank_account_holder,
                account_number=profile.account_number,
                num_months=6,
                n_transactions=28,
            ),
            scenario_dir,
            profile,
        )
        financials_pdf, _ = generate_financials(FinancialsGeneratorConfig(), scenario_dir, profile)
        ssm_pdf, _ = generate_ssm(SSMGeneratorConfig(), scenario_dir, profile)
        tax_pdf, _ = generate_tax(TaxReturnGeneratorConfig(), scenario_dir, profile)

        page_counts = {
            "bank_statement": _page_count(bank_pdf),
            "audited_financials": _page_count(financials_pdf),
            "ssm_registration": _page_count(ssm_pdf),
            "tax_return": _page_count(tax_pdf),
        }
        manifest = {
            **metadata,
            "company_name": profile.company_name,
            "deliberate_missing_fields": list(profile.missing_fields),
            "page_counts": page_counts,
            "total_pages": sum(page_counts.values()),
            "coherent_financials": asdict(profile),
        }
        (scenario_dir / "scenario_manifest.json").write_text(
            json.dumps(manifest, indent=2, default=_json_default),
            encoding="utf-8",
        )
        summaries.append(manifest)
    return summaries


def print_summary(summaries: list[dict[str, Any]]) -> None:
    print("Scenario | BS pages | AF pages | SSM pages | TAX pages | Total")
    print("---------|----------|----------|-----------|-----------|------")
    for summary in summaries:
        counts = summary["page_counts"]
        print(
            f"{summary['scenario_id']:>8} |"
            f" {counts['bank_statement']:>8} |"
            f" {counts['audited_financials']:>8} |"
            f" {counts['ssm_registration']:>9} |"
            f" {counts['tax_return']:>9} |"
            f" {summary['total_pages']:>5}"
        )
    print(f"Total pages across all scenarios: {sum(item['total_pages'] for item in summaries)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=REPOSITORY_ROOT / "data" / "scenarios",
        help="Output directory for generated scenario packages",
    )
    arguments = parser.parse_args()
    summaries = generate_all(arguments.output)
    print_summary(summaries)


if __name__ == "__main__":
    main()
