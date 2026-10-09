"""Regression tests for the ten coherent multi-document SME scenarios."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ingestion.extractor import extract_bank_statement
from app.ingestion.financials_extractor import extract_audited_financials
from app.ingestion.parser import parse_pdf
from app.ingestion.ssm_extractor import extract_ssm_registration
from app.ingestion.tax_extractor import extract_tax_return
from app.validation.cross_doc import run_cross_doc_checks
from scripts.generate_scenarios import generate_all


@pytest.fixture(scope="module")
def generated_scenarios(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("scenarios")
    generate_all(output)
    return output


def test_all_scenarios_have_expected_page_counts(generated_scenarios: Path) -> None:
    scenario_dirs = sorted(generated_scenarios.glob("scenario_*"))
    assert len(scenario_dirs) == 10
    for scenario_dir in scenario_dirs:
        manifest = json.loads((scenario_dir / "scenario_manifest.json").read_text())
        assert manifest["page_counts"] == {
            "bank_statement": 8,
            "audited_financials": 7,
            "ssm_registration": 5,
            "tax_return": 5,
        }
        assert manifest["total_pages"] == 25


def test_manifest_findings_match_extracted_documents(generated_scenarios: Path) -> None:
    for scenario_dir in sorted(generated_scenarios.glob("scenario_*")):
        bank = extract_bank_statement(parse_pdf(scenario_dir / "bank_statement.pdf"))
        financials = extract_audited_financials(parse_pdf(scenario_dir / "audited_financials.pdf"))
        ssm = extract_ssm_registration(parse_pdf(scenario_dir / "ssm_registration.pdf"))
        tax = extract_tax_return(parse_pdf(scenario_dir / "tax_return.pdf"))
        findings = run_cross_doc_checks(
            [bank],
            ["bank"],
            [ssm],
            ["ssm"],
            [financials],
            ["financials"],
            [tax],
            ["tax"],
        )
        actual_codes = sorted(finding.code for finding in findings)
        manifest = json.loads((scenario_dir / "scenario_manifest.json").read_text())
        expected_codes = sorted(manifest["expected_inconsistency_codes"])
        assert actual_codes == expected_codes, scenario_dir.name


def test_missing_data_scenario_is_explicit(generated_scenarios: Path) -> None:
    manifest = json.loads(
        (generated_scenarios / "scenario_10" / "scenario_manifest.json").read_text()
    )
    assert manifest["deliberate_missing_fields"] == [
        "tax.capital_allowance_schedule",
        "tax.authorized_signatory",
    ]
