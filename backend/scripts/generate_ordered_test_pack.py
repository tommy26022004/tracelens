from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
from pathlib import Path

import pymupdf
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

COMPANY = "LOTUS TEST TRADING SDN BHD"
FINANCIAL_ROWS = [
    ("Revenue", "revenue", 120000, 100000, 1),
    ("Cost of Sales", "cost_of_sales", 60000, 50000, 1),
    ("Gross Profit", "gross_profit", 60000, 50000, 1),
    ("Operating Expenses", "operating_expenses", 30000, 26000, 1),
    ("EBIT", "ebit", 30000, 24000, 1),
    ("Interest Expense", "interest_expense", 3000, 2000, 1),
    ("Net Profit", "net_profit", 21600, 17600, 1),
    ("Cash from Operations", "cash_from_operations", 28000, 22000, 1),
    ("Current Assets", "current_assets", 80000, 65000, 2),
    ("Non-Current Assets", "non_current_assets", 120000, 115000, 2),
    ("Current Liabilities", "current_liabilities", 40000, 35000, 2),
    ("Non-Current Liabilities", "non_current_liabilities", 60000, 55000, 2),
    ("Total Equity", "total_equity", 100000, 90000, 2),
]


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def heading(document: canvas.Canvas, title: str, page: int = 1) -> None:
    document.setFillColorRGB(0.04, 0.12, 0.23)
    document.setFont("Helvetica-Bold", 15)
    document.drawString(40, 794, title)
    document.setFont("Helvetica", 9)
    document.drawString(40, 773, "SYNTHETIC TEST DATA - NOT AN OFFICIAL FINANCIAL DOCUMENT")
    document.setStrokeColorRGB(0.7, 0.75, 0.8)
    document.line(40, 760, 555, 760)
    document.setFont("Helvetica", 8)
    document.drawString(40, 25, f"Academic fixture | fictitious company and identifiers | Page {page}")


def lines(document: canvas.Canvas, values: list[str], start: int = 725) -> None:
    document.setFont("Helvetica", 10)
    for index, value in enumerate(values):
        document.drawString(40, start - index * 23, value)


def bank(path: Path, holder: str = COMPANY, wrong_closing: bool = False) -> dict:
    document = canvas.Canvas(str(path), pagesize=A4)
    heading(document, "SYNTHETIC BANK - STATEMENT OF ACCOUNT")
    fields = {"bank_name": "SYNTHETIC BANK", "account_holder": holder,
              "account_number": "TEST-ACCOUNT-001", "statement_period_start": "2025-01-01",
              "statement_period_end": "2025-01-31", "opening_balance": "10000.00",
              "total_credits": "10000.00", "total_debits": "6000.00",
              "closing_balance": "14900.00" if wrong_closing else "14000.00"}
    lines(document, ["Bank Name: SYNTHETIC BANK", f"Account Holder: {holder}",
                     "Account Number: TEST-ACCOUNT-001", "Statement Period: 01 Jan 2025 - 31 Jan 2025"])
    document.setFont("Helvetica-Bold", 9)
    for position, label in [(40, "Date"), (112, "Description"), (365, "Debit"), (445, "Credit"), (505, "Balance")]:
        document.drawString(position, 600, label)
    balance = 10000
    transactions = []
    for index in range(10):
        credit, debit = (2000, None) if index % 2 == 0 else (None, 1200)
        balance += (credit or 0) - (debit or 0)
        day = index * 3 + 1
        description = f"{'CUSTOMER RECEIPT' if credit else 'OPERATING PAYMENT'} {index + 1:02}"
        document.setFont("Helvetica", 9)
        position = 574 - index * 23
        document.drawString(40, position, f"{day:02}/01/2025")
        document.drawString(112, position, description)
        if debit:
            document.drawRightString(418, position, f"{debit:,.2f}")
        if credit:
            document.drawRightString(495, position, f"{credit:,.2f}")
        document.drawRightString(555, position, f"{balance:,.2f}")
        transactions.append({"txn_date": f"2025-01-{day:02}", "description": description,
                             "debit": f"{debit:.2f}" if debit else None,
                             "credit": f"{credit:.2f}" if credit else None,
                             "balance": f"{balance:.2f}", "page": 1})
    lines(document, [f"{label}: RM {float(fields[key]):,.2f}" for label, key in
                     [("Opening Balance", "opening_balance"), ("Total Credits", "total_credits"),
                      ("Total Debits", "total_debits"), ("Closing Balance", "closing_balance")]], 285)
    document.save()
    return {"kind": "bank_statement", "pages": 1, "fields": fields, "field_pages": {key: 1 for key in fields},
            "transactions": transactions, "arithmetic_expected_closing": "14000.00"}


