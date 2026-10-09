"""Generate a realistic multi-account, multi-year SME loan package."""

from __future__ import annotations

import argparse
import calendar
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pymupdf
from pydantic import BaseModel
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ingestion.coherent_financials import CoherentFinancials, money  # noqa: E402
from app.ingestion.financials_synthetic import (  # noqa: E402
    FinancialsGeneratorConfig,
    build_financials,
)
from app.ingestion.financials_synthetic import (  # noqa: E402
    render_pdf as render_financials,
)
from app.ingestion.multi_year_financials import (  # noqa: E402
    MultiYearCoherentFinancials,
    build_default_multi_year_financials,
)
from app.ingestion.package_manifest import (  # noqa: E402
    GeneratedPackageDocument,
    PackageDocumentKind,
    RealisticPackageManifest,
    default_realistic_package_manifest,
)
from app.ingestion.pdf_layout import (  # noqa: E402
    LEFT,
    draw_page_frame,
    draw_section,
    draw_table,
    draw_title,
)
from app.ingestion.ssm_synthetic import (  # noqa: E402
    SSMGeneratorConfig,
    build_ssm,
)
from app.ingestion.ssm_synthetic import (  # noqa: E402
    render_pdf as render_ssm,
)
from app.ingestion.synthetic import (  # noqa: E402
    GeneratorConfig,
    build_statement,
)
from app.ingestion.synthetic import (  # noqa: E402
    render_pdf as render_bank,
)
from app.ingestion.tax_synthetic import (  # noqa: E402
    TaxReturnGeneratorConfig,
    build_tax_return,
)
from app.ingestion.tax_synthetic import (  # noqa: E402
    render_pdf as render_tax,
)


def _month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def _page_count(path: Path) -> int:
    with pymupdf.open(path) as document:
        return document.page_count


def _coherent_for_year(
    profile: MultiYearCoherentFinancials,
    year: int,
) -> CoherentFinancials:
    snapshot = profile.snapshot(year)
    period = snapshot.financial_period
    base = profile.base_financials
    scale = period.revenue / base.revenue
    return base.with_changes(
        company_name=profile.company_name,
        bank_account_holder=profile.company_name,
        audited_company_name=profile.company_name,
        tax_company_name=profile.company_name,
        registration_number=profile.registration_number,
        tax_reference_number=profile.tax_reference_number,
        financial_year_end=date(year, 12, 31),
        revenue=period.revenue,
        prior_revenue=money(period.revenue / Decimal("1.10")),
        cost_of_sales=money(base.cost_of_sales * scale),
        salaries=money(base.salaries * scale),
        rental_expense=money(base.rental_expense * scale),
        depreciation=money(base.depreciation * scale),
        administrative_expenses=money(base.administrative_expenses * scale),
        finance_costs=money(base.finance_costs * scale),
        tax_expense=money(base.tax_expense * scale),
        ppe=money(base.ppe * scale),
        intangible_assets=money(base.intangible_assets * scale),
        trade_receivables=money(base.trade_receivables * scale),
        cash_and_bank=money(base.cash_and_bank * scale),
        inventories=money(base.inventories * scale),
        trade_payables=money(base.trade_payables * scale),
        short_term_borrowings=money(base.short_term_borrowings * scale),
        tax_payable_balance=money(base.tax_payable_balance * scale),
        long_term_borrowings=money(base.long_term_borrowings * scale),
        paid_up_capital=money(base.paid_up_capital * scale),
        retained_earnings=money(base.retained_earnings * scale),
        cash_from_operations=money(base.cash_from_operations * scale),
        cash_from_investing=money(base.cash_from_investing * scale),
        cash_from_financing=money(base.cash_from_financing * scale),
        tax_gross_business_income=snapshot.tax_gross_business_income,
        tax_chargeable_income=snapshot.tax_chargeable_income,
    )


def _write_ground_truth(path: Path, model: BaseModel) -> None:
    path.with_suffix(".ground_truth.json").write_text(
        model.model_dump_json(indent=2), encoding="utf-8"
    )


def _render_supporting_document(
    output_path: Path,
    company_name: str,
    title: str,
    page_count: int,
    year: int,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(output_path), pagesize=A4)
    for page_number in range(1, page_count + 1):
        draw_page_frame(pdf, company_name, title, page_number, page_count)
        y = draw_title(pdf, title.upper(), f"Reporting year {year}")
        y = draw_section(pdf, f"SECTION {page_number:02d}", y)
        rows = [
            (
                f"Supporting item {index:02d}",
                f"RM {Decimal(150000 + page_number * 5000) / Decimal(index + 1):,.2f}",
                f"Reference {year}-{page_number:02d}-{index:02d}",
            )
            for index in range(1, 14)
        ]
        draw_table(
            pdf,
            ("Description", "Amount", "Reference"),
            rows,
            (230, 115, 147),
            y,
            27,
            ("left", "right", "left"),
            8,
        )
        pdf.setFont("Helvetica", 8)
        pdf.drawString(LEFT, 58, "Synthetic supporting document for workload evaluation.")
        pdf.showPage()
    pdf.save()


