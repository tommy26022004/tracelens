"""Export the manual testing guide to an Excel workbook.

Each scenario becomes its own sheet so you can tick checkboxes inline,
add notes per step, and hand a single .xlsx to a supervisor or QA
reviewer.

Layout per sheet:
    A: Step ID            (1.1, 1.2, ...)
    B: What to do         (instructions)
    C: Expected outcome   (what "right" looks like)
    D: If it goes wrong   (troubleshooting)
    E: Result             (dropdown: PASS / FAIL / SKIP)
    F: Notes              (free-text, for the reviewer)

Run:
    python -m scripts.export_testing_guide
    # writes docs/TESTING_GUIDE.xlsx
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.worksheet import Worksheet

# ---------------------------------------------------------------------------
# Styling helpers
# ---------------------------------------------------------------------------

THIN = Side(border_style="thin", color="CBD5E1")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

HEADER_FILL = PatternFill("solid", fgColor="4F46E5")  # indigo-600
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
SECTION_FILL = PatternFill("solid", fgColor="EEF2FF")  # indigo-50
SECTION_FONT = Font(bold=True, color="3730A3", size=12)
SCENARIO_FILL = PatternFill("solid", fgColor="DBEAFE")
WRAP = Alignment(wrap_text=True, vertical="top")


# ---------------------------------------------------------------------------
# Content — kept in plain Python data so it stays diff-friendly.
# Each "step" tuple: (id, do, expected, if_wrong)
# ---------------------------------------------------------------------------

OVERVIEW_PARAGRAPHS = [
    "Hệ thống làm gì:",
    "Loan officer ở ngân hàng Malaysia muốn cho SME vay tiền. Họ phải đọc nhiều "
    "loại giấy tờ (bank statement, đăng ký SSM, audited financials, tax Form C) "
    "rồi viết bản đánh giá rủi ro — quá trình mất 2-6 tuần.",
    "Hệ thống tự động: parse PDF → trích số liệu → đối chiếu giữa các file → "
    "tính tỷ số tài chính → đánh giá 5C → sinh risk summary với inline "
    "citations (mỗi câu trace ngược về dòng PDF gốc — yêu cầu FEATERS của BNM).",
    "",
    "Các khái niệm chính:",
    "• chunk_id: mẩu thông tin nhỏ trích từ PDF, dạng "
    "{document_id}:{kind}:{index}.",
    "• FEATERS: 7 nguyên tắc BNM cho AI — Fairness/Ethics/Accountability/"
    "Transparency/Explainability/Reliability/Security. Project tập trung "
    "Explainability → mọi claim phải traceable.",
    "• 5C: framework credit assessment — Character/Capacity/Capital/Collateral/"
    "Conditions.",
    "• Citation hallucination: LLM trích dẫn chunk_id không có thật. Hệ thống "
    "catch trước khi hiển thị.",
]


PRE_CHECK_STEPS = [
    (
        "0.1",
        "Kiểm tra bạn có:\n"
        "• Docker Desktop đang chạy\n"
        "• Python với uv đã cài (Phase 1)\n"
        "• Node.js 20+ và npm\n"
        "• Gemini API key đã paste vào backend/.env\n\n"
        "Nếu chưa có Gemini key: mở https://aistudio.google.com → API keys → "
        "Create. Paste vào backend/.env sau dấu = của dòng GEMINI_API_KEY=.",
        "Tất cả 4 checkpoint đều ✓.",
        "Nếu thiếu thứ gì, dừng lại và cài trước.",
    ),
    (
        "0.2",
        "Mở terminal, chạy:\n\n    docker ps",
        "Hiện bảng header CONTAINER ID IMAGE COMMAND... — không có error.",
        "Nếu thấy 'error during connect: docker daemon': mở Docker Desktop từ "
        "Start menu, đợi ~30 giây cho daemon khởi động, chạy lại lệnh.",
    ),
]


SCENARIO_1 = {
    "title": "Scenario 1 — Happy path (chạy đầy đủ với 4 loại document)",
    "intro": [
        "Upload 4 PDF (cùng công ty ACME), hệ thống chạy 6 step và trả về "
        "summary với citations click được.",
    ],
    "steps": [
        (
            "1.1",
            "Mở terminal, chạy:\n\n"
            "    cd c:/Tommy/Documents/GitHub/FYP\n"
            "    docker compose up -d qdrant postgres",
            "Output kết thúc bằng 'Container fyp-qdrant-1 Started' và "
            "'Container fyp-postgres-1 Started'.\n\n"
            "Verify thêm: curl http://localhost:6333/ phải trả "
            "{\"title\":\"qdrant - vector search engine\",...}.",
            "Lỗi 'port already in use': chạy docker compose down rồi up lại.\n"
            "Lỗi 'cannot find Docker daemon': quay lại bước 0.2.",
        ),
        (
            "1.2",
            "Mở TERMINAL MỚI (giữ terminal cũ chạy Docker), chạy:\n\n"
            "    cd c:/Tommy/Documents/GitHub/FYP/backend\n"
            "    uv run uvicorn app.main:app --reload\n\n"
            "Để tab này chạy trong suốt session test.",
            "Cuối output có:\n"
            "  INFO: Uvicorn running on http://127.0.0.1:8000\n"
            "  INFO: Application startup complete.\n\n"
            "Verify: curl http://localhost:8000/health trả {\"status\":\"ok\"}.\n"
            "Bonus: mở http://localhost:8000/docs xem Swagger UI.",
            "ModuleNotFoundError: chạy uv sync rồi thử lại.\n"
            "address already in use: kill process Python cũ hoặc dùng --port 8001.",
        ),
        (
            "1.3",
            "Mở TERMINAL THỨ 3, chạy:\n\n"
            "    cd c:/Tommy/Documents/GitHub/FYP/frontend\n"
            "    npm run dev",
            "Output có:\n"
            "  VITE v... ready in ... ms\n"
            "  ➜  Local: http://localhost:5173/\n\n"
            "Mở http://localhost:5173/ trong browser, thấy:\n"
            "• Header 'SME Loan Risk Analyser' + tag 'Prototype'\n"
            "• Card 'Upload SME application package' + drop zone",
            "npm: command not found → cài Node từ nodejs.org.\n"
            "Trang trắng → F12 → Console xem lỗi. Restart npm run dev.",
        ),
        (
            "1.4",
            "Trên trang web, click 'browse to select'. Tìm tới:\n"
            "    c:\\Tommy\\Documents\\GitHub\\FYP\\data\\samples\\\n\n"
            "Chọn 4 file PDF (KHÔNG chọn .ground_truth.json):\n"
            "• bank_statement_2026-01-01.pdf\n"
            "• ssm_202401000123.pdf\n"
            "• audited_financials_2025.pdf\n"
            "• tax_return_YA2025.pdf\n\n"
            "Click Open.",
            "Hiện danh sách 4 file với kích thước (KB).\n"
            "Nút 'Analyse package' sáng lên (không bị mờ).",
            "Danh sách không hiện → F12 → Console.",
        ),
        (
            "1.5",
            "Click 'Analyse package'. Đợi 40-60 giây.\n\n"
            "Đừng đóng tab hay click lại.\n"
            "Có thể theo dõi terminal backend song song.",
            "Sau khi spinner dừng, trang xuất hiện CARDS MỚI:\n\n"
            "• Risk summary: headline + body có inline tags [chunk_id] màu xanh\n"
            "• 5C credit assessment: 5 cột Character/Capacity/Capital/Collateral/"
            "Conditions, mỗi cột có rating chip (strong/adequate/weak/...)\n"
            "• Validation findings: có thể trống (4 file synthetic đều consistent)\n"
            "• Bank-statement metrics: Net change, Avg inflow,...\n"
            "• Reasoning trail: 6 dòng theo thứ tự parse → extract → validate → "
            "ratios → assess_5c → summarise. Tổng ~40-60s.",
            "Spinner >3 phút: có thể rate-limit. Check backend terminal cho lỗi "
            "429 RESOURCE_EXHAUSTED — đợi 1 phút.\n"
            "Error đỏ: đọc message. 'GEMINI_API_KEY is not configured' → quay 0.1.\n"
            "Không có Risk summary: xem terminal backend cho traceback.",
        ),
        (
            "1.6",
            "Trong card Risk summary, tìm 1 tag xanh indigo (ví dụ "
            "[transaction:5] hoặc [summary:0]).\n\n"
            "CLICK vào tag đó.",
            "Modal popup hiện ra với:\n"
            "• Tiêu đề 'Source citation' + chunk_id đầy đủ\n"
            "• Kind: transaction/summary/director/period\n"
            "• Page: số trang PDF gốc\n"
            "• Source text: văn bản gốc — đây là cái LLM đã dựa vào\n"
            "• Raw metadata (collapsible): debit, credit, balance,...\n\n"
            "Đóng modal: click ra ngoài hoặc nút ×.\n\n"
            "TẠI SAO QUAN TRỌNG: chứng minh AI không hallucinate. Mỗi claim có "
            "thể trace ngược về PDF gốc.",
            "Modal hiện 'Chunk lookup failed (404)' → Qdrant bị wipe. Refresh "
            "trang, upload lại từ đầu.",
        ),
        (
            "1.7",
            "Cuộn xuống card 'Reasoning trail'. Đọc 6 dòng.",
            "6 step đầy đủ:\n"
            "• parse (~14ms): detect 4 kinds\n"
            "• extract (~9s): upsert ~19 chunks\n"
            "• validate (~0ms): 0 findings cho synthetic clean data\n"
            "• ratios (~0ms): bank metrics + financial ratios\n"
            "• assess_5c (~13s): rate Character/Capacity/Capital/...\n"
            "• summarise (~20s): generate >=1 citation\n\n"
            "Đây là AUDIT TRAIL FEATERS — mọi step có timestamp, lưu vào Postgres.",
            "Thiếu step nào → có error ở giữa pipeline. Xem card 'Recoverable "
            "errors' nếu có, hoặc terminal backend.",
        ),
    ],
}


SCENARIO_2 = {
    "title": "Scenario 2 — Cross-doc validation catch tên không khớp",
    "intro": [
        "Chứng minh cross-doc validation hoạt động — đây là điểm khác biệt so "
        "với prior work (đa số chỉ xử lý 1 doc type tại 1 thời điểm).",
        "Bước 2.1 sinh bank statement giả mang tên BETA CORP (khác với SSM "
        "tên ACME). Hệ thống phải flag CRITICAL khi upload.",
    ],
    "steps": [
        (
            "2.1",
            "Terminal mới (giữ backend + frontend đang chạy):\n\n"
            "    cd c:/Tommy/Documents/GitHub/FYP/backend\n"
            "    uv run python -c \"\n"
            "from pathlib import Path\n"
            "from app.ingestion.synthetic import GeneratorConfig, generate\n"
            "cfg = GeneratorConfig(seed=99, account_holder='BETA CORP SDN BHD', "
            "n_transactions=10)\n"
            "pdf, gt = generate(cfg, Path('../data/samples'))\n"
            "print(f'Sinh xong: {pdf}')\n"
            "\"",
            "Output báo 'Sinh xong: ..\\data\\samples\\bank_statement_2026-01-01.pdf'.\n"
            "File gốc bị ghi đè — đây là chủ ý cho test.",
            "Lỗi import → đảm bảo đứng đúng thư mục backend/ trước khi chạy.",
        ),
        (
            "2.2",
            "Quay lại http://localhost:5173/.\n"
            "1. REFRESH trang (Ctrl+R) — quan trọng để clear state cũ.\n"
            "2. Click 'browse to select', chọn lại 4 file (bank giờ là BETA "
            "CORP, 3 file kia vẫn ACME).\n"
            "3. Click 'Analyse package', chờ ~40-60s.",
            "Card 'Validation findings' XUẤT HIỆN với ít nhất 1 finding MÀU "
            "ĐỎ (CRITICAL):\n\n"
            "  HOLDER_SSM_MISMATCH\n"
            "  Bank statement holder 'BETA CORP SDN BHD' does not match any "
            "registered company name on the SSM form(s): ACME TRADING SDN BHD.\n\n"
            "Click citation tags trong finding — đưa về:\n"
            "• Bank summary (chứng cứ holder = BETA CORP)\n"
            "• SSM summary (chứng cứ tên đăng ký = ACME)\n\n"
            "Đây là kết quả TỐT: hệ thống catch identity mismatch.\n\n"
            "BONUS: Risk summary có nhắc đến mismatch không?",
            "Không thấy finding → có thể bạn quên refresh hoặc upload nhầm file. "
            "Verify lại tên file đã upload.",
        ),
        (
            "2.3",
            "Restore file gốc:\n\n"
            "    cd c:/Tommy/Documents/GitHub/FYP/backend\n"
            "    uv run python -c \"\n"
            "from pathlib import Path\n"
            "from app.ingestion.synthetic import GeneratorConfig, generate\n"
            "pdf, gt = generate(GeneratorConfig(), Path('../data/samples'))\n"
            "print(f'Restored: {pdf}')\n"
            "\"",
            "Output 'Restored: ..\\data\\samples\\bank_statement_2026-01-01.pdf'.",
            "Quan trọng để Scenario 3 và 4 chạy đúng — đừng quên.",
        ),
    ],
}


SCENARIO_3 = {
    "title": "Scenario 3 — Declared income không khớp deposits",
    "intro": [
        "Tax return khai income RM 5M (quá lớn) trong khi bank statement chỉ "
        "thể hiện inflow ~RM 1M/năm. Gap >30% phải bị flag WARNING.",
    ],
    "steps": [
        (
            "3.1",
            "Terminal mới:\n\n"
            "    cd c:/Tommy/Documents/GitHub/FYP/backend\n"
            "    uv run python -c \"\n"
            "from decimal import Decimal\n"
            "from pathlib import Path\n"
            "from app.ingestion.tax_synthetic import "
            "TaxReturnGeneratorConfig, generate\n"
            "cfg = TaxReturnGeneratorConfig(\n"
            "  gross_business_income=Decimal('5000000.00'),\n"
            "  chargeable_income=Decimal('1200000.00'),\n"
            "  tax_payable=Decimal('288000.00'),\n"
            ")\n"
            "pdf, gt = generate(cfg, Path('../data/samples'))\n"
            "print(f'Sinh xong: {pdf}')\n"
            "\"",
            "Output báo Sinh xong: ..\\data\\samples\\tax_return_YA2025.pdf.",
            "Lỗi import → đảm bảo trong thư mục backend/.",
        ),
        (
            "3.2",
            "Refresh trang web, upload lại 4 file. Click Analyse.",
            "Validation findings có 1 finding MÀU VÀNG (WARNING):\n\n"
            "  DECLARED_INCOME_VS_DEPOSITS\n"
            "  Tax return declares gross business income RM 5000000.00, but "
            "annualised bank credits suggest RM ~1095677 (~78% gap).\n\n"
            "Citations chỉ về tax_return summary và bank_statement summary.",
            "% gap có thể khác chút (60-80%) tùy seed bank statement. Cốt yếu "
            "là phải >30% và bị flag.",
        ),
        (
            "3.3",
            "Restore tax return gốc:\n\n"
            "    cd c:/Tommy/Documents/GitHub/FYP/backend\n"
            "    uv run python -c \"\n"
            "from pathlib import Path\n"
            "from app.ingestion.tax_synthetic import "
            "TaxReturnGeneratorConfig, generate\n"
            "pdf, gt = generate(TaxReturnGeneratorConfig(), "
            "Path('../data/samples'))\n"
            "print(f'Restored: {pdf}')\n"
            "\"",
            "Output 'Restored: ..\\data\\samples\\tax_return_YA2025.pdf'.",
            "—",
        ),
    ],
}


SCENARIO_4 = {
    "title": "Scenario 4 — Evaluation harness (FYP grading metrics)",
    "intro": [
        "Script tự đo 4 metric mà proposal section 12 cam kết:",
        "• Extraction accuracy ≥ 90%",
        "• Citation faithfulness = 0 hallucinations",
        "• Latency p95 < 180s",
        "• SUS template (cần user study riêng)",
    ],
    "steps": [
        (
            "4.1",
            "Terminal mới (giữ backend chạy):\n\n"
            "    cd c:/Tommy/Documents/GitHub/FYP/backend\n"
            "    uv run python -m scripts.evaluate --runs 2\n\n"
            "Tham số --runs 2 = chạy graph 2 lần để đo latency p50/p95.\n"
            "Tổng thời gian: ~3-5 phút.",
            "Cuối output có report 'FYP EVALUATION REPORT' với 4 sections.\n"
            "Section [1] EXTRACTION ACCURACY: 4 doc types đều 100%, PASS (>90%).\n"
            "Section [2] CITATION FAITHFULNESS: PASS (0 hallucinations).\n"
            "Section [3] LATENCY: p50 ~50s, p95 ~60s, PASS (<180s).\n"
            "Section [4] USABILITY: text instructions (chưa run được tự động).",
            "Extraction <90% → có mismatch generator vs extractor (đọc 'mismatch:').\n"
            "Faithfulness <100% → LLM hallucinate chunk_ids (xem 'Invalid').\n"
            "Latency p95 ≥ 180s → Gemini chậm hoặc rate limit. Chạy lại sau.",
        ),
        (
            "4.2",
            "(Optional) Dump JSON cho FYP report:\n\n"
            "    cd c:/Tommy/Documents/GitHub/FYP/backend\n"
            "    uv run python -m scripts.evaluate --runs 3 --json eval_report.json",
            "File eval_report.json được tạo, chứa full machine-readable data. "
            "Paste vào final report làm appendix.",
            "—",
        ),
    ],
}


CLEANUP_STEPS = [
    (
        "C.1",
        "Stop frontend: Ctrl+C ở terminal frontend.\n"
        "Stop backend: Ctrl+C ở terminal backend.",
        "Cả 2 terminal về prompt thường.",
        "Nếu Ctrl+C không tắt được, đóng cả terminal.",
    ),
    (
        "C.2",
        "Stop containers:\n\n"
        "    cd c:/Tommy/Documents/GitHub/FYP\n"
        "    docker compose down",
        "Output 'Container fyp-qdrant-1 Stopped/Removed', 'fyp-postgres-1 "
        "Stopped/Removed', 'Network fyp_default Removed'.",
        "Nếu muốn fresh start lần sau (xóa volume data): docker compose down -v.",
    ),
]


TROUBLESHOOTING = [
    (
        "ECONNREFUSED localhost:8000 trong browser console",
        "Backend chưa khởi động hoặc đã crash. Quay lại Bước 1.2.",
    ),
    (
        "Modal citation hiện 'Chunk lookup failed (404)'",
        "Qdrant đã bị wipe giữa lần ingest. Refresh trang, upload lại.",
    ),
    (
        "'429 RESOURCE_EXHAUSTED' ở terminal backend",
        "Gemini free tier = 1500 req/day. Đã hit limit, chờ 24h hoặc đổi key.",
    ),
    (
        "Trang web load nhưng UI vỡ (không có style)",
        "Tailwind chưa build. Trong terminal frontend chạy lại 'npm run dev'.",
    ),
    (
        "Sample PDF không đúng (do edge-case test)",
        "Re-sinh tất cả: chạy lại 3 lệnh Python ở Scenario 2.3 / 3.3, hoặc "
        "python -m scripts.smoke_agent.",
    ),
    (
        "Mất API key",
        "Tạo key mới ở aistudio.google.com → API keys, paste vào backend/.env, "
        "restart backend.",
    ),
    (
        "Postgres container không khởi động",
        "Check 'docker logs fyp-postgres-1'. Thường là conflict cổng 5432 với "
        "Postgres local. Stop Postgres local trước.",
    ),
]


SUPERVISOR_QA = [
    (
        "Tại sao em không dùng Amazon Bedrock như proposal viết ban đầu?",
        "Free tier giới hạn ở Bedrock + không có AWS credit. Đã design "
        "provider-agnostic layer (app/core/llm.py) nên swap Gemini ↔ Bedrock "
        "chỉ cần thay implementation, agent code không đổi.",
    ),
    (
        "Tại sao chỉ test với synthetic data?",
        "Real SME documents là confidential, chứa NRIC + tax info. Synthetic "
        "data có ground truth chính xác để đo extraction accuracy. Phase "
        "future work: validate với real anonymised data từ supervisor.",
    ),
    (
        "FEATERS Explainability cụ thể thể hiện ở đâu?",
        "Mỗi claim trong risk summary có inline [chunk_id] citation — loan "
        "officer click vào xem dòng PDF gốc. Hệ thống verify tất cả citations "
        "against ingestion-produced allow-list — nếu LLM hallucinate chunk_id, "
        "bị catch và logged vào recoverable errors.",
    ),
    (
        "5C Capital tại sao luôn là 'insufficient_data' khi chỉ upload bank "
        "statement?",
        "Capital đánh giá vốn chủ (equity) — chỉ có trong audited financials. "
        "Bank statement không bộc lộ thông tin này. Đây là đúng epistemic "
        "stance — thà rate insufficient_data còn hơn LLM đoán bừa.",
    ),
    (
        "Reasoning chain lưu ở đâu? Có thể audit lại không?",
        "Postgres checkpointer (langgraph-checkpoint-postgres). Mỗi state sau "
        "từng node được persist với thread_id. Có thể replay 1 application "
        "sau này.",
    ),
]


# ---------------------------------------------------------------------------
# Sheet builders
# ---------------------------------------------------------------------------

COLUMN_WIDTHS = {
    "A": 8,
    "B": 55,
    "C": 55,
    "D": 45,
    "E": 12,
    "F": 30,
}


def _set_widths(ws: Worksheet) -> None:
    for col, width in COLUMN_WIDTHS.items():
        ws.column_dimensions[col].width = width


def _write_header_row(ws: Worksheet, row: int, cells: list[str]) -> None:
    for col_idx, value in enumerate(cells, start=1):
        cell = ws.cell(row=row, column=col_idx, value=value)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = WRAP
        cell.border = BORDER
    ws.row_dimensions[row].height = 28


def _write_step_rows(ws: Worksheet, start_row: int, steps: list[tuple]) -> int:
    """Write each step into a single row spanning columns A-F."""
    row = start_row
    for step_id, do, expected, if_wrong in steps:
        ws.cell(row=row, column=1, value=step_id).alignment = WRAP
        ws.cell(row=row, column=2, value=do).alignment = WRAP
        ws.cell(row=row, column=3, value=expected).alignment = WRAP
        ws.cell(row=row, column=4, value=if_wrong).alignment = WRAP
        ws.cell(row=row, column=5, value="").alignment = WRAP  # dropdown target
        ws.cell(row=row, column=6, value="").alignment = WRAP
        for col_idx in range(1, 7):
            ws.cell(row=row, column=col_idx).border = BORDER
        # Approximate auto-height: 18px per ~80 chars in any column.
        approx_lines = max(
            (len(do) // 70) + do.count("\n") + 1,
            (len(expected) // 70) + expected.count("\n") + 1,
            (len(if_wrong) // 70) + if_wrong.count("\n") + 1,
            3,
        )
        ws.row_dimensions[row].height = min(approx_lines * 16, 320)
        row += 1
    return row


def _attach_result_dropdown(ws: Worksheet, first_row: int, last_row: int) -> None:
    if last_row < first_row:
        return
    dv = DataValidation(type="list", formula1='"PASS,FAIL,SKIP"', allow_blank=True)
    dv.add(f"E{first_row}:E{last_row}")
    ws.add_data_validation(dv)


def build_overview_sheet(ws: Worksheet) -> None:
    ws.title = "Overview"
    _set_widths(ws)
    ws.merge_cells("A1:F1")
    ws["A1"] = "Hướng dẫn test manual hệ thống FYP"
    ws["A1"].font = Font(bold=True, size=16, color="3730A3")
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws["A1"].fill = SECTION_FILL
    ws.row_dimensions[1].height = 34

    row = 3
    for paragraph in OVERVIEW_PARAGRAPHS:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
        cell = ws.cell(row=row, column=1, value=paragraph)
        cell.alignment = WRAP
        if paragraph.endswith(":"):
            cell.font = SECTION_FONT
        approx_lines = max((len(paragraph) // 100) + 1, 1)
        ws.row_dimensions[row].height = approx_lines * 16
        row += 1

    row += 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
    cell = ws.cell(
        row=row, column=1, value="Cách dùng workbook này"
    )
    cell.font = SECTION_FONT
    cell.fill = SECTION_FILL
    cell.alignment = WRAP
    row += 1

    instructions = [
        "1. Mỗi sheet ứng với 1 scenario (Pre-check + 4 Scenarios + Cleanup + "
        "Troubleshooting + Supervisor Q&A).",
        "2. Đọc cột B (What to do) — làm theo từng bước.",
        "3. So sánh kết quả thực tế với cột C (Expected outcome).",
        "4. Nếu khớp → chọn PASS ở cột E (dropdown).",
        "5. Nếu sai → đọc cột D (If it goes wrong), thử fix; chọn FAIL nếu "
        "không sửa được.",
        "6. Cột F (Notes) để ghi observation, screenshot path, hoặc questions "
        "cho supervisor.",
    ]
    for line in instructions:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
        cell = ws.cell(row=row, column=1, value=line)
        cell.alignment = WRAP
        ws.row_dimensions[row].height = 24
        row += 1


def build_steps_sheet(
    wb: Workbook,
    title: str,
    section_title: str,
    intro: list[str],
    steps: list[tuple],
) -> None:
    ws = wb.create_sheet(title=title)
    _set_widths(ws)

    # Section banner.
    ws.merge_cells("A1:F1")
    ws["A1"] = section_title
    ws["A1"].font = Font(bold=True, size=14, color="1E1B4B")
    ws["A1"].fill = SCENARIO_FILL
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 28

    # Intro lines.
    row = 2
    for line in intro:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
        cell = ws.cell(row=row, column=1, value=line)
        cell.alignment = WRAP
        ws.row_dimensions[row].height = 18
        row += 1
    row += 1

    # Column header row.
    _write_header_row(
        ws,
        row,
        ["Step", "What to do", "Expected outcome", "If it goes wrong", "Result", "Notes"],
    )
    first_data_row = row + 1
    last_data_row = _write_step_rows(ws, first_data_row, steps) - 1
    _attach_result_dropdown(ws, first_data_row, last_data_row)

    # Freeze the header row.
    ws.freeze_panes = ws.cell(row=first_data_row, column=1)


def build_troubleshooting_sheet(wb: Workbook) -> None:
    ws = wb.create_sheet(title="Troubleshooting")
    ws.column_dimensions["A"].width = 60
    ws.column_dimensions["B"].width = 80

    ws.merge_cells("A1:B1")
    ws["A1"] = "Troubleshooting nhanh"
    ws["A1"].font = Font(bold=True, size=14, color="1E1B4B")
    ws["A1"].fill = SCENARIO_FILL
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 28

    _write_header_row(ws, 3, ["Triệu chứng", "Cách xử lý"])
    row = 4
    for symptom, fix in TROUBLESHOOTING:
        ws.cell(row=row, column=1, value=symptom).alignment = WRAP
        ws.cell(row=row, column=2, value=fix).alignment = WRAP
        for col_idx in (1, 2):
            ws.cell(row=row, column=col_idx).border = BORDER
        ws.row_dimensions[row].height = max((len(fix) // 90 + 1) * 18, 24)
        row += 1


def build_supervisor_qa_sheet(wb: Workbook) -> None:
    ws = wb.create_sheet(title="Supervisor Q&A")
    ws.column_dimensions["A"].width = 55
    ws.column_dimensions["B"].width = 80

    ws.merge_cells("A1:B1")
    ws["A1"] = "Phòng trường hợp supervisor hỏi"
    ws["A1"].font = Font(bold=True, size=14, color="1E1B4B")
    ws["A1"].fill = SCENARIO_FILL
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 28

    _write_header_row(ws, 3, ["Question", "Answer"])
    row = 4
    for q, a in SUPERVISOR_QA:
        ws.cell(row=row, column=1, value=q).alignment = WRAP
        ws.cell(row=row, column=2, value=a).alignment = WRAP
        for col_idx in (1, 2):
            ws.cell(row=row, column=col_idx).border = BORDER
        ws.row_dimensions[row].height = max((len(a) // 90 + 1) * 18, 30)
        row += 1


def build_summary_sheet(wb: Workbook) -> None:
    ws = wb.create_sheet(title="Summary checklist", index=1)
    ws.column_dimensions["A"].width = 32
    ws.column_dimensions["B"].width = 70
    ws.column_dimensions["C"].width = 14

    ws.merge_cells("A1:C1")
    ws["A1"] = "Tổng — sau khi xong từng scenario, tick PASS ở đây"
    ws["A1"].font = Font(bold=True, size=14, color="1E1B4B")
    ws["A1"].fill = SCENARIO_FILL
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 28

    _write_header_row(ws, 3, ["Scenario", "Tiêu chí PASS", "Result"])
    rows = [
        (
            "Scenario 1 — Happy path",
            "Risk summary có citations click được, 6 step trace hoàn chỉnh, "
            "0 fatal errors.",
        ),
        (
            "Scenario 2 — Holder mismatch",
            "Có CRITICAL finding HOLDER_SSM_MISMATCH khi bank holder = BETA "
            "CORP còn SSM = ACME.",
        ),
        (
            "Scenario 3 — Income mismatch",
            "Có WARNING finding DECLARED_INCOME_VS_DEPOSITS với % gap đúng "
            "(>30%).",
        ),
        (
            "Scenario 4 — Evaluation harness",
            "scripts.evaluate chạy xong; 3 PASS đầu (extraction ≥90%, "
            "faithfulness 100%, latency p95 <180s).",
        ),
    ]
    row = 4
    for name, criterion in rows:
        ws.cell(row=row, column=1, value=name).alignment = WRAP
        ws.cell(row=row, column=2, value=criterion).alignment = WRAP
        ws.cell(row=row, column=3, value="").alignment = WRAP
        for col_idx in (1, 2, 3):
            ws.cell(row=row, column=col_idx).border = BORDER
        ws.row_dimensions[row].height = 40
        row += 1
    dv = DataValidation(type="list", formula1='"PASS,FAIL,SKIP"', allow_blank=True)
    dv.add(f"C4:C{row - 1}")
    ws.add_data_validation(dv)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    wb = Workbook()
    build_overview_sheet(wb.active)
    build_summary_sheet(wb)
    build_steps_sheet(
        wb,
        title="Pre-check",
        section_title="Trước khi bắt đầu — kiểm tra môi trường",
        intro=[
            "Đảm bảo môi trường đủ điều kiện trước khi chạy các scenarios.",
        ],
        steps=PRE_CHECK_STEPS,
    )
    build_steps_sheet(
        wb,
        title="Scenario 1 - Happy path",
        section_title=SCENARIO_1["title"],
        intro=SCENARIO_1["intro"],
        steps=SCENARIO_1["steps"],
    )
    build_steps_sheet(
        wb,
        title="Scenario 2 - Holder mismatch",
        section_title=SCENARIO_2["title"],
        intro=SCENARIO_2["intro"],
        steps=SCENARIO_2["steps"],
    )
    build_steps_sheet(
        wb,
        title="Scenario 3 - Income mismatch",
        section_title=SCENARIO_3["title"],
        intro=SCENARIO_3["intro"],
        steps=SCENARIO_3["steps"],
    )
    build_steps_sheet(
        wb,
        title="Scenario 4 - Evaluation",
        section_title=SCENARIO_4["title"],
        intro=SCENARIO_4["intro"],
        steps=SCENARIO_4["steps"],
    )
    build_steps_sheet(
        wb,
        title="Cleanup",
        section_title="Cleanup sau khi test xong",
        intro=["Tắt mọi process và container."],
        steps=CLEANUP_STEPS,
    )
    build_troubleshooting_sheet(wb)
    build_supervisor_qa_sheet(wb)

    out_path = Path(__file__).resolve().parents[2] / "docs" / "TESTING_GUIDE.xlsx"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    print(f"Workbook saved to: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
