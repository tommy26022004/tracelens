"""LangGraph state graph for the credit-assessment agent.

Node sketch:
    parse → extract → validate → ratios → assess_5c → summarise

Each node is implemented in its own domain package; this module wires them
together and exposes a single compiled graph.
"""

# TODO: implement once domain modules expose their callable nodes.