def generate_realistic_package(
    output_dir: Path,
    profile: MultiYearCoherentFinancials | None = None,
    manifest: RealisticPackageManifest | None = None,
) -> RealisticPackageManifest:
    profile = profile or build_default_multi_year_financials()
    manifest = manifest or default_realistic_package_manifest()
    output_dir.mkdir(parents=True, exist_ok=True)
    documents: list[GeneratedPackageDocument] = []

    allocations = profile.monthly_credit_targets(2025)
    account_balances = {account.account_id: account.opening_balance for account in profile.accounts}
    for account in profile.accounts:
        for month in account.active_months:
            start = date(2025, month, 1)
            end = _month_end(2025, month)
            target_credits = allocations[(account.account_id, month)]
            synthetic_annual_income = money(
                target_credits * Decimal(365) / Decimal((end - start).days + 1)
            )
            monthly_profile = profile.base_financials.with_changes(
                company_name=profile.company_name,
                bank_account_holder=profile.company_name,
                audited_company_name=profile.company_name,
                tax_company_name=profile.company_name,
                account_number=account.account_number,
                statement_start=start,
                opening_bank_balance=account_balances[account.account_id],
                tax_gross_business_income=synthetic_annual_income,
            )
            config = GeneratorConfig(
                period_start=start,
                opening_balance=account_balances[account.account_id],
                bank_name=account.bank_name,
                account_holder=profile.company_name,
                account_number=account.account_number,
                n_transactions=56,
                num_months=1,
            )
            statement = build_statement(config, monthly_profile)
            account_balances[account.account_id] = statement.closing_balance
            relative_path = Path("bank") / account.account_id / f"statement_2025_{month:02d}.pdf"
            pdf_path = output_dir / relative_path
            render_bank(statement, pdf_path, config)
            _write_ground_truth(pdf_path, statement)
            documents.append(
                GeneratedPackageDocument(
                    relative_path=relative_path.as_posix(),
                    kind=PackageDocumentKind.BANK_STATEMENT,
                    pages=_page_count(pdf_path),
                    account_id=account.account_id,
                    period_start=start,
                    period_end=end,
                )
            )

    for year in manifest.financial_years:
        year_profile = _coherent_for_year(profile, year)
        financials = build_financials(FinancialsGeneratorConfig(), year_profile).model_copy(
            update={"page_count": 40}
        )
        relative_path = Path("audited") / f"audited_financials_{year}.pdf"
        pdf_path = output_dir / relative_path
        render_financials(financials, pdf_path, year_profile, supplemental_pages=33)
        _write_ground_truth(pdf_path, financials)
        documents.append(
            GeneratedPackageDocument(
                relative_path=relative_path.as_posix(),
                kind=PackageDocumentKind.AUDITED_FINANCIALS,
                pages=_page_count(pdf_path),
                financial_year=year,
            )
        )

    ssm_profile = _coherent_for_year(profile, max(manifest.financial_years))
    registration = build_ssm(SSMGeneratorConfig(), ssm_profile).model_copy(
        update={"page_count": 25}
    )
    ssm_relative = Path("ssm") / "ssm_registration.pdf"
    ssm_path = output_dir / ssm_relative
    render_ssm(registration, ssm_path, ssm_profile, supplemental_pages=20)
    _write_ground_truth(ssm_path, registration)
    documents.append(
        GeneratedPackageDocument(
            relative_path=ssm_relative.as_posix(),
            kind=PackageDocumentKind.SSM_REGISTRATION,
            pages=_page_count(ssm_path),
        )
    )

    for year in manifest.financial_years:
        year_profile = _coherent_for_year(profile, year)
        tax = build_tax_return(TaxReturnGeneratorConfig(), year_profile).model_copy(
            update={"page_count": 20}
        )
        relative_path = Path("tax") / f"tax_return_YA{year}.pdf"
        pdf_path = output_dir / relative_path
        render_tax(tax, pdf_path, year_profile, supplemental_pages=15)
        _write_ground_truth(pdf_path, tax)
        documents.append(
            GeneratedPackageDocument(
                relative_path=relative_path.as_posix(),
                kind=PackageDocumentKind.TAX_RETURN,
                pages=_page_count(pdf_path),
                financial_year=year,
            )
        )

    support_specs = [
        (
            PackageDocumentKind.MANAGEMENT_ACCOUNTS,
            4,
            8,
            "management_accounts",
            "Quarterly Management Accounts",
        ),
        (
            PackageDocumentKind.CASH_FLOW_FORECAST,
            1,
            12,
            "forecast",
            "Twelve-Month Cash Flow Forecast",
        ),
        (
            PackageDocumentKind.FACILITY_STATEMENT,
            2,
            8,
            "facilities",
            "Existing Banking Facility Statement",
        ),
    ]
    for kind, file_count, pages, folder, title in support_specs:
        for index in range(1, file_count + 1):
            relative_path = Path(folder) / f"{kind.value}_{index:02d}.pdf"
            pdf_path = output_dir / relative_path
            _render_supporting_document(pdf_path, profile.company_name, title, pages, 2025)
            documents.append(
                GeneratedPackageDocument(
                    relative_path=relative_path.as_posix(),
                    kind=kind,
                    pages=_page_count(pdf_path),
                    financial_year=2025,
                )
            )

    completed = manifest.model_copy(update={"documents": documents})
    completed = RealisticPackageManifest.model_validate(completed.model_dump())
    (output_dir / "package_manifest.json").write_text(
        completed.model_dump_json(indent=2), encoding="utf-8"
    )
    return completed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=REPOSITORY_ROOT / "data" / "realistic_scenarios" / "realistic_01",
    )
    arguments = parser.parse_args()
    completed = generate_realistic_package(arguments.output)
    print(f"Package: {completed.package_id}")
    print(f"PDF files: {len(completed.documents)}")
    print(f"Pages: {sum(document.pages for document in completed.documents)}")
    print(f"Output: {arguments.output}")


if __name__ == "__main__":
    main()
