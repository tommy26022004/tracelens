# FYP học kỳ 2 — Kế hoạch tổng thể

Ngày lập: **13/09/2026**. Trạng thái: **đã triển khai T01/T02 và phần lưu PDF/viewer của T03; các giai đoạn còn lại chưa hoàn thành**.

Mục tiêu: hoàn thiện prototype phân tích hồ sơ vay SME có số liệu kiểm tra được, nguồn bằng chứng rõ ràng, human review và bộ đánh giá tái lập phục vụ demo/Report 2.

Report 1 đã nộp theo xác nhận của chủ dự án. Dùng bản này làm điểm bắt đầu khi quay lại; các trạng thái tháng 5 trong PROGRESS.md và mô tả tháng 6 trong PROJECT_CONTEXT_HANDOFF.md có phần đã cũ.

## 1. Nhớ lại hệ thống trong 5 phút

Loan officer tải một bộ PDF của một SME lên; hệ thống chạy sáu bước:

```text
Upload PDF → Parse → Extract → Validate → Ratios → Assess 5C → Summarise
                                                               ↓
                                        Dashboard → Human review
```

| Thành phần | Vai trò |
|---|---|
| SvelteKit, frontend/ | Upload, theo dõi job, inventory, summary, 5C, findings, citation modal |
| FastAPI, backend/app/api/ | Nhận file, tạo job, trả kết quả và truy nguồn |
| LangGraph, backend/app/agent/ | Sáu node tuần tự; chưa phải agent tự chọn tool theo kiểu ReAct |
| Ingestion | Đọc PDF, phân loại, trích dữ liệu, chia chunk, tạo inventory |
| Validation và ratios | Kiểm tra nhất quán và tính toán bằng code |
| Qdrant | Lưu chunk/vector; có hàm search và lookup citation |
| Gemini | Sinh đánh giá 5C và summary; có fallback khi lần gọi đầu thất bại |
| PostgreSQL, Redis | Đã chạy trong Docker; job/result hiện chưa được lưu bền vững qua chúng |

Giữ stack, provider abstraction và sáu node hiện có. Tích hợp retrieval bên trong các bước đánh giá/tóm tắt trước khi cân nhắc đổi topology.

## 2. Baseline đã kiểm tra ngày 13/09/2026

- Cả năm Docker service đang chạy; backend, PostgreSQL và Redis báo healthy.
- Backend health API trả `{"status":"ok"}`.
- Backend: **73 passed, 1 skipped**, **24.77 giây**; một cảnh báo deprecation từ dependency Google GenAI.
- Test skip là live-Qdrant integration. Test full graph hiện dùng fake LLM/vector store.
- Frontend `npm run check`: **0 errors, 0 warnings**.
- Chưa chạy lại live Gemini, browser upload hoặc live-Qdrant integration trong lần lập kế hoạch này.
- Trước khi thêm tài liệu này, Git có **57 mục thay đổi/untracked**: 33 tracked files bị sửa và 24 untracked entries. Đây là công việc có sẵn cần bảo toàn.

### Dữ liệu và phạm vi hiện có

- Generator có 10 controlled scenarios, phục vụ các tình huống đã biết và ground truth.
- Có 3 realistic workload scenarios với test: khỏe mạnh; thiếu tháng/trùng file; audited–tax mismatch.
- Mỗi realistic package có **32 PDF / 337 trang**.
- Bốn loại trích cấu trúc: bank statements, audited financials, SSM, tax returns.
- Ba loại mới chỉ index theo trang: management accounts, cash-flow forecast, facility statements.
- Gói chuẩn có **25 file trích cấu trúc và 7 supporting file chỉ index**.
- Inventory tính cả `extracted` và `indexed` là processed. “32 processed, 0 failed” chưa chứng minh tất cả file đã được sử dụng để đánh giá.

Các số 100% trong tài liệu cũ chỉ áp dụng cho dataset/phép đo tương ứng. Benchmark realistic dùng store giả, không gọi Gemini; thời gian benchmark đó không phải latency toàn hệ thống thật.

## 3. Những phát hiện quyết định thứ tự sửa

