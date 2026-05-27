"""End-to-end smoke test for the Phase 3a graph (parse + extract nodes).

Generates a synthetic statement, runs it through the compiled graph,
prints the resulting state + trace. Exits non-zero on failure.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from app.agent.graph import compile_graph
from app.ingestion.ssm_synthetic import SSMGeneratorConfig, generate as generate_ssm
from app.ingestion.store import COLLECTION_NAME, VectorStore
from app.ingestion.synthetic import GeneratorConfig, generate


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        bank_pdf, _ = generate(GeneratorConfig(seed=314, n_transactions=12), out)
        ssm_pdf, _ = generate_ssm(SSMGeneratorConfig(seed=314), out)

        store = VectorStore()
        if store._client.collection_exists(COLLECTION_NAME):  # noqa: SLF001
            store._client.delete_collection(COLLECTION_NAME)  # noqa: SLF001

        graph = compile_graph()
        config = {"configurable": {"thread_id": "smoke-agent-1"}}
        result = graph.invoke(
            {
                "application_id": "smoke-app",
                "pdf_paths": [str(bank_pdf), str(ssm_pdf)],
                "trace": [],
                "errors": [],
            },
            config=config,
        )

        print(f"document_ids: {result.get('document_ids')}")
        print(f"statements  : {len(result.get('statements', []))}")
        print(f"errors      : {result.get('errors')}")
        print()
        print("Reasoning trail:")
        for step in result.get("trace", []):
            duration_ms = (step.finished_at - step.started_at).total_seconds() * 1000
            print(f"  [{step.node:8}] {duration_ms:6.1f}ms  {step.summary}")

        if not result.get("statements"):
            print("FAIL: no statements extracted")
            return 1

        # Phase 3b: show downstream-node outputs.
        inconsistencies = result.get("inconsistencies", [])
        print(f"inconsistencies: {len(inconsistencies)}")
        for issue in inconsistencies:
            print(f"  - [{issue['severity']}] {issue['code']}: {issue['message']}")

        ratios = result.get("ratios", {}).get("bank_statement_metrics", [])
        if ratios:
            r = ratios[0]
            print(
                f"metrics[0]: net_change=RM{r['net_change']}, "
                f"avg_inflow=RM{r['avg_daily_inflow']}/day, "
                f"deposits={r['deposit_count']}"
            )

        five_c = result.get("five_c")
        if five_c:
            print("5C assessment:")
            for dim in ("character", "capacity", "capital", "collateral", "conditions"):
                d = five_c[dim]
                print(f"  {dim:11}: {d['rating']:18}  evidence={d['evidence_chunk_ids']}")

        risk_summary = result.get("risk_summary")
        if risk_summary:
            import json as _json

            s = _json.loads(risk_summary)
            print()
            print("Risk summary headline:")
            print(f"  {s['headline']}")
            print(f"cited_chunk_ids: {s['cited_chunk_ids']}")

        if result.get("errors"):
            print(f"errors: {result['errors']}")
            # Citation errors are recoverable — the dashboard surfaces them.
            fatal = [e for e in result["errors"] if not e.recoverable]
            if fatal:
                print(f"FAIL: fatal errors: {fatal}")
                return 1
        print("PASS")
        return 0


if __name__ == "__main__":
    sys.exit(main())
