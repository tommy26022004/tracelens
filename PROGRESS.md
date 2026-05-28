# Project Progress Log

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

1. ✅ **Submit FYP title to FYPPGBank portal** — done 2026-05-28, awaiting approval (~2-3 days).
2. **Wait for title approval + supervisor assignment** (~2026-05-31 expected).
3. **Run SUS user study** — 5-10 participants, follow [`docs/USER_STUDY_KIT.md`](docs/USER_STUDY_KIT.md).
4. **Manual test pass** — follow [`docs/TESTING_GUIDE.md`](docs/TESTING_GUIDE.md) / `.xlsx` để confirm tất cả 4 scenario PASS.
5. **(Optional) Real anonymised SME documents** — xin từ supervisor, re-run `scripts/evaluate.py` để đo accuracy trên real data.
6. **(Optional) Ablation study** — bật/tắt cross-doc validation, đo impact lên 5C ratings.
7. **Write FYP final report** — Chapters 1-7 + appendices.

---

## Known issues / debt

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

> Newest first. Mỗi entry là 1 lần làm việc đáng record.

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
