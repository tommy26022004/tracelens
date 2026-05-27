# Final Year Project Proposal
## Asia Pacific University (APU) Malaysia
### Bachelor of Information Technology (FinTech)

---

**Student Name:** Tran Quang Dat
**Student ID:** TP079959
**Email:** TP079959@mail.apu.edu.my
**Programme:** BSc (Hons) Information Technology (FinTech)
**Date:** May 2026

---

# Project Title

**An Agentic AI System for Multi-Document Financial Analysis and Explainable Risk Summarization in Malaysian SME Lending**

---

# 1. Introduction

Small and Medium Enterprises (SMEs) represent 97% of all businesses in Malaysia and contribute approximately 38% of the national GDP. Despite their economic significance, SMEs face a severe financing gap — Bank Negara Malaysia (BNM) and the SME Finance Forum estimate a global MSME financing gap of USD 5.2 trillion, of which Malaysia is a significant contributor.

The core bottleneck is not the absence of creditworthy SMEs, but the inefficiency of the manual credit assessment process. Loan officers at Malaysian financial institutions must manually collect, read, and cross-verify multiple financial documents — bank statements, audited financial statements, SSM registration records, and tax returns — before producing a credit assessment memo. This process typically takes 2 to 6 weeks per application and is highly susceptible to human error, inconsistency, and implicit bias.

Artificial intelligence has demonstrated strong potential in automating parts of this workflow. However, existing commercial AI lending systems (e.g., Lama AI, Casca, Ocrolus) are built for Western markets and are not adapted to Malaysian document formats, local regulatory frameworks (BNM), or the specific document ecosystem of Malaysian SMEs (e.g., SSM Form 9/24/49, CCRIS/CTOS reports, Peppol e-invoices). The most advanced Malaysia-specific academic work (AI-BAAM, 2024) addresses only single-document bank statement analysis and does not perform cross-document reasoning.

Furthermore, BNM's Discussion Paper on Artificial Intelligence in the Malaysian Financial Sector (August 2025) introduces the FEATERS principles — Fairness, Ethics, Accountability, Transparency, Explainability, Reliability, and Security — as mandatory requirements for AI used in credit assessment. No existing deployed system in Malaysia has demonstrated compliance with these explainability requirements within a multi-document LLM reasoning architecture.

This project proposes to fill that gap by building a production-grade agentic AI system that automates multi-document financial analysis for SME loan applications in the Malaysian context, producing explainable risk summaries that support — not replace — human loan officer judgment.

---

# 2. Problem Statement

Malaysian SME loan officers currently perform the following steps manually for every application:

1. Collect and verify completeness of document packages
2. Manually transcribe financial figures from PDFs into spreadsheet models (financial spreading)
3. Cross-check consistency across multiple documents (e.g., declared revenue vs. actual bank deposits)
4. Calculate financial ratios (Debt Service Ratio, Debt-to-Equity, Current Ratio, Net Profit Margin)
5. Assess qualitative factors (business model viability, management quality)
6. Write a credit assessment memo for the credit committee

This process has four critical problems:

- **Speed:** 2–6 weeks per application creates a financing access gap for SMEs with urgent capital needs
- **Accuracy:** Manual data entry from scanned documents introduces transcription errors
- **Consistency:** Different loan officers apply subjective judgment inconsistently across applications
- **Explainability:** Rejected applicants receive no structured feedback, preventing them from improving their applications

---

# 3. Aim

To design, develop, and evaluate an agentic AI system that can automatically extract, cross-validate, and reason across multiple financial documents submitted by Malaysian SMEs, producing structured and explainable risk summaries that assist loan officers in making faster and more consistent credit decisions.

---

# 4. Objectives

1. **To develop a multi-document ingestion pipeline** capable of parsing Malaysian SME financial documents (bank statements, audited financials, SSM registration, tax returns) using OCR and document intelligence techniques

