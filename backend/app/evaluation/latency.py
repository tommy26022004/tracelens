"""Latency benchmark for the agent graph.

We extract per-node and end-to-end times from the trace that
`ReasoningStep` already records — no instrumentation required.

The proposal target is <3 minutes end-to-end. We report:
- total wall-clock
- per-node breakdown so the dashboard can show the slowest step
- p50 / p95 over N runs when run via the harness
"""

from __future__ import annotations

import statistics
from typing import Any

from pydantic import BaseModel, Field

from app.agent.state import ReasoningStep


class LatencyReport(BaseModel):
    run_count: int
    total_ms_p50: float
    total_ms_p95: float
    total_ms_runs: list[float] = Field(default_factory=list)
    per_node_ms_p50: dict[str, float] = Field(default_factory=dict)


def _trace_total_ms(trace: list[ReasoningStep]) -> float:
    return sum(
        (step.finished_at - step.started_at).total_seconds() * 1000 for step in trace
    )


def _trace_per_node(trace: list[ReasoningStep]) -> dict[str, float]:
    return {
        step.node: (step.finished_at - step.started_at).total_seconds() * 1000
        for step in trace
    }


def time_graph_run(
    graph: Any,
    pdf_paths: list[str],
    *,
    runs: int = 3,
    thread_id_prefix: str = "latency",
) -> LatencyReport:
    """Run `graph.invoke` N times against the same input and report stats."""
    if runs < 1:
        raise ValueError("runs must be >= 1")

    totals: list[float] = []
    per_node_samples: dict[str, list[float]] = {}
    for i in range(runs):
        state = graph.invoke(
            {
                "application_id": f"eval-{i}",
                "pdf_paths": pdf_paths,
                "trace": [],
                "errors": [],
            },
            config={"configurable": {"thread_id": f"{thread_id_prefix}-{i}"}},
        )
        trace = state.get("trace", [])
        totals.append(_trace_total_ms(trace))
        for node, ms in _trace_per_node(trace).items():
            per_node_samples.setdefault(node, []).append(ms)

    p50 = statistics.median(totals)
    p95 = (
        statistics.quantiles(totals, n=20)[18] if len(totals) >= 2 else totals[0]
    )
    per_node_p50 = {
        node: statistics.median(samples) for node, samples in per_node_samples.items()
    }
    return LatencyReport(
        run_count=runs,
        total_ms_p50=p50,
        total_ms_p95=p95,
        total_ms_runs=totals,
        per_node_ms_p50=per_node_p50,
    )