def ssm(path: Path) -> dict:
    document = canvas.Canvas(str(path), pagesize=A4)
    heading(document, "SSM REGISTRATION - SYNTHETIC FORM 9")
    fields = {"company_name": COMPANY, "registration_number": "SYNTHETIC-REG-001",
              "incorporation_date": "2020-01-15", "company_type": "SDN BHD",
              "business_address": "1 Fictional Test Road, Kuala Lumpur",
              "paid_up_capital": "50000.00"}
    lines(document, ["SURUHANJAYA SYARIKAT MALAYSIA - TEST FACSIMILE",
                     f"Company Name: {COMPANY}", "Registration Number: SYNTHETIC-REG-001",
                     "Date of Incorporation: 15 January 2020", "Company Type: SDN BHD",
                     "Business Address: 1 Fictional Test Road, Kuala Lumpur", "Paid-Up Capital: RM 50,000.00",
                     "Directors:", "1. TEST DIRECTOR - NRIC: TEST-ID-001 - Role: Director"])
    document.save()
    return {"kind": "ssm_registration", "pages": 1, "fields": fields, "field_pages": {key: 1 for key in fields}}


def financials(path: Path, thousands: bool = False) -> dict:
    document = canvas.Canvas(str(path), pagesize=A4)
    periods = {"2025": {}, "2024": {}}
    field_pages = {}
    for page in [1, 2]:
        heading(document, COMPANY, page)
        lines(document, ["AUDITED FINANCIAL STATEMENTS - FICTIONAL TEST FIXTURE",
                         "For the financial year ended 31 December 2025",
                         "Audited by: FICTIONAL TEST AUDITOR (NO REAL AUDIT)",
                         "Amounts in RM'000 (multiply by 1,000)" if thousands else "Amounts in RM"])
        document.setFont("Helvetica-Bold", 11)
        document.drawString(40, 610, "INCOME STATEMENT AND CASH FLOW" if page == 1 else "BALANCE SHEET")
        document.drawRightString(420, 584, "2025")
        document.drawRightString(555, 584, "2024")
        row_index = 0
        for label, key, current, prior, source_page in FINANCIAL_ROWS:
            if source_page != page:
                continue
            position = 557 - row_index * 28
            document.setFont("Helvetica", 10)
            document.drawString(40, position, label)
            divisor = 1000 if thousands else 1
            document.drawRightString(420, position, f"{current / divisor:,.2f}")
            document.drawRightString(555, position, f"{prior / divisor:,.2f}")
            periods["2025"][key] = f"{current:.2f}"
            periods["2024"][key] = f"{prior:.2f}"
            field_pages[key] = page
            row_index += 1
        document.showPage()
    document.save()
    return {"kind": "audited_financials", "pages": 2, "company_name": COMPANY,
            "display_unit": "RM'000" if thousands else "RM", "canonical_unit": "RM",
            "periods": periods, "field_pages": field_pages,
            "expected_ratios_2025": {"current_ratio": "2.0000", "debt_to_equity": "1.0000",
                                     "net_profit_margin_fraction": "0.1800", "interest_coverage": "10.0000"},
            "ratio_note": "Independent arithmetic only. DSR omitted: no actual annual debt-service amount supplied."}


