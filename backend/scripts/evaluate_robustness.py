"""Reproducible bank PDF perturbation baseline; never touches live stores."""

from __future__ import annotations

import argparse
import json
import tempfile
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

import pymupdf

from app.evaluation.extraction_accuracy import score_bank_statement
from app.ingestion import extractor
from app.ingestion.parser import ParsedPage, TextSpan, parse_pdf
from app.ingestion.synthetic import GeneratorConfig, generate
from app.ingestion.types import BankStatement


def old_bucket_rows(spans: list[TextSpan]) -> list[list[TextSpan]]:
    buckets: dict[int, list[TextSpan]] = defaultdict(list)
    for span in spans:
        midpoint = (span.bbox[1] + span.bbox[3]) / 2
        bucket = round(midpoint / extractor.ROW_TOLERANCE) * extractor.ROW_TOLERANCE
        buckets[int(bucket)].append(span)
    return [sorted(row, key=lambda item: item.bbox[0]) for _, row in sorted(buckets.items())]


def perturb(pages: list[ParsedPage], horizontal: float, vertical: float) -> list[ParsedPage]:
    output = []
    for page in pages:
        spans = []
        for index, span in enumerate(page.spans):
            left, top, right, bottom = span.bbox
            shift = vertical if index % 2 else -vertical
            spans.append(replace(span, bbox=(left + horizontal, top + shift, right + horizontal, bottom + shift)))
        output.append(replace(page, spans=spans))
    return output


def scan_copy(source: Path, target: Path) -> None:
    with pymupdf.open(source) as original, pymupdf.open() as scanned:
        for page in original:
            image = page.get_pixmap(matrix=pymupdf.Matrix(1, 1)).tobytes("png")
            copied = scanned.new_page(width=page.rect.width, height=page.rect.height)
            copied.insert_image(copied.rect, stream=image)
        scanned.save(target)


def run() -> dict:
    results = []
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        pdf, truth = generate(GeneratorConfig(seed=21, n_transactions=14, num_months=1), root)
        expected = BankStatement.model_validate_json(truth.read_text())
        pages = parse_pdf(pdf)
        for name, horizontal, vertical in [
            ("original", 0, 0), ("horizontal_shift", 18, 0),
            ("minor_jitter", 18, 0.5), ("moderate_jitter", 18, 1.0),
            ("boundary_jitter", 18, 1.4),
        ]:
            variant = perturb(pages, horizontal, vertical)
            scores = {}
            for label, grouping in [("previous", old_bucket_rows), ("current", extractor._group_into_rows)]:
                original_grouping = extractor._group_into_rows
                try:
                    extractor._group_into_rows = grouping
                    actual = extractor.extract_bank_statement(variant)
                    comparison = score_bank_statement(expected, actual)
                    scores[label] = {
                        "fields_matched": comparison.fields_matched,
                        "fields_total": comparison.fields_total,
                        "accuracy": comparison.accuracy,
                    }
                except (ValueError, TypeError) as error:
                    scores[label] = {"error": type(error).__name__, "accuracy": 0.0}
                finally:
                    extractor._group_into_rows = original_grouping
            results.append({"scenario": name, "scores": scores})

        scan = root / "scan.pdf"
        scan_copy(pdf, scan)
        scan_pages = parse_pdf(scan)
        scanned_detected = all(page.needs_ocr for page in scan_pages)
        try:
            extractor.extract_bank_statement(scan_pages)
            scanned_rejected = False
        except ValueError:
            scanned_rejected = True
        results.append({"scenario": "image_only_scan", "needs_ocr_detected": scanned_detected, "unsupported_extraction_rejected": scanned_rejected})
    return {"dataset": "synthetic-bank-seed-21-v1", "results": results, "scope": "Synthetic PDF; geometry perturbations applied after parsing. Not a real-bank accuracy estimate."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()
    report = run()
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
