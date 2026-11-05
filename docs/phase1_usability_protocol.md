# Phase 1 usability protocol (uncollected)

Recruit at least five consenting participants. Record whether each is a loan officer, finance professional, student, or other; do not conflate convenience-sample results with loan-officer usability. Use synthetic PDFs only. Do not coach participants during tasks.

1. From the landing page, explain what TraceLens does and identify its human-review limitation.
2. Load the supplied synthetic package and start an analysis.
3. Locate a 5C limitation and explain what evidence is missing.
4. Open a citation, identify its PDF filename and supporting page.
5. Locate the bank metrics and one recommended human check.

For each task record completion (yes/no), elapsed seconds, wrong turns, and any error message. After all tasks, administer the ten standard SUS questions from `backend/app/evaluation/sus.py` using the 1–5 scale (strongly disagree to strongly agree). Record responses anonymously as P01–P05 or later. Score with `score_sus_responses`; report individual scores, mean, participant roles, task completion rates, and qualitative issues. Do not fill missing responses or fabricate participants. Obtain consent and avoid collecting real customer financial data.

Phase 1 remains open until participant data has been collected and scored.