def tax(path: Path, gross: int = 120000) -> dict:
    document = canvas.Canvas(str(path), pagesize=A4)
    heading(document, "FORM C - SYNTHETIC TAX RETURN")
    fields = {"company_name": COMPANY, "tax_reference_number": "TEST-TAX-001", "year_of_assessment": 2025,
              "gross_business_income": f"{gross:.2f}", "chargeable_income": "27000.00", "tax_payable": "5400.00"}
    lines(document, ["LEMBAGA HASIL DALAM NEGERI - TEST FACSIMILE", f"Company Name: {COMPANY}",
                     "Tax Reference Number: TEST-TAX-001", "Year of Assessment: 2025",
                     f"Gross Business Income: RM {gross:,.2f}", "Chargeable Income: RM 27,000.00",
                     "Tax Payable: RM 5,400.00", "Fixture amounts only; not a real tax calculation or filing."])
    document.save()
    return {"kind": "tax_return", "pages": 1, "fields": fields, "field_pages": {key: 1 for key in fields}}


def management(path: Path) -> dict:
    document = canvas.Canvas(str(path), pagesize=A4)
    for page in [1, 2, 3]:
        heading(document, "MANAGEMENT ACCOUNTS - SYNTHETIC", page)
        values = [f"Company Name: {COMPANY}", "Reporting period: January 2025"]
        if page == 3:
            values += ["Customer concentration: Alpha Retail represents 65% of sales.",
                       "Supplier dependence: Beta Supplies provides 70% of purchases.",
                       "No collateral valuation is included in this management report."]
        else:
            values += ["Administrative cover and reporting scope." if page == 1 else "Accounting policy: amounts in RM.",
                       "Operational risk details are provided on page 3."]
        lines(document, values)
        document.showPage()
    document.save()
    return {"kind": "management_accounts", "pages": 3,
            "facts": [{"text": "Alpha Retail represents 65% of sales", "page": 3},
                      {"text": "Beta Supplies provides 70% of purchases", "page": 3}]}


