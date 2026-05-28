# Hướng dẫn test manual hệ thống FYP

> Tài liệu này dành cho người chưa quen với hệ thống. Mỗi bước có
> giải thích "tại sao", lệnh chính xác cần chạy, và mô tả "kết quả
> đúng trông như thế nào". Nếu thực tế khác, đọc phần **Nếu sai**
> ngay dưới mỗi bước.

---

## Hệ thống làm gì? (đọc 1 phút)

Một loan officer ở ngân hàng Malaysia muốn cho SME (doanh nghiệp nhỏ và
vừa) vay tiền. Họ phải đọc nhiều loại giấy tờ tài chính (bank
statement, đăng ký kinh doanh SSM, báo cáo kiểm toán, tờ khai thuế Form
C) rồi viết một bản đánh giá rủi ro. Quá trình này mất 2-6 tuần.

Hệ thống này tự động:

1. **Đọc PDF** — parse text + tọa độ từng dòng.
2. **Trích số liệu** — extract revenue, balance, các director, tax,...
3. **Đối chiếu giữa các file** — ví dụ: tên trên SSM có khớp với tên
   chủ tài khoản trên bank statement không?
4. **Tính tỷ số tài chính** — DSR, D/E, NPM,...
5. **Đánh giá 5C** — Character / Capacity / Capital / Collateral / Conditions
   (LLM trả về có structured output).
6. **Sinh risk summary** — văn bản tự nhiên, mỗi câu **đều có citation
   `[chunk_id]`** mà loan officer click vào sẽ xem được dòng PDF gốc
   sinh ra câu đó (đây là yêu cầu FEATERS của BNM).

**Một số khái niệm:**

- **chunk_id**: một mẩu thông tin nhỏ trích từ PDF, có dạng
  `{document_id}:{kind}:{index}`. Ví dụ `bank_statement_2026-01-01:transaction:5`
  = transaction thứ 6 (0-indexed) của bank statement.
- **FEATERS**: 7 nguyên tắc BNM bắt buộc cho AI trong financial sector —
  Fairness, Ethics, Accountability, Transparency, Explainability,
  Reliability, Security. Project tập trung **Explainability** → mỗi
  claim phải traceable về document gốc.
- **5C**: framework cổ điển trong credit assessment — Character (đáng
  tin cậy?), Capacity (có cash flow trả nợ?), Capital (vốn chủ?),
  Collateral (tài sản thế chấp?), Conditions (ngành nghề/môi trường?).
- **Citation hallucination**: LLM trích dẫn một chunk_id không có
  thật. Hệ thống tự catch điều này, không cho nó vào output cuối.

---

## Trước khi bắt đầu — kiểm tra môi trường

### 0.1. Bạn cần có:

- [ ] **Docker Desktop** đang chạy (icon ở taskbar có màu xanh, không
      phải vàng/đỏ).
- [ ] **Python** với `uv` đã cài (Phase 1 đã cài rồi).
- [ ] **Node.js 20+** và `npm` (Phase 5 đã verify).
- [ ] **Gemini API key** trong file `backend/.env`. Nếu chưa có:
  - Mở https://aistudio.google.com → API keys → Create API key
  - Mở file [backend/.env](../backend/.env), tìm dòng
    `GEMINI_API_KEY=` và paste key vào sau dấu `=`. Không có dấu
    nháy, không có khoảng trắng.

### 0.2. Kiểm tra Docker đang chạy:

```bash
docker ps
```

**Kết quả đúng:** Hiện 1 bảng header `CONTAINER ID   IMAGE   COMMAND...`,
có thể có hoặc không có container nào ở dưới. Không có error.

**Nếu sai:** Nếu thấy `error during connect: ... docker daemon`, mở
Docker Desktop từ Start menu, đợi ~30 giây cho daemon khởi động, chạy
lại lệnh.

---

## Scenario 1 — Happy path: chạy đầy đủ với 4 loại document

Đây là kịch bản chính. Bạn sẽ upload 4 PDF (tất cả thuộc cùng 1 công ty
tên ACME), hệ thống chạy 6 step và trả về một bản summary với citations
click được.

### Bước 1.1. Khởi động infrastructure (Qdrant + Postgres)

```bash
cd c:/Tommy/Documents/GitHub/FYP
docker compose up -d qdrant postgres
```

**Tại sao:**
- **Qdrant** là vector database lưu các chunks đã embed (để semantic
  search sau này).
