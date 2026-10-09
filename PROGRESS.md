# Project Progress Log

## 2026-10-09 — Groq LLM provider integration

- Added a provider-agnostic Groq implementation through the OpenAI-compatible chat-completions API. Structured stages use JSON Object mode followed by local Pydantic validation, avoiding Groq `failed_generation` responses seen with the long-form risk-summary schema.
- Added rate-limit retries that respect `Retry-After`, including bounded retries for Groq `413` TPM-window responses, provider-neutral quota errors, and Groq run metadata while retaining Gemini support. The local ignored `backend/.env` now selects `openai/gpt-oss-120b`; no API key is present in tracked files.
- Severity markers such as `[WARNING]` are no longer mistaken for evidence citations. The summary prompt now emits severity labels without brackets, while citation verification remains strict for actual chunk IDs.
- Docker starts the production virtual-environment binary directly instead of invoking `uv run`, preventing dev dependency synchronization and dropped requests after rebuilds.
- Large-package prompts now compact repeated inventory, retrieval audit metadata and monthly metrics before LLM submission while preserving the full saved result/UI audit trail. Structured bank, audited-financial and tax evidence is not repeated in the summary retrieval block; supporting management, facility and forecast evidence remains eligible.
- Live case 6 run `93adb8a1-38d8-4fe3-9d07-79e5ce73acb9` completed both Groq stages with no fallback or recoverable errors and six valid source citations. Live case 11 run `2b546b78-339b-4c3b-85ab-84e4acd8d8a7` also completed without fallback or recoverable errors, cited management evidence from displayed page 3, and correctly rated Conditions as weak from 65% customer and 70% supplier concentration. The same-model case 6 versus case 11 baseline comparison is now complete and passing. Validation: Groq-focused tests `6 passed`; full backend regression `133 passed, 1 skipped`; scoped Ruff checks passed.

## 2026-10-09 — Large-package load verification

- Case 16 (`LOAD-001`) processed the full realistic package: 32/32 PDFs, 337/337 pages, zero failed documents and 1,101 indexed chunks. Recorded stage time total was 6,113 ms (parse 2,307 ms; extract 1,654 ms; validate 10 ms; ratios 4 ms; assess 1,699 ms; summary 439 ms).
- Manually verified tax-return citations for YA2023, YA2024 and YA2025. Identity fields resolve to page 1, monetary fields resolve to page 3, and all extracted amounts match the authored ground-truth files.
- Retrieval remained partial because the generated facility, management and forecast fixtures contain generic tabular supporting items rather than material collateral, market-risk or forecast-assumption statements. The UI correctly says no relevant excerpts were retrieved and asks for manual inspection; it does not claim those documents were missing.
- The original run used deterministic fallbacks after Gemini quota exhaustion. After Groq prompt-budget and TPM-retry fixes, live run `bd654c23-5555-4ffb-8a43-03ea3aab1aaf` completed both AI stages without provider fallback, produced 13 verified summary citations and retained only the expected manual-review retrieval warnings for collateral, conditions and forecast. Detailed evidence is recorded in `data/ordered_tests_v1/16_large_package_32/observations.csv`.

## 2026-10-09 — RM-thousands financial normalization

- Audited-financial extraction now detects explicit `RM'000`, `RM’000` and RM-thousands labels and normalizes every extracted monetary field to canonical RM using a `1,000` multiplier. Plain-RM statements remain unchanged.
- Source display unit, canonical unit and multiplier are retained in the audited-financial model, ratio payload and evidence metadata. RAG text now contains normalized RM amounts rather than the unscaled display figures.
- Technical Details shows an explicit normalization notice before the ratio/input table. Ratios remain unchanged because numerator and denominator use the same multiplier; correct ratios alone are not treated as proof that amount extraction is correct.
- Added case-14 regression comparing all 26 current/prior monetary values and source pages against authored ground truth, plus four ratios and evidence metadata.
- Validation: backend `126 passed, 1 skipped`; frontend `20 passed`, Svelte check clean and production build passed. A live case-14 API run reported source unit `RM'000`, multiplier `1000`, revenue `RM 120,000.00`, operating cash flow `RM 28,000.00`, current assets `RM 80,000.00`, and unchanged expected ratios (`2.0000`, `1.0000`, `0.1800`, `10.0000`). New extractor/chunker/regression code passes scoped Ruff checks; older enum and typography lint findings in adjacent existing files remain out of scope.

## 2026-10-09 — Corrupt-PDF processing failure safeguards

- Corrupt or incomplete PDFs now remain in the package inventory with `parse_failed` status instead of aborting the whole analysis job. The user-facing parse error names the original file and asks for replacement without exposing temporary server paths.
- Failed parses create no chunks, citations, extracted financials or financial conclusions. Deterministic fallback explicitly states that an invalid or damaged PDF was detected and that no financial conclusion is supported.
- Packages where every uploaded document fails extraction now bypass both LLM stages entirely. This avoids unnecessary provider latency/errors when there is no evidence to assess, and the parse audit line reports the true successful count (`Parsed 0/1` for case 13).
- The dashboard completes in human-review mode, shows the failed document count and presents a prominent invalid-PDF alert rather than returning the raw PyMuPDF exception on the upload form.
- Added case-13 regression covering the friendly error, failed inventory state, zero evidence/citations and conservative `insufficient_data` 5C result. Existing missing-file and scanned-PDF regressions remain green.
- Validation: backend `125 passed, 1 skipped`; frontend `20 passed`, Svelte check clean and production build passed. A live case-13 API upload completed at 100% with `0 processed / 1 failed`, `parse_failed`, zero extracted evidence, `Parsed 0/1`, only the expected parse error, and the explicit no-financial-conclusion headline. The evidence-free 5C/summary stages completed deterministically without a provider error. Scoped Ruff checks pass; the previously recorded `datetime.timezone.utc` modernization in `nodes.py` remains intentionally out of scope.

## 2026-10-09 — Scanned-PDF OCR failure safeguards

- Image-only or insufficient-text PDFs are now recorded as `ocr_required` extraction failures with their affected page numbers, rather than only appearing as unsupported unknown documents.
- Deterministic summary fallback now receives package-inventory and OCR context. A package with zero extracted documents states that OCR is required and that no document evidence was extracted; it no longer claims successful processing.
- The dashboard distinguishes completed runs with document failures, shows a visible OCR-not-supported warning, and keeps the processed/failed counts explicit. Recommended checks suppress raw validation-code entries and collapse duplicate bank, financial, registration, collateral, repayment and conditions actions.
- Added case-12 regression covering OCR-page detection, failed inventory status, conservative 5C ratings, zero citations and the OCR-specific fallback narrative.
- Validation: backend `124 passed, 1 skipped`; frontend `20 passed`, Svelte check clean and production build passed. Changed Python files pass Ruff format; scoped Ruff lint passes, while the previously recorded `datetime.timezone.utc` modernization in `nodes.py` remains intentionally out of scope.

## 2026-10-09 — Management-concentration Conditions safeguard

- Added a deterministic 5C guard for retrieved management-accounts evidence: customer or supplier concentration at or above 50% forces Conditions to `weak` rather than allowing an AI-generated `adequate` rating. The 50% boundary is an explicit prototype review flag, not a production lending threshold.
- The guard uses only retrieved management-account lines containing concentration/dependence terms and percentages. Its evidence IDs are restricted to allowed retrieved chunks, preserving the original source page.
- Added case-11 regression proving the 65% customer and 70% supplier facts produce a weak Conditions rating and that every Conditions citation resolves to `management.pdf` page 3.
- Validation: backend `123 passed, 1 skipped`; targeted case-11 regression passed. The new regression is Ruff-formatted; Ruff still reports the previously recorded `datetime.timezone.utc` modernization in `nodes.py`, which remains intentionally out of scope.

## 2026-10-09 — Missing-tax review presentation safeguards

- Character now describes only compliance documents actually present in the package. Case 10 with SSM but no tax return no longer states that a tax return was supplied, and its follow-up no longer asks to verify filing/payment records for a missing document.
- Summary headlines reposition source citations before contrasting package-inventory limitations, so a financial PDF citation does not appear to substantiate missing-document or coverage-gap observations. The summary prompt now states the same constraint.
- Recommended human checks no longer receive raw validation-code strings from the backend. Structured validation findings remain in the dedicated system-check and validation sections, while the checklist retains human-readable actions.
- Added a case-10 regression for expected missing-document findings, inventory-aware Character wording, citation placement and duplicate machine-check suppression.
- Validation: backend `122 passed, 1 skipped`; targeted case-10 regression passed; changed summary and regression files pass Ruff lint/format checks.