2. **To implement a ReAct-based AI agent** using LangGraph that performs multi-step reasoning across extracted financial data, cross-validates figures between documents, and calculates standard credit assessment metrics (5C framework)

3. **To design an explainability layer** that generates structured, natural-language risk summaries aligned with BNM's FEATERS explainability requirements, enabling loan officers to trace each risk flag back to its source document and data point

4. **To build a loan officer dashboard** that presents the AI-generated risk summary, document consistency flags, key financial ratios, and recommended areas for further human review

5. **To evaluate the system** against real-world SME loan application scenarios, measuring document extraction accuracy, cross-validation correctness, reasoning quality, and loan officer usability

---

# 5. Research Gap

| Dimension | Existing Work | This Project |
|---|---|---|
| Geography | US/Western markets (Lama AI, Casca, Ocrolus) | Malaysia-specific document formats and regulatory context |
| Document scope | Single document type (AI-BAAM: bank statements only) | Multi-document cross-validation |
| Reasoning approach | Rule-based extraction or single-pass LLM | Multi-step ReAct agent reasoning |
| Explainability | Post-hoc methods (SHAP, attention maps) | Natively explainable, source-traced reasoning |
| Regulatory alignment | None cited | BNM FEATERS-compliant design |
| Human-in-the-loop | Varies | Explicit — agent assists, officer decides |

**Core research gap statement:**
> *No deployed system in Malaysia performs multi-document LLM agent reasoning for SME credit assessment that produces natively explainable outputs compliant with BNM's FEATERS framework.*

---

# 6. Targeted Users

| User | Role | How They Use the System |
|---|---|---|
| **Loan Officer** | Primary user | Reviews AI-generated risk summary, uses consistency flags to prioritize manual review, makes final credit decision |
| **Credit Committee** | Secondary user | Reviews standardized summaries across applications for portfolio-level consistency |
| **SME Applicant** | Indirect beneficiary | Faster decision turnaround; structured feedback if application is flagged |

---

# 7. SDG Alignment

| SDG | Target | Relevance |
|---|---|---|
| **SDG 8: Decent Work and Economic Growth** | 8.3, 8.10 | Primary alignment — accelerates SME access to financing, which drives employment and economic output |
| **SDG 10: Reduced Inequalities** | 10.2, 10.5 | Secondary alignment — consistent AI assessment reduces loan officer subjectivity and bias against thin-file SMEs, women-owned businesses, and minority entrepreneurs |
| **SDG 1: No Poverty** | 1.4 | Indirect alignment — SME credit access is an upstream driver of household income and reduces informal economy dependency |

---

# 8. Proposed System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     LOAN OFFICER DASHBOARD                  │
│              (SvelteKit Frontend)                           │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST API
┌──────────────────────────▼──────────────────────────────────┐
│                    FASTAPI BACKEND                          │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              DOCUMENT INGESTION LAYER               │   │
│  │  PyMuPDF + Amazon Textract                          │   │
│  │  Supports: Bank Statements, Audited Financials,     │   │
│  │  SSM Registration, Tax Returns (Form C/B/BE)        │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                   │
│  ┌──────────────────────▼──────────────────────────────┐   │
│  │           VECTOR STORAGE & RETRIEVAL                │   │
│  │  Qdrant — stores chunked document embeddings        │   │
│  │  for semantic retrieval during agent reasoning      │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                   │
│  ┌──────────────────────▼──────────────────────────────┐   │
│  │           REACT AGENT (LangGraph)                   │   │
│  │                                                     │   │
│  │  Tools available to agent:                          │   │
│  │  - extract_financials(document_id, fields)          │   │
│  │  - cross_validate(field, doc_a, doc_b)              │   │
│  │  - calculate_ratio(ratio_type, values)              │   │
│  │  - flag_inconsistency(description, severity)        │   │
│  │  - retrieve_context(query)                          │   │
│  │  - generate_summary(findings)                       │   │
│  │                                                     │   │
│  │  Reasoning loop:                                    │   │
│  │  Thought → Action → Observation → Thought → ...    │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                   │
│  ┌──────────────────────▼──────────────────────────────┐   │
│  │              LLM LAYER                              │   │
│  │  Amazon Bedrock (Claude)                            │   │
│  │  - Financial figure extraction                      │   │
│  │  - Natural language reasoning                       │   │
│  │  - Risk summary generation                          │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                   │
│  ┌──────────────────────▼──────────────────────────────┐   │
│  │           EXPLAINABILITY LAYER                      │   │
│  │  - Every risk flag traced to source document        │   │
│  │  - Every figure cited with page/section reference   │   │
│  │  - Reasoning chain stored and auditable             │   │
│  │  - BNM FEATERS compliant output format              │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    DATABASE LAYER                           │
│  PostgreSQL — application data, audit logs                  │
│  Redis — session cache, job queue                           │
└─────────────────────────────────────────────────────────────┘
```

---

# 9. Agent Reasoning Workflow

```
INPUT: SME Loan Application Package
(Bank Statements x6, Audited Financials x2, SSM Form, Tax Return x2)
        │
        ▼