- **Postgres** lưu reasoning trail (mỗi step của agent được persist —
  audit trail theo FEATERS).

**Kết quả đúng:**
```
Container fyp-qdrant-1 Started
Container fyp-postgres-1 Started
```
(hoặc `Running` nếu đã chạy sẵn).

**Verify:**
```bash
curl http://localhost:6333/
```
Phải trả `{"title":"qdrant - vector search engine","version":"..."}`.

**Nếu sai:**
- Lỗi `port already in use`: có process khác đang chiếm cổng. Chạy
  `docker compose down` rồi `docker compose up -d qdrant postgres`
  lại.
- Lỗi `cannot find Docker daemon`: quay lại Bước 0.2.

---

### Bước 1.2. Khởi động backend (FastAPI)

Mở **terminal mới**, không đóng terminal hiện tại.

```bash
cd c:/Tommy/Documents/GitHub/FYP/backend
uv run uvicorn app.main:app --reload
```

**Kết quả đúng:** Cuối output có dòng:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [...] using WatchFiles
INFO:     Started server process [...]
INFO:     Application startup complete.
```

Backend giờ sẵn sàng ở `http://localhost:8000`. Để tab này chạy trong
suốt session test.

**Verify (trong terminal khác):**
```bash
curl http://localhost:8000/health
```
Trả `{"status":"ok"}`.

**Bonus:** Mở browser tới http://localhost:8000/docs để xem Swagger UI
(tự sinh) — bạn thấy mọi endpoint API.

**Nếu sai:**
- `ModuleNotFoundError`: bạn quên `uv sync` trước đó. Chạy
  `uv sync` rồi thử lại.
- `address already in use`: có process khác đang chiếm 8000. Mở task
  manager, kill process Python cũ, hoặc đổi port: `uvicorn app.main:app --port 8001`.

---

### Bước 1.3. Khởi động frontend (SvelteKit)

Mở **terminal thứ 3**.

```bash
cd c:/Tommy/Documents/GitHub/FYP/frontend
npm run dev
```

**Kết quả đúng:** Output kết thúc bằng:
```
  VITE v... ready in ... ms

  ➜  Local:   http://localhost:5173/
```

**Verify:** Mở http://localhost:5173/ trong browser. Bạn thấy:
- Header: "SME Loan Risk Analyser" + tag "Prototype" màu xanh.
- Card chính: "Upload SME application package" + drop zone có icon
  upload.

**Nếu sai:**
- `npm: command not found`: cài Node.js từ https://nodejs.org/
- Trang trống trắng: mở DevTools (F12) → Console tab → xem lỗi. Phổ
  biến nhất là Tailwind chưa build — restart `npm run dev`.

---

### Bước 1.4. Upload 4 PDF mẫu

Mình đã sinh sẵn 4 PDF synthetic ở `data/samples/`:

| File | Loại | Mô tả |
|---|---|---|
| `bank_statement_2026-01-01.pdf` | Bank statement | 1 tháng giao dịch của ACME |
| `ssm_202401000123.pdf` | SSM Form 9 | Đăng ký kinh doanh của ACME |
| `audited_financials_2025.pdf` | Audited financials | Báo cáo tài chính 2 năm (2024 + 2025) |
| `tax_return_YA2025.pdf` | Tax Form C | Tờ khai thuế 2025 |

**Cách upload:**