## 2026-10-09 — Revenue-mismatch fallback safeguards

- Case 09 deterministic fallback now surfaces the audited-versus-tax income discrepancy and both source citations in the headline/body instead of returning only a generic processing message. It explicitly identifies itself as fallback output and does not infer fraud or tax evasion.
- Conditions remains `insufficient_data` when the uploaded package has no external market, industry, concentration, supplier or facility-purpose evidence. Document processing and internal financial activity no longer imply an adequate Conditions rating.
- Character wording now distinguishes limited bank coverage from complete absence of bank evidence; financials-and-tax-only packages no longer claim that limited bank activity was observed.
- Added a full case-09 regression using an unavailable LLM to verify warning severity, source citations, conservative 5C ratings and mismatch-specific fallback narrative.
- Validation: backend `121 passed, 1 skipped`; targeted case-09 regression passed. Ruff reports one pre-existing `datetime.timezone.utc` modernization in `nodes.py`; no unrelated modernization was applied.

## 2026-10-09 — Outstanding issue audit

- Reviewed recorded open bugs and the case-08 screenshot report. Could not reproduce RAG topic overlap on the saved case-08 dashboard at desktop width 1440 before the change; do not claim a confirmed root cause for the screenshot artifact.
- Hardened RAG topic cards with minimum-width reset, natural row sizing and wrapping for long identifiers. Browser verification after change: eight topic cards, no intersecting rectangles or horizontal overflow at width 1440; no card horizontal overflow at width 390. Viewport reset after testing.
- Added case-08 regression proving critical HOLDER_SSM_MISMATCH links both bank and SSM sources, with no spurious balance arithmetic warning. Existing case-02 day-count and conservative Capacity regressions pass.
- Validation: backend 120 passed, 1 skipped; frontend 19 passed, check clean and build passed. Added append-only resolution follow-up for original EXT-001 bug; original run and bug records remain preserved.
- Remaining limitations: full live AI retest of case 06 after earlier provider 503 is still not verified; semantic correctness of every AI claim and generalisation beyond authored fixtures are not established. Screenshot overlap remains not reproduced, rather than confirmed fixed. No new live AI request was made during this audit.

## 2026-10-08 — Standalone 5C section heading

- Render standalone Provisional 5C Assessment labels as full-width group headings, not numbered empty assessment cards. Support plain, bold and Markdown heading forms without rendering arbitrary HTML.
- Content-card numbering excludes group headings. Narrative claims, amounts, citations and saved snapshots are preserved; existing results use the new presentation without rerunning the model.
- Added heading recognition regression covering colon placement and preserving sentences containing assessment claims.

## 2026-10-05 — Clean package review safeguards

- Live rerun d1b62a35-ddb5-4d62-946c-b8434c0c2381 processed all four files but Gemini returned 503 for both AI steps; deterministic fallbacks were used and errors surfaced. Character stayed insufficient_data and checks were retained. Live AI generation remains unverified until provider recovery. Evidence: data/verification/clean-package-review-live.json.

- Character now remains insufficient_data when banking history has gaps in the configured review period or no bank metrics exist. Limited transactions and the presence of SSM/tax documents do not establish sustained payment conduct or verified compliance. This is a conservative prototype rule, not a universal lending threshold.
- Summary prompt preserves supplied ratings and distinguishes registration/tax documents from verified filing acceptance/payment.
- Recommended human checks no longer suppress all entries that duplicate validation codes, fixing a heading with an empty list. Narrative 5C Markdown/colon labels render as readable criterion headings while preserving amounts and citations.
- Added case-06 four-document regression for expected missing-bank-month warning, complete core-document inventory and conservative Character. Backend 119 passed, 1 skipped; frontend check clean, 15 tests passed and build passed. Historical analysis values remain unchanged.

## 2026-10-05 — Tax case 05 evidence and UI

- Added tax-specific retrieval and structured tax facts to both assessment prompts, with exact source chunk IDs and explicit limitations: reported tax payable is not proof of payment, audited profit or repayment capacity.
- Exposed extracted tax fields and page provenance in saved analysis responses and added a Technical Details tax card with source inspection. Historical snapshots remain unchanged.
- Invalid summary citations remaining after retry now replace the AI narrative with deterministic fallback rather than only removing citation markers. Tax-only Capacity wording no longer implies bank/financial metrics exist.
- Regression compares six case-05 fields and source pages, prompt availability and allowed citation IDs. Backend: 118 passed, 1 skipped; frontend: check clean, 14 tests passed, build passed.
- Live run 922ba6cc-3b1c-4982-9569-990e1847513f retrieved one tax excerpt, reported RM120000/RM27000/RM5400 with valid citation and no processing errors. Raw response: data/verification/tax-review-live.json. Scoped synthetic retest only; not comprehensive production acceptance or semantic verification of every sentence.

## 2026-10-05 — Financial case 04 review and scoped retest

- Removed the assumed 10% liabilities principal repayment from DSR. Without a verified annual repayment schedule, DSR remains unavailable; Capacity remains insufficient_data rather than a strength claim.
- Included audited financial inputs and canonical source references in Capacity evidence. Preserved comparative periods in financial trends (case 04: 2024 and 2025, revenue growth 20%).
- Added financial ratio tables, formulas, limitations and input values to Technical Details; NPM displays as 18%. Split financial narrative sections without rewriting source text or citations.
- Case 04 regression checks verify 26 extracted financial values and source pages, four ratios, unavailable DSR and comparative trend. Live Gemini run 053d572d-53b4-489e-b51d-77fc2951b8a5 confirms unavailable DSR, partial Capacity evidence and both years. Snapshot saved at data/verification/2026-10-05-financial-review/live-result.json. A subsequent wording-only correction avoids requesting financial statements already supplied; the historical snapshot is unchanged.
- Validation: backend 117 passed, 1 skipped; frontend check 0 errors/warnings, 14 tests passed, production build passed. This is a scoped synthetic-fixture retest, not overall production acceptance or independent verification of every generated claim.

## 2026-10-05 — Split combined 5C narrative for readability

- Display-only splitting at explicit sentence-initial 5C assessment transitions; keeps conclusions and source citations with their original criterion instead of splitting every two sentences.
- Cards use criterion names when identifiable and no longer stretch shorter text cards to the tallest neighbour. Original stored narrative is unchanged; applies to saved dashboards too.
- Added tests for all five criteria, quoted labels, financial decimals, citation preservation and keeping concluding sentences attached.

## 2026-10-05 — Company case workspace and saved dashboards

- Added Company cases separately from Development History: explicit company/reference, immutable Test/Real category (Test default), under review / awaiting documents / reviewed states, review notes and append-only review events.
- Users explicitly link completed saved analyses as separate versions; duplicate links and non-analysis entries are rejected. Historical runs are not auto-promoted into real company cases. Company identity matching is manual and disclosed in UI.
- Both History and case versions can open the full saved dashboard using /?saved=<history-id>. Loading reads the stored snapshot without calling analysis/LLM, and displays an original-result warning; source evidence uses existing source APIs.
- Case JSON files are stored separately under data/company_cases on the existing data mount. Existing analysis snapshots stay unchanged. This remains a trusted-local single-process prototype, not authenticated production case management or automated lending approval.
- New document analysis remains an explicit new run; users link its saved result to the existing case. No automatic incremental reanalysis or document merging is implemented.
- Verification: 115 backend tests passed, 1 skipped; 11 frontend tests passed; Svelte check/build passed. Live /api/cases starts empty, existing 16 History records preserved, /cases returned HTTP200. Services restarted.

## 2026-10-05 — Analysis progress follows processing stages

- Replaced fixed 20% agent_graph status with streamed graph state updates: reading10, parsed20, extracted40, validated50, calculated55, assessed80, summarised95, completed100.
- User-facing friendly stage labels replace internal graph terminology. Bar animates between stage milestones and holds completion for 650ms before displaying results. Percentages represent workflow milestones, not elapsed-time estimates; slow AI calls may pause on their current stage.
- Failed jobs preserve their last progress instead of claiming 100%. Added stage-stream and failure regression tests. Existing synchronous analysis and saved result format remain unchanged.
- Verification: 112 backend tests passed, 1 skipped; 11 frontend tests passed; svelte-check and production build passed. Restarted both services. Live paid-model progress timing has not been measured in this change.

