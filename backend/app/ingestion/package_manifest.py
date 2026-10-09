"""Schema and default specification for realistic SME loan packages."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class PackageDocumentKind(StrEnum):
    BANK_STATEMENT = "bank_statement"
    AUDITED_FINANCIALS = "audited_financials"
    SSM_REGISTRATION = "ssm_registration"
    TAX_RETURN = "tax_return"
    MANAGEMENT_ACCOUNTS = "management_accounts"
    CASH_FLOW_FORECAST = "cash_flow_forecast"
    FACILITY_STATEMENT = "facility_statement"


class PackageDocumentSpec(BaseModel):
    kind: PackageDocumentKind
    expected_files: int = Field(ge=1)
    expected_pages_per_file: int = Field(ge=1)
    structured_extraction: bool = True
    required: bool = True

    @property
    def expected_pages(self) -> int:
        return self.expected_files * self.expected_pages_per_file


class GeneratedPackageDocument(BaseModel):
    relative_path: str
    kind: PackageDocumentKind
    pages: int = Field(ge=1)
    account_id: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    financial_year: int | None = None


class PackageAcceptanceCriteria(BaseModel):
    minimum_files: int = Field(ge=1)
    maximum_files: int = Field(ge=1)
    minimum_pages: int = Field(ge=1)
    maximum_pages: int = Field(ge=1)
    required_bank_months: int = Field(default=12, ge=1, le=24)
    required_financial_years: int = Field(default=3, ge=1, le=5)
    require_resolvable_citations: bool = True
    require_failure_isolation: bool = True

    @model_validator(mode="after")
    def validate_ranges(self) -> PackageAcceptanceCriteria:
        if self.minimum_files > self.maximum_files:
            raise ValueError("minimum_files cannot exceed maximum_files")
        if self.minimum_pages > self.maximum_pages:
            raise ValueError("minimum_pages cannot exceed maximum_pages")
        return self


class RealisticPackageManifest(BaseModel):
    specification_version: str = "1.0"
    package_id: str
    title: str
    company_name: str
    account_ids: list[str] = Field(min_length=1)
    financial_years: list[int] = Field(min_length=1)
    document_specs: list[PackageDocumentSpec] = Field(min_length=1)
    expected_findings: list[str] = Field(default_factory=list)
    documents: list[GeneratedPackageDocument] = Field(default_factory=list)
    acceptance: PackageAcceptanceCriteria

    @property
    def expected_file_count(self) -> int:
        return sum(item.expected_files for item in self.document_specs)

    @property
    def expected_page_count(self) -> int:
        return sum(item.expected_pages for item in self.document_specs)

    @model_validator(mode="after")
    def validate_expected_workload(self) -> RealisticPackageManifest:
        if (
            not self.acceptance.minimum_files
            <= self.expected_file_count
            <= self.acceptance.maximum_files
        ):
            raise ValueError("Expected file count falls outside acceptance range")
        if (
            not self.acceptance.minimum_pages
            <= self.expected_page_count
            <= self.acceptance.maximum_pages
        ):
            raise ValueError("Expected page count falls outside acceptance range")
        if len(set(self.account_ids)) != len(self.account_ids):
            raise ValueError("account_ids must be unique")
        if len(set(self.financial_years)) != len(self.financial_years):
            raise ValueError("financial_years must be unique")
        if self.documents:
            if len(self.documents) != self.expected_file_count:
                raise ValueError("Generated document count does not match specification")
            generated_pages = sum(document.pages for document in self.documents)
            if generated_pages != self.expected_page_count:
                raise ValueError("Generated page count does not match specification")
        return self


def default_realistic_package_manifest() -> RealisticPackageManifest:
    return RealisticPackageManifest(
        package_id="realistic_01",
        title="Healthy multi-account, multi-year SME package",
        company_name="ACME TRADING SDN BHD",
        account_ids=["operating_account", "collection_account"],
        financial_years=[2023, 2024, 2025],
        document_specs=[
            PackageDocumentSpec(
                kind=PackageDocumentKind.BANK_STATEMENT,
                expected_files=18,
                expected_pages_per_file=4,
            ),
            PackageDocumentSpec(
                kind=PackageDocumentKind.AUDITED_FINANCIALS,
                expected_files=3,
                expected_pages_per_file=40,
            ),
            PackageDocumentSpec(
                kind=PackageDocumentKind.SSM_REGISTRATION,
                expected_files=1,
                expected_pages_per_file=25,
            ),
            PackageDocumentSpec(
                kind=PackageDocumentKind.TAX_RETURN,
                expected_files=3,
                expected_pages_per_file=20,
            ),
            PackageDocumentSpec(
                kind=PackageDocumentKind.MANAGEMENT_ACCOUNTS,
                expected_files=4,
                expected_pages_per_file=8,
                structured_extraction=False,
            ),
            PackageDocumentSpec(
                kind=PackageDocumentKind.CASH_FLOW_FORECAST,
                expected_files=1,
                expected_pages_per_file=12,
                structured_extraction=False,
            ),
            PackageDocumentSpec(
                kind=PackageDocumentKind.FACILITY_STATEMENT,
                expected_files=2,
                expected_pages_per_file=8,
                structured_extraction=False,
            ),
        ],
        acceptance=PackageAcceptanceCriteria(
            minimum_files=30,
            maximum_files=45,
            minimum_pages=250,
            maximum_pages=500,
        ),
    )