Bảng dưới là baseline trước sửa. Tiến độ hiện tại được đánh dấu ở G1; không hiểu các lỗi đã đánh dấu hoàn thành là vẫn còn tồn tại.

| Mức | Bằng chứng từ code | Hệ quả |
|---|---|---|
| P0 | Tài liệu cũ, nhiều thay đổi chưa commit | Ghi nhận và bảo toàn baseline trước khi triển khai |
| P1 | CitedText và thẻ 5C chỉ hiện hai phần cuối chunk ID | Nhiều nguồn khác nhau cùng hiện summary:0/period:0; đây là lỗi nhãn UI, chưa đủ để kết luận mất metadata |
| P1 | Chunk audited/tax/SSM có trang gán cố định; FE chưa nhận citation loại page | Cần provenance theo field/trang thực và hỗ trợ các loại chunk đầy đủ |
| P1 | PDF upload bị xóa sau job; modal chỉ hiện text/metadata | Chưa mở lại PDF gốc đúng trang sau phân tích |
| P1 | validate_node lưu package findings nhưng hai node cuối tự chạy lại intra/cross checks, bỏ qua package checks | Thiếu tháng/trùng file có thể không đi vào 5C/summary |
| P1 | Hai node cuối tính lại metrics thay vì dùng đầy đủ state.ratios | Các khu vực có thể diễn giải các tập dữ liệu khác nhau |
| P1 | Allowed citations chỉ gồm bốn loại tài liệu trích cấu trúc | Bảy supporting PDF chưa đi vào prompt của graph |
| P1 | semantic_search có ở store/API nhưng không được gọi trong graph đánh giá | RAG chưa nối vào luồng tạo 5C/summary |
| P1 | score_faithfulness chỉ kiểm tra ID thuộc allowlist | Citation tồn tại không chứng minh claim được nguồn hỗ trợ |
| P1 | Job trong dictionary RAM; graph dùng InMemorySaver | Restart mất job/result; thiếu lịch sử hồ sơ |
| P2 | Parser chỉ đánh dấu needs_ocr | Chưa xử lý scan hoàn chỉnh |
| P2 | Extractor dựa nhiều vào layout/nhãn của generator | Cần dữ liệu khác layout và held-out tests |
| P2 | Retry sửa citation nằm ngoài try/fallback của lần gọi đầu | Cần test timeout/429 ở lần retry |
| P2 | Citation sai bị bỏ nhưng câu văn vẫn giữ | Claim cần được đánh dấu chưa xác minh |
| P2 | Auth là placeholder; chưa có lưu correction/review | Chốt human-review scope; chỉ làm login khi scope cần |

Nguồn đối chiếu:
- `frontend/src/lib/components/CitedText.svelte`, `frontend/src/lib/citations.ts`, `frontend/src/routes/+page.svelte`
- `backend/app/ingestion/chunker.py`, `parser.py`, `package_inventory.py`, `types.py`
- `backend/app/agent/nodes.py`, `graph.py`, `state.py`
- `backend/app/api/applications.py`, `documents.py`, `auth.py`
- `backend/app/ingestion/store.py`, `backend/app/core/embeddings.py`
- `backend/app/evaluation/faithfulness.py`, `backend/tests/test_realistic_benchmark_e2e.py`

## 4. Giai đoạn triển khai và tiêu chí hoàn thành

### G0 — Khôi phục ngữ cảnh, bảo toàn baseline

Đã hoàn thành trong phiên này: audit code, kiểm tra health/Docker, backend tests và frontend check.

- [ ] Sao lưu baseline gồm tracked/untracked source và manifest dữ liệu; giữ secret ngoài tài liệu/commit.
- [ ] Lưu response JSON và ảnh của một upload 32 PDF, ghi model/embedding mode, latency và fallback status.
- [ ] Đối chiếu yêu cầu đã chốt trong IR với implemented/partial/planned.
- [ ] Cập nhật README/handoff ngắn gọn; chốt deadline, giờ làm/tuần và phạm vi scan/template.
- [ ] Ghi nhận bản Git khi chủ dự án yêu cầu commit; không reset/ghi đè các thay đổi hiện có.