## 2026-10-04 — SSM test review fixes

- Retrieval labels now explicitly describe available-source search completion, not sufficient evidence for all 5Cs. Backend historical status values remain intact.
- Bank coverage displays not assessed when no usable bank metrics exist, rather than reporting missing months: none for an SSM-only package.
- Full assessment preserves original paragraph boundaries; removed the every-two-sentences split that orphaned the Capital conclusion. Technical details uses full width when no bank metrics table exists.
- Summary prompt requires exact validation severity. A targeted deterministic guard rejects critical-warning/finding/alert language when no critical finding exists and uses a logged deterministic fallback. This is a narrow safeguard, not comprehensive semantic verification (mixed-severity attribution still needs further work).
- Appended system validation text includes canonical severity. Existing saved AI narratives are not rewritten by these fixes.
- Verification: 110 backend tests passed, 1 skipped; 11 frontend tests passed; svelte-check and production build passed. Restarted backend/frontend and added a linked History note. No live Gemini SSM rerun was performed in this change.

## 2026-10-04 — Assessment and history layout follow-up

- Replaced narrow left-aligned full narrative with responsive numbered detail cards in two desktop columns; retained original text and citations without regenerating AI claims.
- History now defaults to compact record summaries with expandable evidence, snapshot and follow-up controls. No saved data removed.
- Fixed false history relationships: missing related_id and missing application_id previously compared equal and linked unrelated analysis entries to manual records. Relationships now require a nonempty explicit identifier and exclude self-links.
- Previous review final verification: 105 backend tests passed, 1 skipped; frontend 7 tests passed, check/build successful.
- Current UI verification: 9 frontend tests passed including explicit/absent history-link regressions; svelte-check 0 errors/warnings and production build passed.

## 2026-10-03 — First bank test review and scoped fixes

- Fixed inclusive statement days (January = 31; daily inflow RM322.58, outflow RM193.55). Added same-day, month-end, leap-year and invalid-period regression tests.
- Bank-only assessments without financial ratios now use Capacity insufficient_data, not weak merely because evidence is missing. This conservative guard is not full semantic verification.
- Capacity retrieval includes source-linked structured bank metrics; inventory absence checks no longer query transaction evidence. Local lexical retrieval remains in use.
- Added readable narrative paragraphs, visible metric headings, red/white Remove button, and suppressed repeated machine-coded human-check entries already shown under validation findings.
- History supports expected/actual/improvement fields, loaded linked follow-ups and original-result inspection. New runs record model and backend source SHA256. Old snapshots remain unchanged.
- Actual case02 bank.pdf: all 69 authored metadata/transaction field comparisons passed; ten transactions. Evidence: data/verification/2026-10-03-review/extraction-comparison.json.
- Live Gemini retest application b1d729a1-4488-453e-8639-60652e67515d returned expected metrics and Capacity insufficient_data; result saved alongside the comparison report. Added original bug, scoped retest and development note to History.
- Validation: backend full suite 104 passed, 1 skipped before an additional history regression; history subset then 6 passed. Frontend 7 tests, svelte-check and production build passed before final duplicate-warning filter (rechecked below in task execution).
- Remaining: independent gold-standard validation, cases03–14, baseline comparison, 32-document workload, semantic verification of all claims and production/security gates. A single authored fixture passing is NOT an overall system pass.

> **Bản tự cập nhật lịch sử project.** Mọi agent (Claude, Cursor, Copilot,
> codex, v.v.) hoặc developer làm việc với repo này **bắt buộc** đọc file
> này trước, và cập nhật sau mỗi lần thay đổi đáng kể. Mục tiêu: bất cứ
> ai mở repo lần đầu đều hiểu được "đang ở đâu", "đã làm gì", "phải làm
> gì tiếp" mà không cần hỏi tác giả.

---

## Onboarding prompt cho agent mới

Copy đoạn này vào đầu chat khi mở session mới với bất kỳ AI agent
(ChatGPT, Gemini, Aider, Cursor, v.v.). Sau đó nói task của bạn ở dòng cuối.

```text
Tôi đang làm Final Year Project tại APU Malaysia. Repo này là project FYP
tên "Agentic AI for Multi-Document Financial Analysis in Malaysian SME
Lending" — stack FastAPI + LangGraph + Gemini + Qdrant + SvelteKit.

Trước khi làm bất cứ việc gì, BẮT BUỘC:

1. Đọc file PROGRESS.md ở root repo — chứa current status, architecture
   decisions, known issues, history, và quy tắc làm việc.
2. Scan mục "## Pending milestones — agent phải hỏi user" trong
   PROGRESS.md. Nếu hôm nay >= ETA của item nào, HỎI TÔI ngay câu đầu
   tiên (trước khi bắt đầu task) để cập nhật trạng thái. Giúp tôi không
   bỏ sót follow-up.
3. Đọc docs/FYP_Context.md để hiểu background project.
4. Nếu task chạm vào code, đọc luôn các file liên quan trước khi sửa.

Trong khi làm việc:
- Tôn trọng "Architecture decisions (locked)" trong PROGRESS.md — đừng tự
  ý đổi (vd: đổi monorepo layout, đổi từ uv sang pip, đổi LLM provider).
- Nếu phát hiện vấn đề với decisions đó, BÁO TÔI trước, đừng làm luôn.
- Trả lời tôi bằng tiếng Việt (code/identifier giữ tiếng Anh).

Sau khi hoàn thành công việc:
- THÊM 1 entry mới vào đầu mục "## History" trong PROGRESS.md theo
  template có sẵn trong file (date, agent name, what changed, why, impact,
  commits).
- Cập nhật "## Current status" + "## Known issues" nếu phase / metric /
  issue thay đổi.
- Nếu pending milestone nào được resolve trong session này, XOÁ khỏi
  "## Pending milestones" và move outcome sang Current status / Next steps.
- Nếu xuất hiện pending milestone mới (vd: vừa submit thứ gì chờ
  approve, vừa start user study chờ kết quả), THÊM vào "## Pending
  milestones" với ETA cụ thể.
- Nếu có dependency mới, ghi rõ trong entry.

Task của tôi là: [TÔI VIẾT TASK Ở ĐÂY]
```

**Cách dùng:**
- Replace `[TÔI VIẾT TASK Ở ĐÂY]` bằng yêu cầu cụ thể.
- Paste vào tin nhắn đầu tiên của session.
- Mỗi session mới = paste lại template, đảm bảo agent không "quên".
- Cuối session, nếu agent quên update `PROGRESS.md`, nhắc một câu:
  *"Đừng quên thêm entry mới vào ## History trong PROGRESS.md trước khi dừng."*

> ⚠️ Mỗi AI tool có quirk riêng. Cursor đôi khi tự ignore convention nếu
> file dài; ChatGPT free tier có thể không follow rule sau ~20 turns
> (drift). Verify agent có thực sự đọc bằng cách hỏi: *"Tóm tắt
> Architecture decisions trong PROGRESS.md cho tôi"* trước khi cho làm task.

---

## Pending milestones — agent phải hỏi user

> **Đây là danh sách những việc đang treo ngoài tầm kiểm soát của code**
> (chờ approve, chờ recruit người, chờ supervisor feedback, …). Mỗi
> agent khi vào session mới **PHẢI scan mục này TRƯỚC** rồi hỏi user
> trạng thái từng item nếu đã quá ETA. Mục đích: giúp user không bỏ sót
> follow-up. Sau khi user trả lời, update item tương ứng + thêm entry
> vào `## History`. Khi item xong, **xoá nó khỏi mục này** và move
> outcome sang `## Current status` / `## Next steps`.

