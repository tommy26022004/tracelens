# FYP Project Context — Tran Quang Dat

> Đây là file context để paste vào chat mới, giúp AI hiểu ngay toàn bộ background và quyết định đã được đưa ra. Không cần giải thích lại từ đầu.

---

## 1. Thông tin sinh viên

- **Tên:** Tran Quang Dat (TP079959)
- **Trường:** Asia Pacific University (APU), Malaysia
- **Ngành:** Bachelor of IT, chuyên ngành FinTech — năm cuối
- **Email:** TP079959@mail.apu.edu.my
- **Status:** Đang chuẩn bị submit FYP title proposal lên FYPPGBank portal

---

## 2. Kinh nghiệm thực tập

**Công ty:** Kollect Systems Sdn Bhd, Kota Damansara, Selangor
**Vị trí:** Full-Stack Software Engineering Intern (January – April 2026)
**Mô tả:** Enterprise FinTech platform — debt collection, receivables management, e-invoicing, AI workflow automation cho doanh nghiệp tài chính

**Những gì đã build trong thực tập:**
- JWT authentication pipeline (login, token rotation, secure cookie handling)
- Dashboard Widgets module (frontend + backend API)
- GDPR-compliant DSAR module + Forgot Password flow
- **ReAct Analytics Agent dùng LangGraph** — natural language → multi-step SQL reasoning
- Debugged cross-session data leakage (datasource isolation failure)
- System Integration Testing (SIT)

**Tech stack đã dùng trong production:**
- Languages: Python, Java, TypeScript, JavaScript
- Backend: Spring Boot, FastAPI, Spring WebFlux, REST API, JWT
- Frontend: SvelteKit, HTML/CSS, ASP.NET
- Databases: PostgreSQL, MySQL, Redis, **Qdrant** (vector DB), DynamoDB
- DevOps: Docker, Microservices, AWS Lambda, AWS Amplify, Git
- AI: **LangGraph, ReAct Agent, LLM Integration, Amazon Bedrock, Amazon Comprehend**

---

## 3. FYP Title đã chọn

> **"An Agentic AI System for Multi-Document Financial Analysis and Explainable Risk Summarization in Malaysian SME Lending"**

---

## 4. Tóm tắt dự án

**Vấn đề giải quyết:**
Loan officer tại các tổ chức tài chính Malaysia phải manually đọc và cross-verify nhiều loại document tài chính của SME (bank statements, audited financials, SSM registration, tax returns) trước khi ra quyết định cho vay. Quá trình này mất 2–6 tuần, dễ sai, thiếu nhất quán, và không có structured explanation cho SME bị reject.

**Giải pháp:**
Một AI agent pipeline tự động:
1. Parse và extract figures từ nhiều loại document Malaysia
2. Cross-validate giữa các documents (ví dụ: declared revenue vs actual bank deposits)
3. Reason qua 5C credit framework (Character, Capacity, Capital, Collateral, Conditions)
4. Generate explainable risk summary bằng ngôn ngữ tự nhiên cho loan officer

**Quan trọng:** System KHÔNG ra quyết định cho vay — chỉ summarize để human loan officer quyết định.

---

## 5. Research Gap (tại sao chưa ai làm)

| Dimension | Existing Work | Project này |
|---|---|---|
| Geography | US/Western (Lama AI, Casca, Ocrolus) | Malaysia-specific formats + BNM regulatory context |
| Document scope | Single document (AI-BAAM: bank statements only) | Multi-document cross-validation |
| Reasoning | Rule-based hoặc single-pass LLM | Multi-step ReAct agent |
| Explainability | Post-hoc (SHAP) | Natively source-traced |
| Regulatory | Không cite | BNM FEATERS-compliant |

**Core gap statement:**
> *"No deployed system in Malaysia performs multi-document LLM agent reasoning for SME credit assessment that produces natively explainable outputs compliant with BNM's FEATERS framework."*

**Key references:**
- AI-BAAM (arXiv:2510.16066) — paper Malaysia gần nhất, chỉ làm single document
- BNM Discussion Paper on AI in Malaysian Financial Sector (August 2025) — cite regulatory motivation
- SME Finance Forum — $5.2 trillion global MSME financing gap

