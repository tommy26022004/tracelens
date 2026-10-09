from app.ingestion.parser import TextSpan
from app.ingestion.types import SourceLocation


def source_location(row: list[TextSpan]) -> SourceLocation:
    if not row or len({span.page for span in row}) != 1:
        raise ValueError("A source row must belong to exactly one PDF page")
    return SourceLocation(
        page=row[0].page,
        text=" ".join(span.text for span in row),
        bbox=(
            min(span.bbox[0] for span in row),
            min(span.bbox[1] for span in row),
            max(span.bbox[2] for span in row),
            max(span.bbox[3] for span in row),
        ),
    )


def labelled_sources(
    rows: list[list[TextSpan]], labels: dict[str, str]
) -> dict[str, SourceLocation]:
    sources: dict[str, SourceLocation] = {}
    for row in rows:
        text = " ".join(span.text for span in row)
        for label, field in labels.items():
            if text.startswith(label) and field not in sources:
                sources[field] = source_location(row)
    return sources