| Item | Submitted/Started | ETA | Cách hỏi user |
|---|---|---|---|
| FYP title approval (FYPPGBank portal) | 2026-05-28 | ~2026-05-31 | "Title đã được approve chưa? Có thấy supervisor được assign chưa?" |
| Supervisor assignment | Depends on title approval | ~2026-05-31 | "Đã biết supervisor là ai chưa? Có cần help draft email intro không?" |
| SUS user study (5-10 participants) | Not started — needs supervisor | TBD | "Đã contact ai cho user study chưa? Cần help soạn email recruitment không?" |
| Real anonymised SME documents | Not started — needs supervisor | TBD | "Supervisor đã share real samples chưa? Nếu có, có muốn chạy lại evaluation harness trên data thật không?" |
| Rotate Gemini API key | Flagged 2026-05-27 | ASAP | "Đã rotate API key chưa? Key cũ đã expose trong chat Claude (~2026-05-27)." |

### Cách follow-up hiệu quả

- **Đầu session**: nếu hôm nay >= ETA của item nào, hỏi item đó ngay
  câu đầu tiên (trước khi nghe task mới của user).
- **Khi user trả lời "chưa"**: đừng push. Ghi nhận và gợi ý thời gian
  hỏi lại (vd: "OK em sẽ hỏi lại nếu sau 3 ngày nữa chưa có update").
- **Khi user trả lời "xong"**: lấy thông tin cụ thể (ngày, tên
  supervisor, link, v.v.) → update PROGRESS.md → xoá khỏi mục pending.
- **Nếu item bị stuck dài hạn**: gợi ý alternative (vd supervisor
  không phản hồi → suggest hỏi APU FYP coordinator).

---

## RULES — đọc trước khi sửa file

### Khi nào phải cập nhật file này?

**BẮT BUỘC** thêm 1 entry mới vào mục `## History` khi:
- Hoàn thành 1 task có user-visible impact (feature mới, bug fix, refactor).
- Thay đổi quyết định kiến trúc (thay framework, đổi DB, thay LLM provider).
- Add/remove document type hoặc agent node.
- Thay đổi proposal scope hoặc evaluation methodology.
- Sửa workflow của user (UI flow, API contract).

**KHÔNG cần** cập nhật khi:
- Sửa typo trong comment.
- Format code (auto-format).
- Bump dep versions không có breaking change.
- Edit cosmetic của UI mà không thay đổi flow.

### Format mỗi entry mới

Insert vào đầu mục `## History` (newest first), theo template:

```markdown
### YYYY-MM-DD — [Agent name hoặc User] — Short headline (max 80 chars)

**What changed:**
- Bullet point cụ thể (file path khi cần).

**Why:**
- Lý do — link tới issue/proposal section/user request nếu có.

**Impact:**
- Test status (X/Y pass), evaluation metric ảnh hưởng, breaking changes.

**Commits:** `abc1234`, `def5678`
```

### Cũng phải cập nhật

- **Mục `## Current status`** ở đầu file — nếu phase / metrics / next steps thay đổi.
- **Mục `## Known issues`** — thêm/xóa khi gặp / sửa được.

### Đừng phá file này

- File này KHÔNG phải changelog auto-generated. Đừng overwrite — chỉ append entry mới ở đầu `## History`.
- KHÔNG xóa entry cũ. Nếu sai, sửa bằng cách thêm entry mới ghi rõ "supersedes YYYY-MM-DD".
- Giữ markdown đúng cú pháp (`{...}` không escape, dùng inline code cho file path).

---

## Project at a glance

- **Title:** *An Agentic AI System for Multi-Document Financial Analysis and Explainable Risk Summarization in Malaysian SME Lending*
- **Author:** Tran Quang Dat (TP079959) — APU BSc IT (FinTech), final year
- **Supervisor:** *To be assigned (FYPPGBank portal pending)*
- **Stack:** FastAPI + LangGraph + Google Gemini API + PyMuPDF + Qdrant + PostgreSQL + Redis + Docker + SvelteKit + Tailwind v4
- **Constraint:** No GPU, no budget — Gemini free tier + self-hosted everything.
- **Documents:** [`docs/FYP_Proposal.md`](docs/FYP_Proposal.md) | [`docs/FYP_Context.md`](docs/FYP_Context.md) | [`docs/TESTING_GUIDE.md`](docs/TESTING_GUIDE.md) | [`docs/USER_STUDY_KIT.md`](docs/USER_STUDY_KIT.md)

---

## Current status

- Update 2026-09-30: Upgraded olive theme to explicit neumorphic components: raised cards/labels/buttons, recessed upload fields and segmented assessment tabs, larger metric typography, and responsive 5C card grid. Financial content and backend behavior remain unchanged.

- Update 2026-09-30: Olive soft-UI theme applied across upload, dashboard and Development History: cream background, rounded cards, soft shadows, olive actions/citations and muted terracotta prototype badge. Red/amber diagnostic meanings remain separate. No backend logic or test history was changed.

- Update 2026-09-30: Added numbered development fixtures in `data/ordered_tests_v1` (01–16), with 24 PDF-named inputs including one deliberately invalid file, authored ground truth and Vietnamese test instructions. All application test statuses remain not_run; no history entries or LLM calls were created. The retained 32-PDF package is unchanged.

- Update 2026-09-30: `/history` adds an initially empty internal development history. New completed/failed analysis executions save append-only JSON records and result snapshots beside source-document storage. Manual test/bug/note entries, linked follow-ups, category/search filters and JSON export are available. No older records are imported; manual test status is not automated test evidence. This is a trusted-local prototype, not an authenticated or tamper-proof audit service.

### Verified restart baseline — 2026-09-13

- Report 1 has been submitted, as confirmed by the project owner in this conversation.
- The current Semester 2 roadmap is [docs/SEMESTER_2_MASTER_PLAN.md](docs/SEMESTER_2_MASTER_PLAN.md), including the code audit, acceptance criteria and proposed delivery sequence.
- Fresh checks: 73 backend tests passed, 1 live-Qdrant integration test skipped; frontend check reported 0 errors and 0 warnings. All five Docker services were running and the backend health endpoint returned OK.
- The 32-PDF workload contains 25 files with structured extraction and 7 supporting files currently indexed as page text. Processing completion does not measure full assessment coverage.
- The first implementation pass now makes 5C/summary consume canonical findings/ratios, preserves extracted source locations and original PDFs, and adds numbered citations with a multi-page PDF preview. Same-name PDFs no longer crash the upload list.
- After implementation: 83 backend tests passed, 1 skipped; three frontend citation tests passed; frontend type-check reported 0 errors and 0 warnings, and the production build passed. See the newest history entry for verification scope.
- Update 2026-09-24: application-scoped retrieval now feeds supporting-document evidence into 5C and summary, with bounded context, embedding-space isolation and a frontend retrieval audit panel.
- Latest checks: 90 backend tests passed, 1 skipped; 3 frontend tests passed; type-check 0 errors/0 warnings; production build passed. Real in-memory Qdrant plus fake LLM verifies a supporting-PDF page-7-only fact reaches both prompts.
- Docker is running again (2026-09-24). The owner's live screenshot shows 32 documents/337 pages processed and partial retrieval with seven excerpts; collateral/conditions/forecast evidence remains missing. This does not establish semantic correctness.
- Dashboard presentation update (2026-09-24): Overview, Documents & Evidence and Technical Details views; expandable 5C/full assessment, grouped citations, searchable sources and a right-side source dialog. No assessment logic changed. Frontend: 5 tests passed, check 0 errors/0 warnings, production build passed.
- Remaining gaps include retrieval-quality calibration, claim-level evidence verification, OCR/general-layout extraction and durable result history. Default local embeddings remain lexical hashing, not a semantic model.
- The May snapshot and pending milestones are historical and must not override the newer plan or the owner's confirmed Report 1 submission.

### Historical snapshot

**As of 2026-05-28**

- **FYP title đã submit lên FYPPGBank portal**; chờ approve (~2-3 ngày,
  ETA ~2026-05-31).
- **Supervisor:** vẫn chưa được assign — depends on title approval.

| Layer | Status | Where |
|---|---|---|
| Phase 1 — Research & Design | ✅ Done | Proposal frozen |
| Phase 2 — Document Pipeline | ✅ 4/4 doc types | `backend/app/ingestion/` |
| Phase 3 — Agent Development | ✅ 6 nodes wired | `backend/app/agent/` |
| Phase 4 — Explainability | ✅ Inline citations + validation | `backend/app/explainability/` |
| Phase 5 — Dashboard | ✅ SvelteKit demo | `frontend/` |
| Phase 6 — Evaluation | ✅ Harness + 3/4 metrics auto | `backend/app/evaluation/` + `backend/scripts/evaluate.py` |
| Phase 7 — Write-up | ⏳ Not started | — |

