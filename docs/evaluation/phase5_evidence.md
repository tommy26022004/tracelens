# TraceLens evaluation evidence (local, 2026-11-05)

## Reproducible technical results

| Measure | Observed result | Scope and limitation |
| --- | --- | --- |
| Field extraction | Bank 429/429, SSM 13/13, audited financials 32/32, tax 6/6 | Four generated PDFs; not a real-world accuracy estimate. See `backend/scripts/evaluate.py`. |
| Bank layout robustness | Previous 2/5 scenarios extracted; current 5/5, with 79/79 matched fields on each successful scenario | One synthetic bank PDF, geometry altered after PDF parsing. See `robustness_baseline.json`. Failed extraction is scored zero, not 0/79 matched fields. |
| Image-only scan | OCR need flagged; structured extraction rejected | No automatic OCR accuracy claim. |
| Validation findings | 100% precision and recall in three generated 32-file workloads | Ground truth contains selected finding codes; not exhaustive real-bank validation. |
| Retrieval relevance | Recall@3 1.0, Precision@3 0.333, MRR 1.0 on four curated queries | Tiny lexical test against real isolated Qdrant. Not representative of arbitrary user questions. |
| Citation IDs | 3/3 valid; 20% sentence citation coverage | Identifier validity is not factual correctness. |
| Browser E2E | 3/3 Chrome runs passed (82.01s, 85.03s, 88.23s) | Synthetic demo through local UI, backend, job processing, and source viewer; test records remain in local history. |
| Backend suite | 143 passed, 3 skipped | Optional integrations require explicit services. |

The earlier latency sample reported p50 39.40s and p95 39.52s over three isolated evaluation runs. The Chrome runs above have longer end-user durations and are not directly comparable. No measured improvement in broad extraction accuracy can be claimed from synthetic fixtures already at 100%.

## Human usability evaluation

No SUS participants have been recorded. The template `sus_responses_template.csv` intentionally has only headers. Follow `docs/phase1_usability_protocol.md`, collect consented responses from at least five actual participants, and record their roles. Score only completed data using:

`cd backend; .\.venv\Scripts\python.exe -m scripts.score_usability ..\docs\evaluation\sus_responses.csv --json ..\docs\evaluation\sus_results.json`

Do not commit identifiable participant data or real customer financial records. Until responses are supplied, mean SUS, task completion, and qualitative findings remain **not measured**.
