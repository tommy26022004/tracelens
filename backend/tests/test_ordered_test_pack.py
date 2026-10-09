import hashlib
import json

import pymupdf
import pytest

from scripts.generate_ordered_test_pack import build


def test_ordered_fixtures_are_independent_and_not_run(tmp_path):
    root = tmp_path / "ordered"
    plan = build(root)
    assert len(plan) == 16
    assert sum(case["pdf_count"] for case in plan) == 24
    for case in plan:
        assert case["status"] == "not_run"
        folder = root / case["folder"]
        truth = json.loads((folder / "ground_truth.json").read_text(encoding="utf-8"))
        assert truth["system_test_status"] == "not_run"
        for name, expected in truth["documents"].items():
            path = folder / "upload" / name
            assert hashlib.sha256(path.read_bytes()).hexdigest() == expected["sha256"]
            if expected["kind"] == "invalid":
                with pytest.raises(pymupdf.FileDataError):
                    pymupdf.open(path)
                continue
            with pymupdf.open(path) as document:
                assert len(document) == expected["pages"]
                text = "\n".join(page.get_text() for page in document)
                if expected.get("image_only"):
                    assert not text.strip()
                    assert document[0].get_images()
                else:
                    assert "SYNTHETIC" in text
                    assert "NOT AN OFFICIAL" in text
                if expected["kind"] == "management_accounts":
                    assert "65%" in document[2].get_text()
                    assert "70%" in document[2].get_text()
                    assert "65%" not in document[0].get_text()
    clean = json.loads((root / "02_bank_extraction/ground_truth.json").read_text(encoding="utf-8"))["documents"]["bank.pdf"]
    broken = json.loads((root / "07_balance_mismatch/ground_truth.json").read_text(encoding="utf-8"))["documents"]["bank.pdf"]
    assert clean["transactions"] == broken["transactions"]
    assert clean["fields"]["closing_balance"] == "14000.00"
    assert broken["fields"]["closing_balance"] == "14900.00"
    standard = json.loads((root / "04_financials_and_ratios/ground_truth.json").read_text(encoding="utf-8"))["documents"]["financials.pdf"]
    thousands = json.loads((root / "14_units_rm_thousands/ground_truth.json").read_text(encoding="utf-8"))["documents"]["financials_rm_thousands.pdf"]
    assert standard["periods"] == thousands["periods"]
    assert thousands["display_unit"] == "RM'000"
    with pytest.raises(FileExistsError):
        build(root)