1. Trên trang web (http://localhost:5173/), trong drop zone, click chữ
   **"browse to select"** (chữ màu xanh indigo).
2. File picker mở ra. Đi tới folder
   `c:\Tommy\Documents\GitHub\FYP\data\samples\`.
3. **Chọn cả 4 file PDF** (Ctrl+Click từng file, hoặc Ctrl+A rồi bỏ
   chọn 4 file `.ground_truth.json`).
4. Click **Open**.

**Kết quả đúng:** Dưới drop zone hiện danh sách 4 file:
```
· bank_statement_2026-01-01.pdf    3.2 KB
· ssm_202401000123.pdf             2.4 KB
· audited_financials_2025.pdf      3.5 KB
· tax_return_YA2025.pdf            1.8 KB
```

Nút **"Analyse package"** (màu xanh indigo) sáng lên (không bị mờ).

**Nếu sai:** Nếu danh sách không hiện, kiểm tra DevTools console.

---

### Bước 1.5. Chạy phân tích — đây là step quan trọng nhất

Click **"Analyse package"**.

**Trong 30-60 giây tiếp theo:**

- Nút đổi thành **"Analysing…"** với spinner xoay.
- Đây là lúc agent chạy hết 6 step. Chậm nhất là 2 step gọi LLM:
  `assess_5c` (~13s) và `summarise` (~20s).
- Đừng đóng tab hay click lại.

**Bạn cũng có thể theo dõi backend terminal song song** — bạn sẽ thấy
log như:
```
INFO:     127.0.0.1:... - "POST /api/applications/analyse HTTP/1.1" 200 OK
```

**Kết quả đúng (sau ~40-60s):**

Trang xuất hiện thêm các cards mới (cuộn xuống):

#### Card 1: "Risk summary"
- Có **headline** (1 câu lớn) kết thúc bằng tag `[chunk_id]` màu xanh
  indigo (ví dụ `[bank_statement_2026-01-01:summary:0]`).
- Có **body** (vài câu) cũng có inline citations.
- Có **"Recommended human checks"** — list các thứ loan officer nên
  verify thủ công.

#### Card 2: "5C credit assessment"
- 5 cột: Character / Capacity / Capital / Collateral / Conditions.
- Mỗi cột có một **rating chip** (màu):
  - 🟢 `strong` / `adequate` / `healthy`
  - 🟡 `stretched`
  - 🔴 `weak` / `distressed`
  - ⚪ `insufficient data`
- Capital có thể là **adequate/healthy** vì có audited financials (khác
  với khi chỉ upload bank statement, nó sẽ là `insufficient_data`).
- Mỗi cột có chip evidence_chunk_ids click được.

#### Card 3: "Validation findings"
- Có thể trống (0 findings) vì 4 file synthetic đều consistent về tên
  ACME.
- Hoặc có 0-2 findings màu xám (INFO) / vàng (WARNING).

#### Card 4: "Bank-statement metrics"
- Hiển thị: Net change, Avg daily inflow/outflow, Deposits/Withdrawals,
  Closing balance.

#### Card 5: "Reasoning trail"
- 6 dòng theo thứ tự: parse → extract → validate → ratios → assess_5c
  → summarise.
- Mỗi dòng có thời gian (ms) và mô tả ngắn.
- `parse` và `validate` nhanh (~10ms). `assess_5c` và `summarise` chậm
  (10-30 giây).

**Nếu sai:**
- **Spinner chạy > 3 phút**: Có thể Gemini API trả slow hoặc đang
  rate-limit. Kiểm tra terminal backend xem có lỗi không. Nếu thấy
  `429 RESOURCE_EXHAUSTED`, đợi 1 phút.
- **Hiện error đỏ**: Đọc error message. Nếu là `GEMINI_API_KEY is not
  configured`, quay lại Bước 0.1 fill key.
- **Không có Risk summary**: Có thể LLM fail. Xem terminal backend, có
  thể có traceback.

---

### Bước 1.6. Click vào một citation để verify explainability

Đây là **điểm sáng của project** — bạn sẽ thấy mọi claim của AI đều
trace ngược được về dòng PDF gốc.

**Cách làm:**

1. Trong card **Risk summary**, tìm 1 tag xanh indigo trong headline
   hoặc body. Ví dụ tag có dạng `transaction:5` hoặc `summary:0`.
2. **Click vào tag đó.**

**Kết quả đúng:**

Một modal popup hiện ra với:
- **Tiêu đề "Source citation"** + chunk_id đầy đủ ở dưới.
- **Kind**: ví dụ `transaction` hoặc `summary`.
- **Page**: số trang trong PDF gốc.
- **Source text**: văn bản gốc — đây là cái mà AI đã dựa vào để viết
  câu trên.
- **Raw metadata** (collapsible): nhấp vào để xem thêm — debit, credit,
  balance, txn_date,...

Đóng modal bằng cách click ra ngoài hoặc nút **×**.

**Tại sao điều này quan trọng:**
- Nếu AI viết "ACME có doanh thu RM 1.8M" mà bạn click tag thấy source
  text là "Revenue: RM 1,800,000.00" → AI **không** hallucinate.
- Nếu có 1 chunk_id không tồn tại, hệ thống đã catch trước khi hiển
  thị (xem Card "Recoverable errors" ở cuối nếu có).

**Verify thêm:**
- Click 2-3 citations khác để confirm mỗi cái mở đúng source.
- Trong card 5C, click chips ở dưới từng dimension — cũng mở chunk
  detail.

---

### Bước 1.7. Check reasoning trail (audit trail)

Cuộn xuống card **"Reasoning trail"**. Bạn thấy:

```
14ms      parse       Parsed 4/4 PDFs; kinds: ['audited_financials', 'bank_statement', 'ssm_registration', 'tax_return']
9001ms    extract     Extracted 1 bank statement(s), 1 SSM, 1 audited financials, 1 tax return(s); upserted 19 chunks
0ms       validate    Validation: 0 intra-doc + 0 cross-doc finding(s)
0ms       ratios      Computed bank metrics for 1 statement(s); financial ratios for 1 audited set(s)
13550ms   assess_5c   5C assessment: Character=adequate, Capacity=strong, Capital=adequate, ...
19300ms   summarise   Generated risk summary with 5 citation(s)
```

**Đây là audit trail FEATERS** — mọi step đều có timestamp và summary,
được lưu vào Postgres checkpointer.

**Kết quả đúng cần nhìn vào:**
- Đủ 6 step, không thiếu cái nào.
- `parse` detect đúng **4 kinds** (xem dòng `kinds: [...]`).
- `extract` upsert >15 chunks (synthetic data chỉ có ~19).
- `validate` báo 0 findings cho synthetic (vì data đã consistent).
- `summarise` có >= 1 citation.

---

## Scenario 2 — Edge case: cross-doc validation catch tên không khớp

Đây là scenario chứng minh **cross-doc validation hoạt động** — proposal
section 5 nói đây là điểm khác biệt so với prior work.

### Bước 2.1. Sinh ra một bank statement "giả" của công ty khác

Bank statement gốc của ACME. Bây giờ mình sẽ sinh thêm 1 bank
statement nhưng đổi tên holder thành **BETA CORP** (không khớp với SSM).

Mở **terminal mới** (giữ backend + frontend đang chạy):

```bash
cd c:/Tommy/Documents/GitHub/FYP/backend
uv run python -c "
from pathlib import Path
from app.ingestion.synthetic import GeneratorConfig, generate
cfg = GeneratorConfig(
    seed=99,
    account_holder='BETA CORP SDN BHD',
    n_transactions=10,
)
pdf, gt = generate(cfg, Path('../data/samples'))
print(f'Sinh xong: {pdf}')
"
```

**Kết quả đúng:** Output báo
`Sinh xong: ..\data\samples\bank_statement_2026-01-01.pdf` (file gốc bị
ghi đè — đây là chủ ý).

### Bước 2.2. Upload lại với bank statement "lạ"

Quay lại trang http://localhost:5173/.

1. **Refresh trang** (Ctrl+R) — quan trọng để clear state cũ.
2. Click **"browse to select"**, chọn 4 file (bank statement giờ là
   bản BETA CORP):
   - bank_statement_2026-01-01.pdf (BETA CORP)
   - ssm_202401000123.pdf (ACME)
   - audited_financials_2025.pdf (ACME)
   - tax_return_YA2025.pdf (ACME)
3. Click **Analyse package**, chờ ~40-60s.

**Kết quả đúng:**

Card **"Validation findings"** phải xuất hiện và có ít nhất 1 finding
**màu đỏ** (CRITICAL) với code `HOLDER_SSM_MISMATCH`:

> Bank statement holder 'BETA CORP SDN BHD' does not match any
> registered company name on the SSM form(s): ACME TRADING SDN BHD.

Click các citation tags trong finding này — chúng đưa bạn về:
- chunk `summary:0` của bank statement (chứng cứ holder là BETA CORP)
- chunk `summary:0` của SSM (chứng cứ tên đăng ký là ACME)

**Tại sao đây là kết quả tốt:**
- Hệ thống tự catch identity mismatch — đây là vấn đề shell company /
  identity fraud trong thực tế.
- Severity CRITICAL → loan officer thấy ngay phải reject hoặc verify
  thêm.

**Bonus:** Đọc thử **Risk summary** — nó có nhắc đến mismatch không?
Một LLM tốt sẽ thận trọng hơn khi rate 5C (ví dụ Character có thể bị
rate weak).

### Bước 2.3. Restore lại file gốc

```bash
cd c:/Tommy/Documents/GitHub/FYP/backend
uv run python -c "
from pathlib import Path
from app.ingestion.synthetic import GeneratorConfig, generate
pdf, gt = generate(GeneratorConfig(), Path('../data/samples'))
print(f'Restored: {pdf}')
"
```

---

## Scenario 3 — Edge case: declared income không khớp deposits

Tax return khai income RM 1.75M; bank statement chỉ thể hiện inflow
RM 90k/tháng (tức ~RM 1.08M/năm). Gap >30% phải bị flag WARNING.

### Bước 3.1. Sinh tax return với income "lạ"

```bash
cd c:/Tommy/Documents/GitHub/FYP/backend
uv run python -c "
from decimal import Decimal
from pathlib import Path
from app.ingestion.tax_synthetic import TaxReturnGeneratorConfig, generate
cfg = TaxReturnGeneratorConfig(
    gross_business_income=Decimal('5000000.00'),  # over-declared so gap > 30%
    chargeable_income=Decimal('1200000.00'),
    tax_payable=Decimal('288000.00'),
)
pdf, gt = generate(cfg, Path('../data/samples'))
print(f'Sinh xong: {pdf}')
"
```

### Bước 3.2. Upload và xem finding

Refresh trang web, upload lại 4 file (giờ tax return có income hơi
"lạ"), click Analyse.

**Kết quả đúng:** Card Validation findings có 1 finding **màu vàng**
(WARNING) với code `DECLARED_INCOME_VS_DEPOSITS`:

> Tax return declares gross business income RM 5000000.00, but
> annualised bank credits suggest RM 1095677.97 (78% gap). Verify
> whether the gap reflects non-business deposits, seasonality, or
> under-declaration.

Citations chỉ về tax_return summary và bank_statement summary.

### Bước 3.3. Restore tax return gốc

```bash
cd c:/Tommy/Documents/GitHub/FYP/backend
uv run python -c "
from pathlib import Path
from app.ingestion.tax_synthetic import TaxReturnGeneratorConfig, generate
pdf, gt = generate(TaxReturnGeneratorConfig(), Path('../data/samples'))
print(f'Restored: {pdf}')
"
```

---

## Scenario 4 — Chạy evaluation harness (FYP grading metrics)

Đây là script tự đo 4 metric mà proposal section 12 cam kết:
- Extraction accuracy ≥ 90%
- Citation faithfulness = 0 hallucinations
- Latency p95 < 180s
- SUS template ready (cần user study riêng)

### Bước 4.1. Chạy script

Trong terminal mới (giữ backend đang chạy):

```bash
cd c:/Tommy/Documents/GitHub/FYP/backend
uv run python -m scripts.evaluate --runs 2
```

**Tham số `--runs 2`** = chạy graph 2 lần để đo latency p50/p95. Càng
nhiều runs càng chính xác (nhưng càng lâu).

**Tổng thời gian:** ~3-5 phút (4 doc types × 2 runs × ~50s mỗi lần).

### Bước 4.2. Đọc report

**Kết quả đúng:** Cuối output là một report dạng:

```
======================================================================
FYP EVALUATION REPORT
Generated: 2026-MM-DDTHH:MM:SS+00:00
======================================================================

[1] EXTRACTION ACCURACY
----------------------------------------------------------------------
  bank_statement             79/79   fields (100.00%) PASS (>90%)
  ssm_registration           13/13   fields (100.00%) PASS (>90%)
  audited_financials         32/32   fields (100.00%) PASS (>90%)
  tax_return                  6/6    fields (100.00%) PASS (>90%)
  overall avg              100.00%

[2] CITATION FAITHFULNESS
----------------------------------------------------------------------
  Citations valid:        N/N (100.0%)
  Sentence coverage:      ~50%
  PASS (0 hallucinations)

[3] LATENCY
----------------------------------------------------------------------
  End-to-end p50:   ~50.00s
  End-to-end p95:   ~60.00s
  Per-node p50:
    parse        0.01s
    extract      9.00s
    validate     0.00s
    ratios       0.00s
    assess_5c   13.00s
    summarise   20.00s
  PASS (<180s)

[4] USABILITY (SUS)
----------------------------------------------------------------------
  Run the SUS questionnaire with at least 5 loan-officer participants.
  Score each response with `app.evaluation.sus.score_sus_responses`.
  Target: mean SUS score > 70 ('Good').
======================================================================
```

**3 PASS đầu phải đạt được.** Nếu fail:
- **Extraction <90%**: có mismatch ở synthetic generator vs extractor.
  Đọc kỹ phần "mismatch:" sau từng doc type.
- **Faithfulness <100%**: LLM hallucinate chunk_ids. Đọc dòng "Invalid".
- **Latency p95 ≥ 180s**: Gemini đang chậm hoặc rate limit. Chạy lại
  vào lúc khác.

### Bước 4.3. (Optional) Dump JSON cho FYP report

```bash
cd c:/Tommy/Documents/GitHub/FYP/backend
uv run python -m scripts.evaluate --runs 3 --json eval_report.json
```

File `eval_report.json` chứa full machine-readable data — paste vào
final report làm appendix.

---

## Cleanup sau khi test

```bash
# Stop frontend: Ctrl+C ở terminal frontend.
# Stop backend: Ctrl+C ở terminal backend.

# Stop containers:
cd c:/Tommy/Documents/GitHub/FYP
docker compose down

# (Optional) Xóa volume data nếu muốn fresh start lần sau:
# docker compose down -v
```

---

## Checklist tổng — đánh dấu sau mỗi scenario

- [ ] **Scenario 1**: Upload 4 PDFs ACME → có Risk summary với citations
      click được, 6 step trace hoàn chỉnh, 0 errors.
- [ ] **Scenario 2**: Đổi bank statement thành BETA CORP → có
      CRITICAL finding `HOLDER_SSM_MISMATCH`.
- [ ] **Scenario 3**: Đổi tax income lên RM 5M → có WARNING finding
      `DECLARED_INCOME_VS_DEPOSITS` với % gap đúng.
- [ ] **Scenario 4**: `scripts.evaluate` chạy xong, 3 PASS đầu đều
      đạt được.

Nếu cả 4 đều ✓, hệ thống đã đáp ứng đủ proposal commitments — bạn sẵn
sàng cho Phase 7 (write-up).

---

## Phụ lục — Troubleshooting nhanh

| Triệu chứng | Cách xử lý |
|---|---|
| "ECONNREFUSED localhost:8000" trong browser console | Backend chưa khởi động hoặc đã crash. Quay lại Bước 1.2. |
| Modal citation hiện "Chunk lookup failed (404)" | Qdrant đã bị wipe giữa lần ingest. Refresh trang, upload lại. |
| `429 RESOURCE_EXHAUSTED` ở terminal backend | Gemini free tier = 1500 req/day. Đã hit limit, chờ 24h hoặc đổi key. |
| Trang web load nhưng UI vỡ (không có style) | Tailwind chưa build. Trong terminal frontend chạy lại `npm run dev`. |
| Sample PDF không còn đúng (do edge-case test) | Re-sinh tất cả 4 file bằng `python -m scripts.smoke_agent` ở backend hoặc 3 lệnh Python ở Scenario 2.3 / 3.3. |
| Mất API key | Tạo key mới ở aistudio.google.com → API keys, paste vào `backend/.env`, restart backend. |
| Postgres container không khởi động | Check `docker logs fyp-postgres-1`. Thường là conflict cổng 5432 với Postgres local. Stop Postgres local. |

---

## Hỏi đáp với supervisor — phòng trường hợp bị hỏi

**Q: Tại sao em không dùng Amazon Bedrock như proposal viết ban đầu?**
A: Free tier giới hạn ở Bedrock + không có AWS credit. Đã design provider-
agnostic layer (`app/core/llm.py`) nên swap Gemini ↔ Bedrock chỉ cần
thay implementation, agent code không đổi.

**Q: Tại sao chỉ test với synthetic data?**
A: Real SME documents là confidential, chứa NRIC + tax info. Synthetic
data có ground truth chính xác để đo extraction accuracy. Phase
future work: validate với real anonymised data từ supervisor.

**Q: FEATERS Explainability cụ thể thể hiện ở đâu?**
A: Mỗi claim trong risk summary có inline `[chunk_id]` citation —
loan officer click vào xem dòng PDF gốc. Hệ thống verify tất cả
citations against ingestion-produced allow-list — nếu LLM
hallucinate chunk_id, bị catch và logged vào recoverable errors.

**Q: 5C Capital tại sao luôn là `insufficient_data` khi chỉ upload bank
statement?**
A: Capital đánh giá vốn chủ (equity) — chỉ có trong audited financials.
Bank statement không bộc lộ thông tin này. Đây là **đúng epistemic
stance** — thà rate insufficient_data còn hơn LLM đoán bừa.

**Q: Reasoning chain lưu ở đâu? Có thể audit lại không?**
A: Postgres checkpointer (langgraph-checkpoint-postgres). Mỗi state
sau từng node được persist với thread_id. Có thể replay 1 application
sau này.