**Hoàn thành khi:** biết bản code và dataset nào là baseline, chạy lại được hệ thống, có đầu ra để so sánh.

### G1 — Kết quả nhất quán và dẫn nguồn chính xác

- [x] Cho 5C/summary dùng `state.inconsistencies` và `state.ratios`, bao gồm package findings và metrics tổng hợp.
- [x] Đưa tên ngân hàng, doanh nghiệp, tài khoản và kỳ dữ liệu vào evidence context; thể hiện thiếu nếu chưa xác định được.
- [x] Chuẩn hóa source reference theo lượt upload: application ID trong chunk metadata, document ID, tên file gốc, chunk ID, trang và vị trí nguồn. ID giữa hai lần upload chưa được hợp nhất thành một tài liệu trong kho lâu dài.
- [x] Field/tổng hợp nhiều nguồn phải giữ các nguồn tương ứng; mang provenance từ extraction sang chunking.
- [x] Thay trang gán cố định bằng trang thực tế.
- [x] Giữ PDF gốc và metadata tối thiểu để phục vụ viewer; mở rộng persistence ở G4.
- [x] Đổi nhãn citation thành [1], [2] kèm tooltip/danh sách nguồn.
- [x] Deduplicate theo full chunk ID trong cùng cụm; không gộp nguồn khác nhau chỉ vì cùng suffix.
- [x] Hỗ trợ resolve/render citation loại `page`; nguồn gốc/trang đã có trong metadata. Retrieval đưa supporting pages vào lời giải thích vẫn thuộc G2.
- [ ] Rút summary về các tín hiệu chính; số liệu từng tháng nằm ở phần chi tiết.
- [ ] Đánh dấu claim chưa đủ bằng chứng và giữ dấu vết lỗi.

**Nghiệm thu:** scenario thiếu tháng/trùng file đi vào đúng evidence của hai node cuối; hai file cùng tên không nhầm nguồn; citation audited nằm sau trang 2 mở đúng trang; supporting-page citation dùng được; test hiện tại tiếp tục đạt.

**Đầu ra:** dashboard dễ đọc, truy nguồn được và dùng cùng kết quả kiểm tra ở mọi phần.

Kiểm thử sau sửa: **83 backend tests passed, 1 skipped**; frontend có **3 citation tests passed** và type-check **0 errors, 0 warnings**. Regression tests bao gồm gói 32 PDF thiếu tháng/trùng file chạy qua cả sáu node, hai file cùng tên nhưng nội dung khác nhau, page provenance trên các trang sau, PDF byte-for-byte và ảnh preview. Các kiểm thử backend này dùng LLM/vector-store giả, không phải đo chất lượng suy luận của Gemini.

Kiểm tra browser riêng với Gemini/vector store thật: `realistic_01` xử lý đủ **32 PDF / 337 trang**, không có file lỗi hay recoverable error. Citation kiểm toán mở đúng trang 4 và chuyển sang trang 5; nguồn bank cùng tên file giữ số tham chiếu khác nhau. Tổng thời gian sáu node khoảng **64.7 giây**. Kết quả lưu tại `data/verification/2026-09-13-source-citations-result.json` (Git-ignored). Chưa đánh giá semantic accuracy của toàn bộ lời giải thích, và bảy supporting files vẫn chưa được đưa vào prompt qua retrieval.

### G2 — Retrieval thực sự đi vào đánh giá

**Cập nhật 24/09/2026:** đã triển khai application-scoped retrieval vào 5C/summary, supporting-page context, forecast labels, cảnh báo thiếu evidence và panel audit. Checklist dưới giữ các tiêu chí nghiệm thu tổng thể; chưa đánh dấu toàn bộ hoàn thành khi chưa có live acceptance.

90 backend tests passed, 1 skipped; 3 frontend tests passed, check/build thành công. Qdrant in-memory thật + fake LLM xác nhận fact chỉ có ở trang 7 của supporting PDF đi vào cả hai prompt. Vector được filter theo embedding space; cần upload lại dữ liệu cũ. Local hashing/threshold chưa benchmark semantic relevance. Audit vẫn nằm trong result RAM, legacy lookup vẫn cho phép bỏ application scope.

