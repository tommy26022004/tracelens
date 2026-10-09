# Realistic SME Loan Package Specification

The realistic benchmark complements, rather than replaces, the ten controlled
four-document scenarios. Controlled scenarios measure correctness; realistic
packages measure workload handling, grouping, failure isolation and scalability.

## Baseline workload

| Category | Files | Pages per file | Expected pages |
|---|---:|---:|---:|
| Bank statements | 18 | 4 | 72 |
| Audited financial statements | 3 | 40 | 120 |
| SSM registration package | 1 | 25 | 25 |
| Corporate tax returns | 3 | 20 | 60 |
| Quarterly management accounts | 4 | 8 | 32 |
| Cash-flow forecast | 1 | 12 | 12 |
| Existing facility statements | 2 | 8 | 16 |
| **Total** | **32** |  | **337** |

The package covers two bank accounts, twelve calendar months and three financial
years. The secondary collection account contains six monthly statements.

## Acceptance criteria

- 30–45 PDF files and 250–500 pages per application.
- Twelve months of bank coverage and three financial years.
- Documents grouped by company, account, period and document category.
- Duplicate files and missing bank months detected before risk assessment.
- Multi-account cash flows aggregated without double-counting overlapping periods.
- Every surfaced finding has a resolvable document and page citation.
- A failed document is reported independently and does not abort the package.

## Generated workload scenarios

Run from the repository root:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\benchmark_realistic_packages.py
```

Outputs are written to `data/realistic_scenarios/`:

- `realistic_01`: healthy and complete package.
- `realistic_02`: January omitted and one July statement uploaded twice; follow
  `UPLOAD_PROTOCOL.json` when selecting files.
- `realistic_03`: tax-declared income intentionally differs from audited revenue.
- `benchmark_results.json`: file/page counts, throughput, extraction success and
  finding precision/recall.

Each scenario contains 32 PDFs and 337 pages. The benchmark processes 1,011 pages
in total without calling Gemini, so deterministic ingestion and validation can be
measured repeatedly without API cost.