---

## 6. Tech Stack cho FYP

| Component | Technology | Ghi chú |
|---|---|---|
| Agent orchestration | **LangGraph** | Đã dùng ở Kollect |
| LLM | **Google Gemini API** (free tier) | Thay Amazon Bedrock vì không có budget — provider-agnostic design |
| Document parsing | **PyMuPDF + pdfplumber** | Phần mới cần học |
| OCR | **Tesseract** hoặc Google Document AI free tier | Cho scanned documents |
| Vector DB | **Qdrant** | Đã dùng ở Kollect |
| Backend | **FastAPI** | Đã dùng ở Kollect |
| Frontend | **SvelteKit** | Đã dùng ở Kollect |
| Database | **PostgreSQL + Redis** | Đã dùng ở Kollect |
| Infrastructure | **Docker + localhost** | Demo locally, không cần cloud |

**Lý do dùng Gemini thay Bedrock:** Không có GPU, không có budget. Gemini Flash free tier (1500 req/day) đủ cho FYP workload. Design provider-agnostic để production có thể swap sang Bedrock.

---

## 7. SDG Alignment

- **SDG 8** (primary): Decent Work & Economic Growth — SME access to financing
- **SDG 10** (secondary): Reduced Inequalities — giảm bias trong credit decisions

---

## 8. Targeted Users

- **Primary:** Loan Officer — review AI summary, quyết định cuối
- **Secondary:** Credit Committee — portfolio-level consistency
- **Indirect:** SME Applicant — faster turnaround, structured feedback

---

## 9. Agent Workflow (high-level)

```
INPUT: SME Loan Package (Bank Statements x6, Audited Financials, SSM Form, Tax Returns)
  ↓
STEP 1: Document Parsing & Chunking → store embeddings in Qdrant
  ↓
STEP 2: Financial Extraction → revenue, EBITDA, cash flow, deposits per month
  ↓
STEP 3: Cross-Document Validation → flag inconsistencies với severity level
  ↓
STEP 4: Ratio Calculation → DSR, Debt-to-Equity, Current Ratio, Net Profit Margin
  ↓
STEP 5: 5C Assessment → Character, Capacity, Capital, Collateral, Conditions
  ↓
STEP 6: Risk Summary Generation → natural language, every claim cited to source
  ↓
OUTPUT: Structured Risk Summary → Loan Officer Dashboard (SvelteKit)
```

---

## 10. Độ phức tạp thực tế

```
Độ phức tạp tổng thể: 7/10
Độ phức tạp với background của Dat: 4/10
```

| Phần | Status | Effort |
|---|---|---|
| FastAPI + SvelteKit + JWT + PostgreSQL + Redis + Docker | Đã biết từ Kollect | Thấp |
| LangGraph ReAct Agent + Qdrant | Đã biết, cần deepen | Trung bình |
| Document parsing pipeline (PyMuPDF, OCR, Malaysian formats) | **Chưa làm — phần mới nhất** | Cao |

**Phần khó nhất không phải AI — mà là làm cho OCR đọc đúng Malaysian bank statement format.** Đây cũng là research contribution thực sự.

---

## 11. Chi phí

**Gần như $0** — toàn bộ stack là open source + free tier.
- Gemini API: free (1500 req/day)
- Qdrant: self-hosted free
- Tất cả còn lại: open source

---

## 12. File đã tạo

- [FYP_Proposal.md](FYP_Proposal.md) — full proposal document (Introduction, Problem Statement, Aim, Objectives, Research Gap, Architecture, Workflow, Tech Stack, Timeline, Evaluation Metrics, Ethics, References)

---

## 13. Những gì CHƯA làm / bước tiếp theo

- [ ] Submit title lên FYPPGBank portal
- [ ] Chọn preferred supervisors
- [ ] Bắt đầu setup project repository
- [ ] Research PyMuPDF + pdfplumber cho Malaysian bank statement formats
- [ ] Prototype document parsing pipeline đầu tiên

---

*Context file generated: May 2026 — paste toàn bộ file này vào đầu chat mới để tiếp tục.*
