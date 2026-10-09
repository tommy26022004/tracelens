import json
import re
from pathlib import Path

from app.agent import nodes
from app.explainability.summary import RiskSummary
from tests.test_agent_full_graph import FakeLLM, FakeVectorStore


class MissingTaxLLM(FakeLLM):
    def generate_structured(self, prompt, schema):
        if schema is RiskSummary:
            match = re.search(r"[\w./-]+:period:0", prompt)
            assert match is not None
            financial_citation = match.group(0)
            return schema(
                headline=(
                    "The company reports a current ratio of 2.00 for FY2025, but has "
                    f"significant document coverage gaps [{financial_citation}]."
                ),
                body=f"Audited financial metrics were supplied [{financial_citation}].",
                recommended_human_checks=["Obtain and verify the missing tax return."],
            )
        return super().generate_structured(prompt, schema)


def test_case10_missing_tax_wording_citations_and_human_checks():
    root = Path(__file__).resolve().parents[2] / "data/ordered_tests_v1/10_missing_tax"
    store = FakeVectorStore()
    state = {
        "application_id": "missing-tax-review",
        "pdf_paths": [str(path) for path in sorted((root / "upload").glob("*.pdf"))],
        "trace": [],
        "errors": [],
    }

    state.update(nodes.parse_node(state))
    state.update(nodes.extract_node(state, store=store))
    state.update(nodes.validate_node(state))
    state.update(nodes.ratios_node(state))
    provider = MissingTaxLLM()
    state.update(nodes.assess_5c_node(state, llm=provider, store=store))
    state.update(nodes.summarise_node(state, llm=provider))

    assert {item["code"] for item in state["inconsistencies"]} == {
        "MISSING_BANK_MONTHS",
        "MISSING_CORE_DOCUMENTS",
    }
    character = state["five_c"]["character"]
    assert "SSM registration alone does" in character["reasoning"]
    assert "tax return alone" not in character["reasoning"]
    assert "filing acceptance" not in " ".join(character["flags_for_human_review"])

    summary = json.loads(state["risk_summary"])
    sourced_claim, inventory_claim = summary["headline"].split(", but", 1)
    assert "[" in sourced_claim
    assert "[" not in inventory_claim
    assert all(
        not check.startswith(("MISSING_BANK_MONTHS:", "MISSING_CORE_DOCUMENTS:"))
        for check in summary["recommended_human_checks"]
    )
