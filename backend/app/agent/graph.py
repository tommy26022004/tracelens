"""Credit-assessment LangGraph.

Linear topology (Phase 3 complete):
    START -> parse -> extract -> validate -> ratios -> assess_5c
          -> summarise -> END

`parse` + `extract` are deterministic. `validate` + `ratios` are also
deterministic (audit-friendly baselines). `assess_5c` + `summarise`
invoke the LLM with structured outputs and inline citations
respectively, both producing FEATERS-aligned, source-traced artefacts.

The graph is built once at import time. Callers either:
- `compile_graph()` for an in-memory checkpointer (tests, dev),
- `compile_graph_with_postgres(conn_string)` for production-grade
  persistence.
"""

from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.agent.nodes import (
    assess_5c_node,
    extract_node,
    parse_node,
    ratios_node,
    summarise_node,
    validate_node,
)
from app.agent.state import AgentState


def _build_graph() -> StateGraph:
    graph: StateGraph = StateGraph(AgentState)
    graph.add_node("parse", parse_node)
    graph.add_node("extract", extract_node)
    graph.add_node("validate", validate_node)
    graph.add_node("ratios", ratios_node)
    graph.add_node("assess_5c", assess_5c_node)
    graph.add_node("summarise", summarise_node)

    graph.add_edge(START, "parse")
    graph.add_edge("parse", "extract")
    graph.add_edge("extract", "validate")
    graph.add_edge("validate", "ratios")
    graph.add_edge("ratios", "assess_5c")
    graph.add_edge("assess_5c", "summarise")
    graph.add_edge("summarise", END)
    return graph


def compile_graph():
    """Compile with an in-memory checkpointer. Suitable for tests / dev."""
    return _build_graph().compile(checkpointer=InMemorySaver())


def compile_graph_with_postgres(conn_string: str):
    """Compile with a Postgres checkpointer for durable reasoning trails.

    The caller is responsible for `setup()` of the checkpointer the first
    time it is used against a fresh database — see `scripts/init_agent_db.py`.
    """
    from langgraph.checkpoint.postgres import PostgresSaver

    checkpointer = PostgresSaver.from_conn_string(conn_string)
    return _build_graph().compile(checkpointer=checkpointer)