### Evaluation metrics (latest auto-measured)

| Metric | Result | Target | Status |
|---|---|---|---|
| Extraction accuracy (avg) | 100% (130/130 fields) | >90% | ✅ |
| Citation faithfulness | 100% (0 hallucinations) | 0 | ✅ |
| End-to-end latency p95 | ~59s | <180s | ✅ |
| SUS usability score | Pending user study | >70 | ⏳ |

Re-run: `cd backend && uv run python -m scripts.evaluate --runs 2`.

### Test suite

- 50 passing, 1 skipped (live-Qdrant integration test, opt-in via `FYP_RUN_INTEGRATION=1`).
- Run: `cd backend && uv run pytest tests/`.

---

## Next steps (priority order)

Current technical priorities are in [the Semester 2 master plan](docs/SEMESTER_2_MASTER_PLAN.md), starting with baseline preservation, consistent findings/ratios and traceable citations. The following list is retained as the May 2026 historical plan.

1. ✅ **Submit FYP title to FYPPGBank portal** — done 2026-05-28, awaiting approval (~2-3 days).
2. **Wait for title approval + supervisor assignment** (~2026-05-31 expected).
3. **Run SUS user study** — 5-10 participants, follow [`docs/USER_STUDY_KIT.md`](docs/USER_STUDY_KIT.md).
4. **Manual test pass** — follow [`docs/TESTING_GUIDE.md`](docs/TESTING_GUIDE.md) / `.xlsx` để confirm tất cả 4 scenario PASS.
5. **(Optional) Real anonymised SME documents** — xin từ supervisor, re-run `scripts/evaluate.py` để đo accuracy trên real data.
6. **(Optional) Ablation study** — bật/tắt cross-doc validation, đo impact lên 5C ratings.
7. **Write FYP final report** — Chapters 1-7 + appendices.

---

## Known issues / debt

- **RAG limits (2026-09-24):** re-upload packages to tag old vectors with application/document-kind/embedding-space metadata. No collection was deleted. Local hashing and similarity thresholds are not calibrated for semantic relevance. Scope filters are not authentication; legacy direct lookup still allows omitted application scope.
- **Docker recovery (2026-09-24):** Docker is running again. Earlier runtime-listener failure is no longer the active blocker; retrieval completeness and claim-level accuracy still need investigation.

- **September 2026 citation migration:** old jobs do not contain verified source provenance and their deleted PDFs cannot be restored; re-upload to generate the new source catalogue. Archived PDFs are retained on disk, but jobs/results still disappear on backend restart. Source endpoints remain local-prototype endpoints without authentication.
- **Gemini API key handling**: hiện đang dùng key dev trực tiếp trong `backend/.env`. Một key đã từng paste vào chat (~Dat session 2026-05-27) — cần rotate ở https://aistudio.google.com → API keys → Delete + tạo mới.
- **OCR fallback chưa implement**: `parser.TEXT_DENSITY_THRESHOLD` flag pages cần OCR nhưng Tesseract pipeline chưa wire. Scanned PDFs sẽ fail extract.
- **`document_id` dùng filesystem path**: `f"{path.parent.name}/{path.stem}"` không stable nếu file di chuyển. OK cho FYP demo, không OK cho prod.
- **LangGraph Postgres checkpointer chưa setup() schema lần đầu**: `compile_graph_with_postgres()` yêu cầu caller chạy `checkpointer.setup()` lần đầu. Chưa có wrapper.
- **DSR ratio dùng proxy `10% × total debt`**: real DSR cần loan amortisation schedule. Đã document trong `_dsr()` docstring. Acceptable cho FYP demo.
- **`.gitignore` historical bug**: pattern `lib/` (unanchored) đã từng làm `frontend/src/lib/` bị bỏ qua trong commit `455e419`. Fixed ở `ea32292` bằng `/lib/`. Nếu thêm Python package có `lib/` ở subdir nào đó, có thể bị bỏ ngoài git — luôn `git check-ignore` để verify.
- **Synthetic data only**: chưa test với real SME documents. Extraction accuracy 100% là trên synthetic format.

---

## Architecture decisions (locked)

Quyết định kiến trúc đã được thông qua. Đừng override mà không discuss:

- **Monorepo flat layout**: `backend/` + `frontend/` top-level (KHÔNG `apps/` + `packages/`, KHÔNG `services/`).
- **Backend layout domain-driven**: folders mirror 6-step agent workflow (`ingestion/`, `agent/`, `extraction/`, `validation/`, `ratios/`, `explainability/`).
- **Python package manager = uv** (NOT Poetry, NOT pip).
- **LLM provider-agnostic** qua `app/core/llm.py` Protocol. Default Gemini, hot-swap-able.
- **Linear LangGraph topology** (NOT ReAct tool-selecting agent). 6 nodes cố định map proposal workflow.
- **Per-transaction chunking** cho citation traceability. Mỗi transaction row = 1 chunk với metadata đầy đủ.
- **Inline `[chunk_id]` citation format** — FEATERS-aligned, validated against ingestion-produced allowlist.
- **Deterministic-first validation**: hard checks trước (balance arithmetic, date continuity, holder match), LLM augment sau.
- **Full Docker stack from day one**: backend + frontend + postgres + redis + qdrant trong 1 compose.