┌───────────────────┐
│  STEP 1           │
│  Document Parsing │  ← PyMuPDF + Textract OCR
│  & Chunking       │  ← Store embeddings in Qdrant
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  STEP 2           │
│  Financial        │  ← Agent extracts: Revenue, EBITDA,
│  Extraction       │    Net Profit, Total Assets, Liabilities,
│                   │    Cash Flow, Bank Deposits per month
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  STEP 3           │
│  Cross-Document   │  ← Compare: Declared revenue (financials)
│  Validation       │    vs. Actual deposits (bank statements)
│                   │  ← Compare: Tax declared income vs. financials
│                   │  ← Flag inconsistencies with severity level
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  STEP 4           │
│  Ratio            │  ← Calculate: DSR, Debt-to-Equity,
│  Calculation      │    Current Ratio, Net Profit Margin,
│                   │    Interest Coverage Ratio
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  STEP 5           │
│  5C Assessment    │  ← Character: Payment history patterns
│                   │  ← Capacity: Cash flow vs. loan repayment
│                   │  ← Capital: Equity position
│                   │  ← Collateral: Asset coverage
│                   │  ← Conditions: Industry risk context
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  STEP 6           │
│  Risk Summary     │  ← Natural language summary
│  Generation       │  ← Every claim cited to source document
│                   │  ← Inconsistencies highlighted
│                   │  ← Recommended areas for human review
└────────┬──────────┘
         │
         ▼