def build(root: Path) -> list[dict]:
    if root.exists():
        raise FileExistsError(f"Refusing to overwrite existing test data: {root}")
    root.mkdir(parents=True)
    cases = [
        ("01_history", "HIS-001/002", [], "Kiểm tra trang lịch sử: tạo test not_run, refresh/restart và export. Sau đó dùng PDF của 02 để kiểm tra tự lưu lần chạy.", []),
        ("02_bank_extraction", "EXT-001", ["bank"], "Đối chiếu metadata, 10 giao dịch và bốn tổng tiền với ground truth. Thiếu các loại hồ sơ khác là có chủ đích.", []),
        ("03_ssm_extraction", "EXT-SSM", ["ssm"], "Đối chiếu tên, đăng ký, ngày thành lập và vốn góp; không yêu cầu đánh giá khoản vay đầy đủ.", []),
        ("04_financials_and_ratios", "EXT-002/RAT-001", ["financials"], "Đối chiếu từng năm và trang; kiểm tra bốn tỷ lệ trong ground truth. Không coi DSR ước lượng là nghĩa vụ nợ thật.", []),
        ("05_tax_extraction", "EXT-TAX", ["tax"], "Đối chiếu năm đánh giá và ba số tiền. Thuế phải nộp là dữ liệu fixture, không phải tư vấn thuế.", []),
        ("06_clean_package", "VAL-003", ["bank", "ssm", "financials", "tax"], "Hồ sơ nhất quán để kiểm tra cảnh báo nhầm. Chỉ có một tháng sao kê: cảnh báo thiếu lịch sử là hợp lệ; không yêu cầu mọi 5C phải strong.", []),
        ("07_balance_mismatch", "VAL-001", ["bad_bank"], "Chỉ thay số dư cuối khai báo: 14,900 thay vì 14,000. Máy phải trích đúng số ghi trên PDF và cảnh báo phép tính; không tự sửa thành 14,000.", ["BALANCE_ARITHMETIC"]),
        ("08_identity_mismatch", "VAL-002", ["other_bank", "ssm"], "Chủ tài khoản ORCHID TEST SERVICES khác LOTUS trên SSM. Hiển thị hai nguồn; không kết luận gian lận.", ["HOLDER_SSM_MISMATCH"]),
        ("09_revenue_mismatch", "VAL-REVENUE", ["financials", "bad_tax"], "Chỉ đổi gross business income trong thuế thành 60,000; audited revenue vẫn 120,000. Cảnh báo chênh lệch, không tự kết luận trốn thuế.", ["AUDITED_VS_TAX_REVENUE"]),
        ("10_missing_tax", "MISS-001", ["bank", "ssm", "financials"], "Chủ đích không có tờ khai thuế. Cần cảnh báo thiếu tài liệu; không phát minh dữ liệu thuế.", ["MISSING_CORE_DOCUMENTS"]),
        ("11_evidence_page_3", "SRC-001/RAG-001", ["bank", "ssm", "financials", "tax", "management"], "Management accounts có thật: hai dữ kiện ở trang 3. Nếu retrieval trượt phải nói chưa tìm được bằng chứng, không nói chưa upload. Citation cho 65%/70% phải về trang 3.", []),
        ("12_scanned_bank", "OCR-001", ["scan"], "Sao kê dạng ảnh, không có text layer. Trích đúng bằng OCR hoặc báo cần OCR/chưa hỗ trợ; không coi kết quả rỗng là phân tích thành công.", []),
        ("13_corrupt_pdf", "ERR-001", ["corrupt"], "File .pdf cố ý hỏng. Phải báo lỗi rõ và không đưa ra kết luận tài chính dựa trên file này.", []),
        ("14_units_rm_thousands", "UNIT-001", ["thousands"], "Bảng ghi RM'000: Revenue hiển thị 120.00 nhưng giá trị RM đúng là 120,000. Các ratio không đổi nên ratio đúng không chứng minh extraction đúng.", []),
        ("15_baseline_comparison", "CMP-001", [], "Dùng lại 06 và 11, không copy thêm PDF. Cùng model và prompt đầu ra tương đương; ghi thời gian, chi phí, lỗi, chất lượng citation. Đây là development comparison, không phải holdout.", []),
        ("16_large_package_32", "LOAD-001", [], "Dùng bộ giữ nguyên tại data/realistic_scenarios/realistic_01 (32 PDF). Không upload README/ground truth. Đo thời gian, lỗi và kiểm chứng; 32/32 processed không phải accuracy.", []),
    ]
    manifest = []
    for name, test_id, kinds, instruction, expected_codes in cases:
        folder = root / name
        folder.mkdir()
        upload = folder / "upload"
        upload.mkdir()
        truth = {"test_id": test_id, "system_test_status": "not_run", "dataset_family": "lotus-development-v1",
                 "ground_truth_method": "Authored fixture constants, not extracted system output; manually verify before scoring.",
                 "expected_primary_codes": expected_codes, "instructions": instruction, "documents": {}}
        for kind in kinds:
            filename = {"bad_bank": "bank.pdf", "other_bank": "bank.pdf", "bad_tax": "tax.pdf",
                        "thousands": "financials_rm_thousands.pdf", "scan": "bank_scanned.pdf",
                        "corrupt": "intentionally_corrupt.pdf"}.get(kind, f"{kind}.pdf")
            path = upload / filename
            if kind in {"bank", "bad_bank", "other_bank"}:
                expected = bank(path, "ORCHID TEST SERVICES SDN BHD" if kind == "other_bank" else COMPANY, kind == "bad_bank")
            elif kind == "ssm":
                expected = ssm(path)
            elif kind in {"financials", "thousands"}:
                expected = financials(path, kind == "thousands")
            elif kind in {"tax", "bad_tax"}:
                expected = tax(path, 60000 if kind == "bad_tax" else 120000)
            elif kind == "management":
                expected = management(path)
            elif kind == "scan":
                source = root / "02_bank_extraction/upload/bank.pdf"
                expected = copy.deepcopy(json.loads((root / "02_bank_extraction/ground_truth.json").read_text(encoding="utf-8"))["documents"]["bank.pdf"])
                with pymupdf.open(source) as original, pymupdf.open() as scanned:
                    for page in original:
                        target = scanned.new_page(width=page.rect.width, height=page.rect.height)
                        target.insert_image(target.rect, stream=page.get_pixmap(dpi=140).tobytes("png"))
                    scanned.save(path)
                expected["image_only"] = True
            else:
                path.write_bytes(b"INTENTIONALLY INVALID PDF - SYNTHETIC ERROR HANDLING FIXTURE\n")
                expected = {"kind": "invalid", "pages": None, "expected": "explicit processing failure"}
            expected["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            truth["documents"][filename] = expected
        write_json(folder / "ground_truth.json", truth)
        (folder / "HUONG_DAN.md").write_text(
            f"# {name} — {test_id}\n\n**Trạng thái: CHƯA CHẠY TEST HỆ THỐNG.**\n\n{instruction}\n\n"
            "## Cách thực hiện\n1. Đọc PDF và ground_truth.json trước; xác nhận đáp án thủ công.\n"
            "2. Chỉ upload PDF trong upload/. Không upload ground truth hoặc hướng dẫn.\n"
            "3. Ghi application ID, phiên bản, model và cấu hình.\n"
            "4. Đối chiếu giá trị, năm, đơn vị, trang và cảnh báo; ghi cả lỗi bỏ sót/cảnh báo nhầm.\n"
            "5. Điền observations.csv rồi thêm Test result trong Development History, kèm đường dẫn bằng chứng.\n"
            "6. Nếu fail, tạo bug và linked follow-up sau sửa; không thay đáp án để khớp kết quả máy.\n\n"
            "Các case chỉ có một vài loại tài liệu có thể có cảnh báo thiếu hồ sơ hợp lệ. "
            "Expected codes là mục tiêu chính, không phải danh sách toàn bộ cảnh báo được phép. "
            "Không có rating tín dụng 'đúng' cố định trong fixture.\n", encoding="utf-8")
        with (folder / "observations.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["test_id", "application_id", "document", "field_or_claim", "expected", "actual", "source_page", "status", "notes"])
            writer.writerow([test_id, "", "", "", "See ground_truth.json", "", "", "not_run", ""])
        manifest.append({"folder": name, "test_id": test_id, "pdf_count": len(kinds), "status": "not_run"})
    write_json(root / "test_plan.json", manifest)
    (root / "BAT_DAU_O_DAY.md").write_text(
        "# Bộ test có thứ tự — development v1\n\n"
        "Đi theo thư mục 01 đến 16. Bắt đầu 01 (kiểm tra history), rồi 02 (sao kê 1 trang/10 giao dịch). "
        "Mỗi lần chỉ upload PDF trong upload/ của một case. Các thư mục 01, 15, 16 chỉ có hướng dẫn và tham chiếu, không có PDF riêng.\n\n"
        "Ground truth được viết từ các hằng số dùng tạo PDF, KHÔNG lấy từ kết quả extractor. Cần tự xác nhận trước khi chấm. "
        "Tất cả dữ liệu giả lập, không phải tài liệu chính thức hay chứng nhận kiểm toán. Không có file nào được gửi vào hệ thống phân tích hoặc dịch vụ AI khi tạo bộ này.\n\n"
        "## Giới hạn\nĐây là một họ dữ liệu phát triển với các biến thể kiểm soát, không phải nhiều doanh nghiệp độc lập, "
        "không phải holdout và không đủ để chứng minh khả năng tổng quát. Không tách các biến thể này sang bộ đánh giá cuối. "
        "Sau vòng đầu cần bổ sung bố cục, doanh nghiệp, số âm và mẫu số bằng 0; kiểm thử API timeout/concurrency cần test kỹ thuật, không chỉ PDF.\n\n"
        "07/08/09 thay từng lỗi nguồn riêng. 12 là ảnh scan thật không có text layer. 13 cố ý KHÔNG phải PDF hợp lệ. "
        "14 kiểm tra đổi đơn vị có thể chưa được hỗ trợ: fail là kết quả hợp lệ cần ghi nhận. "
        "Một tháng sao kê không đại diện cả năm; annualisation chỉ là giả định của hệ thống cần kiểm tra, không phải doanh thu thực tế.\n\n"
        + "\n".join(f"- {item['folder']}: {item['test_id']} ({item['pdf_count']} PDF)" for item in manifest), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(build(arguments.output), indent=2))