Live 32-PDF RAG chưa xác nhận vì Docker Desktop lỗi khởi tạo inference manager. Kết quả 13/09 phía trên là source-citation trước RAG, không phải nghiệm thu RAG.

- [ ] Gắn application ID vào chunk và bắt buộc filter theo application khi search/resolve nguồn.
- [ ] Tạo context cho finding/nhóm 5C: query → retrieve → chọn evidence → prompt.
- [ ] Sử dụng management accounts, forecast, facility statements khi có bằng chứng liên quan.
- [ ] Phân biệt dự báo và số thực tế; thêm structured fields cho supporting documents khi cần tính toán.
- [ ] Lưu query, retrieved chunk IDs và evidence đưa vào prompt để đánh giá lại.
- [ ] Ghi rõ embedding mode: `local` hiện là lexical feature hashing; stub khi thiếu Gemini key không chứng minh chất lượng semantic retrieval.
- [ ] Chọn embedding qua bộ query/evidence test; tách collection/reindex có kiểm soát khi đổi model.
- [ ] Xử lý không tìm thấy bằng chứng phù hợp; giữ tính toán tài chính trong code.

**Nghiệm thu:** thông tin chỉ có trong supporting PDF được retrieve và dẫn nguồn; hai application không lẫn evidence; query không có đáp án không tạo số liệu/tài liệu; không trộn vector từ các embedding mode.

**Đầu ra:** luồng RAG quan sát và đo được, phù hợp với mô tả kỹ thuật của dự án.

### G3 — Ground truth, extraction và đối chiếu

Chuẩn bị từ G0 và chạy xuyên suốt G1/G2; không đợi cuối dự án mới kiểm tra correctness.

- [ ] Rà 10 controlled scenarios: fields, findings, severity, nguồn và kết quả tính tay.
- [ ] Tách development fixtures và tập held-out chưa dùng để điều chỉnh parser.
- [ ] Thêm layout khác, field đổi tên, số âm, cột nhiều năm, missing field, ngắt dòng và nhiều trang.
- [ ] Phân biệt parsed/indexed, structured extracted và usable for assessment trên inventory.
- [ ] Test cùng doanh nghiệp/tài khoản/kỳ, file trùng, kỳ chồng lấn và chuyển tiền nội bộ có gây cộng hai lần.
- [ ] So sánh cùng kỳ/cùng định nghĩa field; ghi quy tắc và tolerance trước khi chấm mismatch.
- [ ] Rà proxy debt-service: dùng lịch trả nợ nếu có; nếu thiếu, ghi estimated/assumptions hoặc insufficient data.
- [ ] Test mẫu số 0, missing value, giá trị âm, đơn vị và fiscal year khác calendar year.
- [ ] Báo scan/OCR-needed rõ; triển khai OCR tối thiểu nếu nằm trong phạm vi demo đã chốt, đo riêng text PDF và scan.

**Nghiệm thu:** controlled fixtures có expected output được kiểm chứng; công thức khớp ground truth trong tolerance; không đánh dấu đầy đủ khi thiếu dữ liệu; held-out results được báo riêng.

**Đầu ra:** bộ regression và báo cáo correctness theo từng loại tài liệu.

### G4 — Lưu hồ sơ và human review

Lưu PDF tối thiểu bắt đầu ở G1; giai đoạn này hoàn thiện vòng đời application.

- [ ] PostgreSQL schema/migration cho application, document, job, analysis result và review event.
- [ ] Lưu output, version cấu hình/model và trace sự kiện; giữ nguồn cho kết quả còn hiệu lực.
- [ ] Trạng thái queued/running/completed/failed/partial phản ánh đúng kết quả.
- [ ] Mở lại kết quả hoàn tất sau restart; job dang dở có trạng thái/phương án thử lại rõ.
- [ ] Hiện tiến độ theo bước thật thay vì chỉ 5 → 20 → 100.
- [ ] Danh sách hồ sơ và chi tiết; note/đánh dấu finding đã xác minh/cần bổ sung.
- [ ] Nếu cho sửa field: giữ giá trị gốc, correction và tính lại output phụ thuộc.
- [ ] Export assessment kèm sources, findings, assumptions và review status.
- [ ] Login/quyền sở hữu hồ sơ nếu có nhiều người dùng trong scope; ghi rõ giới hạn nếu demo local một người.

