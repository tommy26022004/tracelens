"""Credit-assessment LangGraph.

Linear topology (Phase 3a):
    START -> parse -> extract -> END

Subsequent phases add: validate -> ratios -> assess_5c -> summarise.

The graph is built once at import time. Callers either:
- `compile_graph()` for an in-memory checkpointer (tests, dev),
- `compile_graph_with_postgres(conn_string)` for production-grade
  persistence (FEATERS audit trail).
"""

from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.agent.nodes import extract_node, parse_node
from app.agent.state import AgentState


def _build_graph() -> StateGraph:
    graph: StateGraph = StateGraph(AgentState)
    graph.add_node("parse", parse_node)
    graph.add_node("extract", extract_node)

    graph.add_edge(START, "parse")
    graph.add_edge("parse", "extract")
    graph.add_edge("extract", END)
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
