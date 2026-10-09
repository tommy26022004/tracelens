# Development History

Open **Development History** in the global navigation, or `/history`.

The workspace starts empty. Existing project progress notes, tests and analysis results are not imported or erased.

## Recording future work

- Analysis: each new execution records a terminal completed/failed event, run ID, times, document count, app version, selected non-secret configuration and the returned result snapshot. Completed means execution finished, not that the assessment is correct. Recoverable errors remain in the snapshot.
- Tests: use Add entry, select Test result, record the dataset, command, expected/actual results and report reference. Default is `not_run`. Passed/failed are manual claims; test commands are not executed by this page.
- Bugs: record the reproduction steps and related run ID. Add a linked follow-up with the fix and retest evidence rather than changing the original entry.
- Notes: record reasoning, decisions, remaining limitations and AI assistance honestly.
- Export JSON downloads the selected record. Analysis exports include the result snapshot. Evidence reference text does not upload or archive external files.

## Persistence and limits

Records are individual JSON files in `development_history`, beside `source_documents`, under the configured source storage parent. With Docker's default `/app/data` mount, this is the repository's `data/development_history`. Native backend execution defaults to `backend/data/development_history`. Back up this directory separately; do not commit sensitive data.

The UI offers no overwrite/delete action. This does not make the filesystem tamper-proof or prove authorship. Endpoints share the prototype's trusted-local security boundary; do not expose this service publicly or use real confidential documents without appropriate authorisation and access controls.

Queued/in-progress jobs are still in-memory; an abrupt shutdown can prevent a completion record. Analysis history is not a durable task queue. API secrets are not captured in configuration, but returned analysis content can itself contain confidential data. Persisting history failures does not suppress analysis errors; successful analysis responses receive a history warning when persistence fails.

Git revision is not automatically verified. App version is captured; manual entries can reference a commit and report path. Missing metrics are not converted into zero accuracy or passing tests. Automated evaluation ingestion, comparison charts, source-document backup, authentication and tamper-evident storage remain future work.
