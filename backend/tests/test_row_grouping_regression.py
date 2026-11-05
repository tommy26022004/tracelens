"""Bank table rows must not depend on arbitrary coordinate buckets."""

from app.ingestion.extractor import _group_into_rows
from app.ingestion.parser import TextSpan


def test_nearby_spans_across_old_bucket_boundary_remain_one_row() -> None:
    spans = [
        TextSpan(text="Date", page=1, bbox=(10, 0.49, 40, 2.49)),
        TextSpan(text="Description", page=1, bbox=(50, 0.51, 120, 2.51)),
        TextSpan(text="Next row", page=1, bbox=(10, 11, 80, 13)),
    ]
    rows = _group_into_rows(spans)
    assert [[span.text for span in row] for row in rows] == [
        ["Date", "Description"],
        ["Next row"],
    ]