**Nghiệm thu:** refresh/restart vẫn mở đúng application/PDF; review note tồn tại; retry không ghi đè nhầm; thao tác review không tự động quyết định khoản vay.

**Đầu ra:** upload → phân tích → xem lại → xác minh → export.

### G5 — Reliability và đánh giá có số liệu

- [ ] Test 429/timeout ở lần đầu và retry citation; hiển thị AI/fallback/partial mode.
- [ ] Test PDF hỏng/encrypted, quá số file/dung lượng, cùng tên file và missing documents.
- [ ] Chạy gói nhỏ, gói 32 PDF và gói chạm giới hạn đã công bố.
- [ ] Integration dùng dataset/collection test riêng; đo ingestion, embeddings/retrieval, Gemini và tổng thời gian riêng.
- [ ] Extraction accuracy theo field/loại tài liệu; không dùng parse success làm value accuracy.
- [ ] Finding precision/recall và false positives trên gói khỏe mạnh.
- [ ] Đổi cách gọi metric allowlist thành citation validity; bổ sung source/page correctness, claim support và citation coverage.
- [ ] Tích hợp RAGAS khi đã có query, retrieved contexts và responses; lưu evaluator/model/config/raw outputs.
- [ ] Kiểm chứng tay số liệu và citation trên mẫu định trước, không thay ground truth bằng LLM evaluator.
- [ ] Usability tasks và SUS theo protocol được chấp thuận; tách nhóm loan officer và người dùng thay thế.
- [ ] Sửa study kit cũ theo UI thật; không loại điểm vì thấp hoặc coi mẫu nhỏ tự động đủ cho kết luận thống kê.

**Nghiệm thu:** mỗi metric có mẫu số, dataset và mode; latency có cấu hình máy/số lần chạy; có raw evidence, case lỗi và hạn chế.
Các ngưỡng >90% extraction, >70 SUS, <180s trong tài liệu cũ là mục tiêu cần đối chiếu IR, chưa phải kết quả hiện tại.
Nếu ít lần chạy, báo median/range và số mẫu; diễn giải percentile theo giới hạn dữ liệu.

**Đầu ra:** evaluation pack CSV/JSON, hình/bảng kết quả, case studies phục vụ Report 2.

### G6 — Chốt demo và bàn giao

- [ ] Freeze dataset/cấu hình demo đã test.
- [ ] Demo gói khỏe mạnh, có mismatch, thiếu dữ liệu; chuẩn bị minh họa fallback.
- [ ] Script 5–10 phút: upload → findings → source → 5C → review → export.
- [ ] Rehearsal từ trạng thái Docker sạch có kiểm soát.
- [ ] Cập nhật sơ đồ/tài liệu theo code thật; lưu screenshots/video/test evidence.
- [ ] Ghi giới hạn và future work còn lại.

**Hoàn thành khi:** demo tái lập được và giải thích bằng chứng cho mỗi tính năng/metric đã công bố.

## 5. Lịch gợi ý và phụ thuộc

Đường triển khai chính: **G0 → G1 → G2 → G4 → G5 → G6**.
G3 chạy từ đầu vì correctness là điều kiện nghiệm thu của mọi giai đoạn.
Chuẩn bị người tham gia usability sớm; thu dữ liệu chính thức khi flow ổn định.

Chưa có deadline/giờ làm được xác nhận. Khung dưới đây giả định **10–12 giờ/tuần**, gồm **8 tuần làm việc + 2 tuần dự phòng**, sẽ chỉnh sau khi chốt OCR/layout và lịch học.