OUTPUT: Structured Risk Summary Report
→ Presented to Loan Officer on Dashboard
→ Human makes final credit decision
```

---

# 10. Tech Stack

| Layer | Technology | Justification |
|---|---|---|
| Agent Orchestration | LangGraph | Production-grade ReAct agent framework; used in internship |
| LLM | Amazon Bedrock (Claude) | Enterprise-grade, Malaysian data residency options, used in internship |
| Document Parsing | PyMuPDF + Amazon Textract | Handles scanned PDFs, handwritten documents, mixed layouts |
| Vector Database | Qdrant | High-performance semantic search; used in internship |
| Backend Framework | FastAPI | Async, production-ready, used in internship |
| Frontend | SvelteKit | Reactive dashboard UI; used in internship |
| Relational Database | PostgreSQL | Audit logs, application data, reasoning chain storage |
| Cache / Queue | Redis | Job queue for async document processing |
| Infrastructure | Docker + AWS Lambda | Containerized microservices; used in internship |
| Authentication | JWT | Secure session management; built from scratch in internship |

---

# 11. Project Timeline

| Phase | Duration | Deliverables |
|---|---|---|
| **Phase 1: Research & Design** | Month 1–2 | Literature review, system design document, architecture diagram, ethics form submission |
| **Phase 2: Document Pipeline** | Month 2–3 | OCR pipeline, document parser for all 4 document types, Qdrant ingestion |
| **Phase 3: Agent Development** | Month 3–5 | LangGraph ReAct agent, all 6 tools implemented, cross-validation logic |
| **Phase 4: Explainability Layer** | Month 5–6 | Source-traced output format, FEATERS-aligned summary generator |
| **Phase 5: Dashboard** | Month 6–7 | SvelteKit frontend, loan officer UI, risk summary display |
| **Phase 6: Evaluation** | Month 7–9 | Test against SME loan scenarios, accuracy metrics, usability testing |
| **Phase 7: Write-up & Submission** | Month 9–12 | Final report, presentation, poster |

---

# 12. Evaluation Metrics

| Metric | What It Measures | Target |
|---|---|---|
| Document extraction accuracy | Correct financial figures extracted vs. ground truth | > 90% |
| Cross-validation correctness | Inconsistencies correctly identified | > 85% |
| Ratio calculation accuracy | Financial ratios correctly computed | > 95% |
| Summary faithfulness | No hallucinated figures in generated summary | 0 hallucinations on cited figures |
| Loan officer usability | System Usability Scale (SUS) score from user testing | > 70 (Good) |
| Processing time | Time from document upload to summary generation | < 3 minutes |

---

# 13. Ethical Considerations

- **Human-in-the-loop:** The system produces summaries only. All credit decisions are made by human loan officers. The system cannot approve or reject any loan application.
- **Data privacy:** All SME financial documents contain sensitive business information. The system will implement encryption at rest and in transit, access control via JWT, and audit logging of all data access — consistent with PDPA Malaysia requirements.
- **Bias mitigation:** The system does not use demographic variables (race, gender, nationality) in its reasoning. Risk flags are based solely on financial data and document consistency.
- **Hallucination prevention:** Every figure in the generated summary must be cited to a specific source document and page. Any figure the agent cannot verify will be flagged as "unverified" rather than estimated.
- **BNM FEATERS alignment:** System design follows BNM's Discussion Paper on AI in the Malaysian Financial Sector (August 2025) — Fairness, Ethics, Accountability, Transparency, Explainability, Reliability, Security.

---

# 14. Expected Outcomes

1. A functional prototype of an agentic AI system that processes Malaysian SME loan application documents end-to-end
2. A validated document extraction pipeline supporting 4 Malaysian SME document types
3. A LangGraph-based ReAct agent capable of multi-step cross-document financial reasoning
4. An explainability framework producing BNM FEATERS-aligned risk summaries
5. A loan officer dashboard enabling efficient human review of AI-generated findings
6. An evaluation report measuring system accuracy, reliability, and usability

---

# 15. References

- Bank Negara Malaysia. (2025). *Discussion Paper on Artificial Intelligence in the Malaysian Financial Sector*. BNM/RH/DP 032-2.
- Bank Negara Malaysia. (2024). *Risk Management in Technology (RMiT) Exposure Draft*.
- SME Finance Forum. (2024). *MSME Finance Gap*. IFC/World Bank Group.
- Mohd Yusoff, A. et al. (2024). *AI-BAAM: AI-Driven Bank Statement Analytics for Malaysian MSME Credit Scoring*. arXiv:2510.16066.
- Ariza-Garzon, M.J. et al. (2024). *Interpretable Large Language Models for Credit Risk Assessment: A Systematic Review*. arXiv:2506.04290.
- Huang, Y. et al. (2025). *Generative AI Augmenting SME Financial Management*. Technovation, ScienceDirect.
- United Nations. (2015). *Transforming our world: the 2030 Agenda for Sustainable Development*. UN DESA.
- Napier AI. (2025). *AI in Malaysia's financial sector: BNM's proposed reforms*.

---

*Prepared by Tran Quang Dat — APU FinTech FYP Proposal, May 2026*