Refer to [`memory/project_repo_architecture.md`](memory/project_repo_architecture.md) ở Claude home directory cho detailed rationale (chỉ Claude truy cập được — đây là user's auto-memory).

---

## History

### 2026-10-03 — Codex — Simplify header

- Removed the header's Decision-support environment text and Prototype badge at the owner's request. Assessment-level human-review notices and all analysis behavior remain unchanged.
- Commits: None.

### 2026-09-30 — Codex — Stronger soft-UI depth and smaller logo

- Increased raised/inset shadow contrast on cards, controls, labels and 5C panels; retained restrained citation and warning treatments. Reduced TraceLens header width from 218px to 186px (about 15%). The requested 6–7/10 intensity is a subjective visual target, not a measured standard.
- Svelte check: 0 errors/0 warnings; production build passed. CSS-only changes; no analysis or history records created.
- Commits: None.

### 2026-09-30 — Codex — TraceLens branding

- Used the owner's original transparent PNG in the header, with a CSS viewport hiding its empty margins without modifying the source image. Added a simplified SVG icon for the favicon and renamed page titles to TraceLens.
- Removed the Agentic AI / BNM FEATERS / APU subtitle as requested. No analysis logic or records changed.
- Verification: Svelte check reported 0 errors and 0 warnings; production build passed.
- Commits: None.

### 2026-09-30 — Codex — Neumorphic component redesign

**What changed:** Replaced the mostly flat treatment with paired light/dark shadows, soft surface gradients, recessed inputs, raised micro-labels, pressed states and numbered human-check tokens. 5C dimensions now use a responsive 1/2/3-column grid with visible expand/collapse affordances. Applied shared card treatment to Development History and retrieval panels. Warning colors and focus outlines remain distinct.

**Verification:** Svelte check passed with 0 errors/0 warnings; 5 frontend tests passed; production build passed. Visually checked upload layout at desktop and 390px; no analysis was submitted and no history was seeded. Populated assessment content is not covered by these visual checks.

**Commits:** None.

### 2026-09-30 — Codex — Olive soft-UI visual theme

**What changed:** Added shared olive/neutral Tailwind tokens, cream background, soft card geometry/shadows, light header and translucent navigation. Updated primary controls, citations and source-page selection to olive; preserved red errors and amber warnings. Added keyboard focus outlines and reduced-motion support; upload input remains keyboard accessible.

**Why:** Apply the owner's selected olive palette and soft Apple-inspired visual direction without changing the analysis workflow.

**Verification:** Svelte check 0 errors/0 warnings; 5 frontend tests passed; production build passed. Restarted only frontend to refresh Docker's source cache. Visually checked live upload and empty history pages. No paid analysis or new history records were generated; populated dashboard was not rerun for this styling change.

**Commits:** None.

### 2026-09-30 — Codex — Numbered controlled development test packs

**What changed:**
- Added a reproducible, non-overwriting generator and a fixture-integrity test.
- Created 01–16 folders covering history, individual document extraction, ratios, clean packages, arithmetic/identity/revenue mismatches, missing documents, page-specific evidence, scans, invalid PDFs, unit conversion, baseline comparison and the existing 32-PDF workload.
- Included source-authored ground truth, SHA-256 hashes, Vietnamese instructions and blank observation templates. All data is explicitly synthetic.

**Why:**
- Enable a small-to-large, repeatable manual testing sequence without inventing successful test history.

**Impact / verification:**
- Fixture-integrity pytest: 1 passed; Ruff checks passed for the new generator and test.
- Verified all 24 generated input hashes and retained 32 PDFs; visually reviewed representative document types, multi-page financials, scan and unit variant.
- No application/extraction performance test was run. No history was seeded. Related variants are development data, not independent holdout evidence; additional companies/layouts and API failure/concurrency tests remain necessary.

**Commits:** None.

### 2026-09-30 — Codex — Retain only the current 32-PDF test package

**What changed:**
- At the owner's request, recycled generated `data/samples`, `data/scenarios`, `data/scenarios_test`, `realistic_02`, `realistic_03` and the duplicate `realistic_01_upload_ready` package.
- Retained `data/realistic_scenarios/realistic_01` with 32 PDFs, manifest and ground truth. Compared SHA-256 hashes first to confirm the upload-ready PDFs were duplicates.
- Preserved source archives, verification evidence, existing benchmark reports and all generator code. No development-history entries were seeded.

**Why:**
- Simplify test inputs before preparing smaller controlled datasets.

**Impact:**
- Verified retained package still contains 32 PDFs. Deleted packages can be restored from Windows Recycle Bin. Old dataset-dependent commands require restoration or regeneration; historical reports are not fresh evaluation results. No application tests were run for this data-only cleanup.

**Commits:** None (not requested).

### 2026-09-30 — Codex — Empty development history workspace

**What changed:**
- Added global Development History navigation and a dedicated page with empty state, manual entries, linked follow-ups, filtering, paging and per-record JSON export.
- New analysis executions persist completion/failure metadata, a safe configuration allowlist and result snapshots automatically. Manual test entries default to not-run. No historical runs, fabricated test results or seed bugs are inserted.
- Storage uses one atomically-written JSON file per record under the existing mounted data directory, separate from source PDFs; no new dependency or database migration. App version is captured, not a verified Git revision. Optional manual version/evidence references remain self-reported.

**Why:**
- Owner wants visible evidence of future testing and improvements, starting from an empty history.

**Impact:**
- Seven focused backend tests passed (history plus existing job routes); five frontend citation tests passed; frontend production build passed; final Svelte check returned zero errors and zero warnings. Browser verified the empty live page and form defaults (`not_run` for tests, `open` for bugs); live history API confirmed zero entries. Test fixtures used temporary storage and no live seed records were created. New history/test files pass Ruff; existing FastAPI `File(...)` default lint findings in applications.py remain unrelated.
- History records remain after refresh/restart. Interrupted processes may lack terminal records; queued/in-progress jobs are still in-memory. Test runners are not automatically imported. JSON result exports are not full PDF backups and may contain sensitive information. Local file records are not tamper-proof.

**Commits:** None (not requested).

### 2026-09-26 — Codex — Verify redesigned dashboard in the browser

**What changed:** Completed browser QA for the presentation-only redesign and refreshed handoff status.

**Why:** Resume the interrupted dashboard readability task.

**Impact / verification:**
- Live synthetic package processed 32 PDF / 337 pages, zero failed documents; application `18f0933e-5bea-4eeb-8b80-89ba8c4cd9c0`.
- Verified Overview, Documents & Evidence and Technical Details navigation; filename search; grouped citation expansion; original audited PDF source page 4 → 5; Escape closes the source dialog.
- Checked 390px responsive viewport: no horizontal document overflow. Browser console reported no errors during this check.
- Frontend check: 0 errors/0 warnings; five unit tests passed; production build passed.
- Retrieval remains partial with seven excerpts and no selected collateral/conditions/forecast evidence. Model prose still sometimes confuses missing retrieved evidence with missing uploaded documents. These are existing analysis issues, not fixed by this UI-only task.

**Commits:** None requested or created.

### 2026-09-24 — Codex — Progressive-disclosure dashboard layout

**What changed:**
- Split results into Overview, Documents & Evidence and Technical Details, keeping all analysis data accessible without one long page.
- Separate processing completion from retrieval status and human-verification requirements. Show the original model headline without generating new claims; collapse full prose until requested.
- Replace five narrow 5C columns with expandable rows containing full reasoning, review flags and source links.
- Group adjacent citations without merging different claims; add source search and a native-dialog right-side PDF viewer with Escape/focus handling.
- Added citation-grouping regression tests and updated navigation instructions.

**Why:** The owner found the information density difficult to read and approved a presentation-only redesign.

**Impact:** Backend analysis, model output, ratings and retrieval logic are unchanged. Five frontend tests passed; Svelte check reports 0 errors/0 warnings; production build passed.

**Commits:** None requested or created.

### 2026-09-24 — Codex — Application-scoped RAG for 5C and summary

**What changed:**
- Added bounded retrieval for six evidence topics and validation findings. Supporting facility, management and forecast pages can enter both final-node prompts.
- Added application and embedding-space isolation; reject foreign, unknown, low-score and stub-mode evidence. Forecasts are labelled separately from actual results.
- Restricted citation candidates to supplied evidence and canonical metrics/findings. Added no-evidence/failure warnings and untrusted-document instructions.
- Exposed queries, chunks, excerpts, scores, warnings and consuming nodes in the API/frontend. Audit data remains part of in-memory results, not durable history.
- Added seven retrieval tests. No new dependencies or provider/topology changes.

**Why:** Continue the approved RAG phase so indexed supporting documents inform assessment.

**Impact / verification:**
- Backend: 90 passed, 1 skipped. Frontend: 3 passed, check 0 errors/0 warnings, production build passed.
- Real in-memory Qdrant plus fake LLM tests cover isolation, empty evidence, context budgets, forecast labels and a page-7-only supporting fact reaching both prompts. These tests do not prove claim correctness or prompt-injection resistance.
- Live 32-PDF RAG verification remains pending because Docker Desktop crashes during inference-manager initialization. The September 13 source-citation result does not verify this RAG implementation.
- Semantic-model selection, relevance calibration and durable application history remain pending.

**Commits:** None requested or created.

> Newest first. Mỗi entry là 1 lần làm việc đáng record.

### 2026-09-13 — Codex — Canonical assessment evidence and original-source citations

**What changed:**
- Final 5C/summary nodes consume saved validation findings, ratios, package totals and identity/coverage context rather than recomputing a smaller evidence set. Material deterministic warnings remain in the human-review checklist; fallback summaries use deduplicated package totals.
- Extractors preserve source page/text/bounding-box metadata through chunking, including multi-page financial periods. Missing provenance is not replaced by guessed page numbers.
- Successful API analyses retain original PDFs plus metadata. Source endpoints serve the original bytes and individual page previews after temporary-upload cleanup.
- Frontend citations use unique numbered references, filenames/pages, adjacent full-ID deduplication and a source catalogue. The source modal separates generated chunk context from extracted source text and the original PDF page. Upload rendering now supports different documents sharing a filename.

**Why:**
- Implement the first two priorities requested by the owner: consistent assessment evidence and usable, verifiable citations for the 32-document workload.

**Impact:**
- Backend suite: 83 passed, 1 live-Qdrant integration test skipped, one existing Google dependency deprecation warning. Frontend: 3 citation tests passed, type-check 0 errors/0 warnings, production build passed.
- Added regression coverage for canonical-state consumption, missing-month/duplicate warnings through the six-node realistic graph, multi-page provenance, same-name PDFs, archived-original integrity and page-preview endpoints.
- Live browser verification completed with the synthetic `realistic_01` workload: 32 PDFs / 337 pages, 0 failed files, 0 recoverable errors, 1,101 indexed chunks and 26 source references. The six node durations total approximately 64.7 seconds. Gemini and the live vector store completed this run; these figures are not a claim of semantic accuracy.
- Opened `audited_financials_2023.pdf` from a numbered citation: source text and original page 4 were displayed, switching to page 5 loaded the correct image and updated the PDF link. Different bank PDFs sharing the same filename uploaded successfully and kept different source numbers. Saved the API result to ignored `data/verification/2026-09-13-source-citations-result.json` for comparison.
- No new dependencies, provider/framework changes, Git branches or commits. Existing uncommitted work was preserved.
- Retrieval integration, semantic claim verification and durable application history remain planned work, not completed features.

**Commits:** None.

---

### 2026-09-13 — Codex — Semester 2 restart audit and master plan

**What changed:**
- Added `docs/SEMESTER_2_MASTER_PLAN.md` with a project refresher, verified implementation gaps, seven delivery stages, acceptance checks and a provisional schedule.
- Added a current restart baseline and marked the older status/next-step snapshot as historical.

**Why:**
- The project owner is returning after completing Semester 1 and requested a comprehensive plan before implementation.
- The new 32-document dashboard test needs a plan grounded in current code rather than older completion claims.

**Impact:**
- Backend: 73 passed, 1 skipped, one dependency deprecation warning; runtime 24.77 seconds. Frontend check: 0 errors, 0 warnings.
- Docker/health verified. No new live Gemini analysis or live-Qdrant integration run was performed.
- No application code, dependencies, Git branches or commits were changed. Existing uncommitted work was preserved.

**Commits:** None.

---

### 2026-05-28 — Claude (Opus 4.7) — Add pending-milestones follow-up system

**What changed:**
- Thêm mục `## Pending milestones — agent phải hỏi user` vào đầu
  PROGRESS.md (ngay sau Onboarding prompt). Bảng 5 cột: Item / Started /
  ETA / Cách hỏi user.
- 5 item ban đầu: title approval (ETA 2026-05-31), supervisor
  assignment, SUS user study, real anonymised documents, Gemini API key
  rotation.
- Cập nhật onboarding prompt template: agent phải scan mục này và hỏi
  user về item nào đã quá ETA TRƯỚC khi nhận task mới.
- Cập nhật rules: khi pending milestone resolve → move sang Current
  status; khi xuất hiện milestone mới → thêm vào bảng với ETA.

**Why:**
- User cần "agent hỏi proactive" để không quên follow-up những thứ
  blocking ngoài tầm kiểm soát của code (vd: chờ supervisor, chờ
  approve administrative).
- Tránh tình trạng user nhớ ra việc cần làm khi đã muộn.

**Impact:**
- Mỗi agent kế tiếp khi vào session sẽ check ETA và hỏi user → user
  không phải tự nhớ.
- Notepad prompt template bạn lưu trước đó nên copy lại từ PROGRESS.md
  (mục "Onboarding prompt cho agent mới") để có version mới.

**Commits:** *(uncommitted khi viết entry này)*

---

### 2026-05-28 — User — FYP title submitted to FYPPGBank portal

**What changed:**
- Submitted FYP title *"An Agentic AI System for Multi-Document Financial
  Analysis and Explainable Risk Summarization in Malaysian SME Lending"*
  to the FYPPGBank portal.
- Updated `## Current status` + `## Next steps` to reflect submission.

**Why:**
- Administrative requirement before APU assigns a supervisor.
- Was the #1 priority item in the previous "Next steps" list.

**Impact:**
- Approval expected within 2-3 days (~2026-05-31).
- Supervisor assignment unblocks once approved.
- SUS user study + Real document benchmarking can proceed once supervisor
  is in place (some require supervisor authorisation).

**Commits:** *(no code change — admin milestone)*

---

### 2026-05-28 — Claude (Opus 4.7) — Add SUS user study kit + progress tracking

**What changed:**
- Tạo [`docs/USER_STUDY_KIT.md`](docs/USER_STUDY_KIT.md): recruitment guide, demo script 10-phút, Google Form template, consent form template, scoring workflow.
- Tạo [`backend/scripts/score_sus.py`](backend/scripts/score_sus.py): đọc CSV export từ Google Forms, scoring theo Brooke 1986, in mean/median/stdev + verdict PASS/FAIL vs target 70.
- Tạo [`data/sus_responses_template.csv`](data/sus_responses_template.csv): CSV template với đúng SUS column order.
- Tạo **chính file này** ([`PROGRESS.md`](PROGRESS.md)) — log cho mọi agent tương lai.

**Why:**
- User cần plan rõ "sau khi hệ thống xong thì làm gì" — Phase 7 timeline.
- User dự kiến không dùng Claude sau tháng này, cần file lịch sử để agent kế tiếp (Cursor / Copilot / codex / v.v.) tiếp tục được.

**Impact:**
- SUS metric pipeline hoàn chỉnh end-to-end (template → form → scoring).
- Test suite không đổi (50 passing, 1 skipped).
- Verified: `python -m scripts.score_sus data/sus_responses_template.csv` với 2 fake rows → mean 86.25 → PASS.

**Commits:** *(uncommitted at time of writing this entry — commit pending user approval)*

---

### 2026-05-28 — Claude (Opus 4.7) — Add manual testing guide (md + xlsx)

**What changed:**
- Tạo [`docs/TESTING_GUIDE.md`](docs/TESTING_GUIDE.md): hướng dẫn manual test từng bước tiếng Việt, 4 scenarios (happy path + 2 cross-doc edge cases + evaluation harness), checkpoints "kết quả đúng phải nhìn thế nào".
- Tạo [`backend/scripts/export_testing_guide.py`](backend/scripts/export_testing_guide.py): Python script convert guide → multi-sheet Excel workbook với dropdown PASS/FAIL/SKIP cho từng step.
- Generated [`docs/TESTING_GUIDE.xlsx`](docs/TESTING_GUIDE.xlsx): 10 sheets (Overview + Summary + Pre-check + 4 Scenarios + Cleanup + Troubleshooting + Supervisor Q&A).
- Added `openpyxl>=3.1.5` to backend dev dependencies.

**Why:**
- User cần file để tự test manual mà không cần Claude hỗ trợ runtime.
- Format Excel tiện hand-off cho supervisor hoặc QA reviewer.

**Impact:**
- No production code change. Test suite không đổi.

**Commits:** *(uncommitted at time of writing — commit pending user approval)*

---

### 2026-05-27 — Claude (Opus 4.7) — Phase 6: 4 doc types + financial ratios + evaluation harness

**What changed:**
- **Audited financials ingestion**: `app/ingestion/financials_synthetic.py` (ReportLab 2-page PDF generator), `financials_extractor.py` (label-based with parentheses → negative handling), chunker emits summary + per-period chunks.
- **Tax return (Form C) ingestion**: `tax_synthetic.py`, `tax_extractor.py`, chunker.
- **Pipeline router** (`app/ingestion/router.py`): detect doc kind by header keywords; extract_node routes to matching extractor.
- **Financial ratios** (`app/ratios/financial_ratios.py`): Current Ratio, Debt-to-Equity, Net Profit Margin, Interest Coverage, estimated DSR — mỗi ratio có band classification + formula + explanation.
- **Cross-doc checks mới**: declared income vs annualised bank deposits, audited revenue vs tax-declared, financials company name vs SSM.
- **Evaluation harness** (`app/evaluation/`): extraction_accuracy.py, faithfulness.py, latency.py, sus.py + `scripts/evaluate.py` unified runner with JSON dump + PASS/FAIL exit code.
- Fixed `.gitignore` bug: unanchored `lib/` pattern was hiding `frontend/src/lib/`. Changed to `/lib/` + `/lib64/`.
- Fixed citation regex để parse comma-joined chunk_ids trong cùng cặp `[...]` (LLM quirk).

**Why:**
- Proposal Section 12 mandates: extraction >90%, faithfulness 0 hallucinations, latency <180s, SUS >70.
- Cross-doc validation là core research contribution (vs prior work AI-BAAM).

**Impact:**
- Test suite 38 → 50 passing.
- Evaluation harness verified vs real Gemini: extraction 100%, faithfulness 100%, latency p95 ~59s. 3/4 metrics auto-PASS.
- `frontend/src/lib/` recovered (5 files) — Phase 5 commit had silently dropped them due to `.gitignore` bug.

**Commits:** `ea32292`

---

### 2026-05-27 — Claude (Opus 4.7) — Phase 5: SvelteKit loan-officer dashboard

**What changed:**
- Bootstrap SvelteKit minimal TS project at `frontend/` (`sv create --template minimal`).
- Tailwind v4 via `@tailwindcss/vite`. Vite proxy `/api → localhost:8000`.
- Components: `CitedText.svelte` (renders inline citation tags), `ChunkModal.svelte` (resolves chunk_id → source row).
- Single-page demo: drag-drop multi-PDF upload → 30-60s spinner → cards (Risk summary / 5C grid / Validation findings / Bank metrics / Reasoning trail).
- Citations clickable; modal shows kind + page + source text + raw metadata.
- New backend endpoint `POST /api/applications/analyse` (multi-file upload, runs graph, returns full state) + `GET /api/applications/chunks/{document_id:path}/{kind}/{index}`.

**Why:**
- Proposal Section 4 Objective 4 — loan officer dashboard.
- FEATERS Explainability requires UI surface for citation traceability.

**Impact:**
- Manual end-to-end verified: upload 2 PDFs → Risk summary với clickable citations.
- TypeScript: 0 errors / 3 warnings.

**Commits:** `455e419`

---

### 2026-05-27 — Claude (Opus 4.7) — Phase 4: SSM ingestion + cross-doc validation

**What changed:**
- SSM Form 9 synthetic generator + label-based extractor.
- `DocumentKind` enum + `detect_document_kind()` router.
- `extract_node` routes by kind; supports bank_statement + ssm_registration.
- Cross-doc check `cross_doc.py`: holder name match (S/B ↔ SDN BHD normalisation), incorporation date predates activity.
- `validate_node` + `ratios_node` + `assess_5c_node` + `summarise_node` filter by kind.

**Why:**
- Multi-doc cross-validation là core research contribution.
- SSM is structurally simplest doc type → good 2nd integration.

**Impact:**
- Test suite 20 → 26 passing.
- End-to-end với bank + SSM: 0 inconsistencies (synthetic ACME data consistent).

**Commits:** `52d86f3`

---

### 2026-05-27 — Claude (Opus 4.7) — Phase 3b: 4 LLM nodes (validate, ratios, 5C, summarise)

**What changed:**
- `app/validation/checks.py`: 4 deterministic checks (balance arithmetic, running balance, date period/order, duplicate detection).
- `app/ratios/bank_statement_metrics.py`: cash-flow metrics.
- `app/ratios/five_c.py`: 5C Pydantic schema + prompt builder.
- `app/explainability/summary.py`: RiskSummary schema + prompt + citation extractor.
- `app/core/llm.py`: provider-agnostic LLM wrapper với `generate_structured(prompt, schema)`.
- 4 nodes mới: validate, ratios, assess_5c, summarise.
- Graph linear `START → parse → extract → validate → ratios → assess_5c → summarise → END`.
- Citation validation: hallucinated chunk_ids logged thành recoverable error.

**Why:**
- Proposal Section 9 6-step workflow hoàn chỉnh.
- FEATERS Accountability: monotonic state, audit-friendly trace.

**Impact:**
- Test suite 12 → 20 passing.
- End-to-end real Gemini 2.5 Flash: ~28s total, 1+ citations, all validated.

**Commits:** `a7fb952`

---

### 2026-05-27 — Claude (Opus 4.7) — Phase 3a: LangGraph skeleton + parse/extract nodes

**What changed:**
- `AgentState` TypedDict với reasoning trail (`Annotated[list[ReasoningStep], operator.add]`).
- `parse_node` + `extract_node` thin-wrap deterministic ingestion services.
- `compile_graph()` (in-memory) + `compile_graph_with_postgres()` (Postgres checkpointer).
- `gemini-2.5-flash` mặc định cho reasoning nodes.
- Added `langgraph-checkpoint-postgres` dep.
- Bug fix: parsed_pages handoff giữa nodes (private key bị LangGraph drop).
- Bug fix: document_id collision khi multiple PDFs cùng basename — dùng `parent.name/stem`.

**Why:**
- Foundation cho 4 LLM nodes phase tiếp theo.
- Postgres checkpointer = FEATERS audit trail durable.

**Impact:**
- Test suite 7 → 12 passing.

**Commits:** `2ca3985`

---

### 2026-05-27 — Claude (Opus 4.7) — Migrate to google-genai SDK

**What changed:**
- Replaced deprecated `google-generativeai` với `google-genai`.
- Embeddings: `text-embedding-004` → `gemini-embedding-001` với `output_dimensionality=768` (giữ Qdrant collection size unchanged).

**Why:**
- `google-generativeai` end-of-life. `text-embedding-004` removed từ v1beta API.

**Impact:**
- Real semantic ranking giờ hoạt động đúng (trước stub embeddings không có signal). Score quality: summary query → kind=summary 0.71, transaction query → kind=transaction 0.66+.

**Commits:** `b5508dc`

---

### 2026-05-27 — Claude (Opus 4.7) — Phase 2: bank statement → Qdrant vertical slice

**What changed:**
- Synthetic Maybank-style PDF generator với ground truth JSON.
- PyMuPDF parser preserving bounding boxes per text span.
- Heuristic bank statement extractor (header + transaction rows + footer totals).
- Citation-preserving chunker: 1 summary + 1 per transaction.
- Provider-agnostic Gemini embeddings + stub fallback (offline tests).
- Qdrant store: upsert + filtered semantic search.
- `POST /api/documents/ingest` + `GET /api/documents/search` endpoints.
- Verified end-to-end against live Qdrant 1.18.1 container.

**Why:**
- Proposal Phase 2 deliverable.
- Bank statement = most-volumed doc type per SME application.

**Impact:**
- First working pipeline. 8 tests passing.

**Commits:** `d667830`

---

### 2026-05-27 — Claude (Opus 4.7) — Scaffold monorepo structure

**What changed:**
- `backend/` (FastAPI domain-driven layout, uv-managed) + `frontend/` placeholder + `infra/docker/` + `data/` (gitignored) + `docs/` (FYP_Proposal.md + FYP_Context.md moved here).
- `docker-compose.yml`: postgres + redis + qdrant + backend (+ frontend profile).
- `Makefile`: `make up / down / test / lint / fmt / backend`.

**Why:**
- Foundation cho mọi phase tiếp theo.
- Architecture decisions locked: flat monorepo, domain-driven backend, uv, full Docker stack.

**Impact:**
- Repo skeleton ready.

**Commits:** `691852c`

---

### 2026-05-27 — User — Initial commit

**What changed:**
- `README.md`, `.gitignore` (Python-flavoured), `.gitattributes`.

**Commits:** `b6388d5`

---

## Glossary cho agent mới

- **chunk_id**: `{document_id}:{kind}:{index}`. Ví dụ `bank_statement_2026-01-01:transaction:5`. Đây là đơn vị citation. Mọi LLM output reference phải dùng format này.
- **FEATERS**: 7 BNM principles cho AI ở financial sector — Fairness/Ethics/Accountability/Transparency/Explainability/Reliability/Security. Project tập trung Explainability + Accountability.
- **5C**: Character / Capacity / Capital / Collateral / Conditions — credit assessment framework.
- **DocumentKind**: enum 5 giá trị — `bank_statement`, `ssm_registration`, `audited_financials`, `tax_return`, `unknown`.
- **AgentState**: LangGraph state TypedDict — slot per domain output + accumulated `trace` + `errors`.
- **ReasoningStep**: 1 entry per node trong trace. Có `started_at`, `finished_at`, `summary`, `inputs`, `outputs`, `citations`.
- **Inconsistency**: 1 validation finding. Có `code` + `severity` (info/warning/critical) + `citations`.

## Helpful one-liners cho agent mới

```bash
# Verify dev env
docker ps                                      # docker daemon up?
curl http://localhost:6333/                    # Qdrant alive?
curl http://localhost:8000/health              # Backend alive?

# Run things
docker compose up -d qdrant postgres           # infra only
cd backend && uv run uvicorn app.main:app --reload
cd frontend && npm run dev

# Tests + evaluation
cd backend && uv run pytest tests/             # 50 tests, 1 skipped
cd backend && uv run python -m scripts.evaluate --runs 2   # 4-metric report

# SUS scoring (when responses available)
cd backend && uv run python -m scripts.score_sus ../data/sus_responses.csv

# Regenerate sample PDFs
cd backend && uv run python -m app.ingestion.synthetic ../data/samples
cd backend && uv run python -m app.ingestion.ssm_synthetic ../data/samples
cd backend && uv run python -m app.ingestion.financials_synthetic ../data/samples
cd backend && uv run python -m app.ingestion.tax_synthetic ../data/samples
```