| Tuần | Việc chính | Đầu ra |
|---|---|---|
| 1 | G0, G1 evidence chung | Baseline; package findings đi vào 5C/summary |
| 2 | G1 provenance/PDF/citation UI | Nguồn phân biệt được và mở đúng trang |
| 3–4 | G2, G3 | RAG có evidence từ supporting PDF; held-out correctness đầu |
| 5 | G4 persistence | Reload/restart vẫn xem hồ sơ |
| 6 | G4 review/export, G3 scope còn lại | Vòng đời hồ sơ hoàn chỉnh |
| 7 | G5 reliability và đo lường | Evaluation pack bước đầu |
| 8 | G5 usability, G6 rehearsal | Demo và evidence cho Report 2 |
| 9–10 | Dự phòng | Dataset mới, quota, lịch người tham gia, feedback supervisor |

Nếu hạn ngắn: ưu tiên G1, RAG tối thiểu scope rõ, ground truth và evaluation; cắt tính năng phụ chưa cam kết. Không tiết kiệm bằng cách bỏ kiểm tra số liệu/nguồn.

## 6. Ba task triển khai đầu tiên

| ID | Task | Nghiệm thu |
|---|---|---|
| T01 | Dùng findings/ratios chuẩn từ state trong 5C/summary | Thiếu tháng/trùng file xuất hiện đúng trong evidence hai bước cuối |
| T02 | Source reference và nhãn citation | Nguồn khác nhau phân biệt được; dedup theo full ID; hỗ trợ page chunks |
| T03 | Lưu PDF và mở đúng trang | Click audited/tax/supporting citation mở đúng nguồn, không dùng trang đoán |

Mỗi task: ghi expected output → sửa và test liên quan → kiểm tra UI/API → lưu evidence → cập nhật tiến độ.
Sau T03, nối retrieval và kiểm chứng một câu hỏi chỉ có đáp án trong supporting PDF.

## 7. Tạm hoãn để giữ phạm vi FYP

- Đổi framework/provider/topology không có nhu cầu cụ thể.
- Microservices/Kubernetes/public cloud khi chưa được yêu cầu.
- Huấn luyện credit scoring model mới hoặc tự động quyết định khoản vay.
- Làm lại toàn bộ UI trước khi dữ liệu/nguồn đúng.
- Cam kết mọi template ngân hàng hoặc mọi loại scan.
- Module ngoài IR đã chốt.

Đa người dùng, public deployment và OCR diện rộng trở thành bắt buộc khi scope đánh giá yêu cầu; phần còn lại phải ghi đúng giới hạn.

## 8. Chạy lại và tìm file

Project root:
`C:\Users\Dell\OneDrive - Asia Pacific University\APU SUBJECT\Year 3\FYP\System`

Từ project root:

```powershell
docker compose ps
docker compose up --build
```

Frontend: http://localhost:5173
API docs: http://localhost:8000/docs
Health: http://localhost:8000/health

Lệnh đã kiểm tra trong phiên này, từ backend:

```powershell
$env:FYP_RUN_INTEGRATION = '0'
.\.venv\Scripts\python.exe -m pytest tests -q
```

Từ project root, khi frontend container đang chạy:

```powershell
docker compose exec -T frontend npm run check
```

| Muốn tìm gì | File/thư mục |
|---|---|
| Upload/job/response | backend/app/api/applications.py; frontend/src/lib/api.ts |
| Sáu node | backend/app/agent/graph.py; nodes.py; state.py |
| Extraction và nguồn | backend/app/ingestion/*extractor.py; types.py; chunker.py |
| Inventory 32 file | backend/app/ingestion/package_inventory.py |
| Mismatch | backend/app/validation/ |
| Công thức/tổng hợp | backend/app/ratios/ |
| Citation UI | frontend/src/lib/components/; frontend/src/lib/citations.ts |
| Prompt | backend/app/ratios/five_c.py; backend/app/explainability/summary.py |
| Retrieval/embedding | backend/app/ingestion/store.py; backend/app/core/embeddings.py |
| Test/dataset/evaluation | backend/tests/; backend/scripts/; backend/app/evaluation/ |
| Docker | HOW_TO_RUN.md; docker-compose.yml |

Phiên mới: đọc bản này, kiểm tra git status, task đang làm và kết quả test gần nhất. Không lấy con số 100% hoặc trạng thái Done trong tài liệu cũ làm kết luận cho code/dataset mới.
