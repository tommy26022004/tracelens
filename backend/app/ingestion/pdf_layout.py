"""Small ReportLab canvas helpers shared by synthetic PDF generators."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

PAGE_WIDTH, PAGE_HEIGHT = A4
LEFT = 42
RIGHT = PAGE_WIDTH - 42


def format_money(value: Decimal) -> str:
    if value < 0:
        return f"({abs(value):,.2f})"
    return f"{value:,.2f}"


def draw_page_frame(
    canvas: Canvas,
    company_name: str,
    document_type: str,
    page_number: int,
    page_count: int,
) -> None:
    canvas.setFillColor(colors.HexColor("#123B63"))
    canvas.rect(0, PAGE_HEIGHT - 48, PAGE_WIDTH, 48, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(LEFT, PAGE_HEIGHT - 29, company_name)
    canvas.drawRightString(RIGHT, PAGE_HEIGHT - 29, document_type)
    canvas.setFillColor(colors.HexColor("#4B5563"))
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(PAGE_WIDTH / 2, 24, f"Page {page_number} of {page_count}")
    canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
    canvas.line(LEFT, 34, RIGHT, 34)


def draw_title(canvas: Canvas, title: str, subtitle: str | None = None, y: float = 750) -> float:
    canvas.setFillColor(colors.HexColor("#0F172A"))
    canvas.setFont("Helvetica-Bold", 16)
    canvas.drawString(LEFT, y, title)
    if subtitle:
        canvas.setFillColor(colors.HexColor("#475569"))
        canvas.setFont("Helvetica", 9)
        canvas.drawString(LEFT, y - 17, subtitle)
        return y - 38
    return y - 24


def draw_section(canvas: Canvas, title: str, y: float) -> float:
    canvas.setFillColor(colors.HexColor("#E2E8F0"))
    canvas.rect(LEFT, y - 5, RIGHT - LEFT, 22, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#0F172A"))
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(LEFT + 7, y + 2, title)
    return y - 24


def draw_key_values(
    canvas: Canvas,
    rows: Sequence[tuple[str, str]],
    y: float,
    label_width: float = 175,
    row_height: float = 21,
) -> float:
    for label, value in rows:
        canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
        canvas.rect(LEFT, y - row_height + 4, RIGHT - LEFT, row_height, fill=0, stroke=1)
        canvas.setFillColor(colors.HexColor("#F8FAFC"))
        canvas.rect(LEFT, y - row_height + 4, label_width, row_height, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor("#334155"))
        canvas.setFont("Helvetica-Bold", 8.5)
        canvas.drawString(LEFT + 6, y - 10, f"{label}:")
        canvas.setFont("Helvetica", 8.5)
        canvas.drawString(LEFT + label_width + 7, y - 10, value)
        y -= row_height
    return y


def draw_table(
    canvas: Canvas,
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    widths: Sequence[float],
    y: float,
    row_height: float = 20,
    aligns: Sequence[str] | None = None,
    font_size: float = 8,
) -> float:
    aligns = aligns or ["left"] * len(headers)
    x_positions = [LEFT]
    for width in widths:
        x_positions.append(x_positions[-1] + width)

    canvas.setFillColor(colors.HexColor("#D9EAF7"))
    canvas.rect(LEFT, y - row_height, sum(widths), row_height, fill=1, stroke=0)
    canvas.setFont("Helvetica-Bold", font_size)
    canvas.setFillColor(colors.HexColor("#0F172A"))
    for index, header in enumerate(headers):
        canvas.drawString(x_positions[index] + 4, y - row_height + 6, header)

    current_y = y - row_height
    canvas.setFont("Helvetica", font_size)
    for row in rows:
        next_y = current_y - row_height
        canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
        canvas.rect(LEFT, next_y, sum(widths), row_height, fill=0, stroke=1)
        for index, value in enumerate(row):
            x_left = x_positions[index]
            x_right = x_positions[index + 1]
            canvas.line(x_right, next_y, x_right, next_y + row_height)
            if aligns[index] == "right":
                canvas.drawRightString(x_right - 4, next_y + 6, str(value))
            else:
                canvas.drawString(x_left + 4, next_y + 6, str(value)[:55])
        current_y = next_y
    return current_y


def finish_page(canvas: Canvas) -> None:
    canvas.showPage()
