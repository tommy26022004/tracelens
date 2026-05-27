"""Tool implementations exposed to the ReAct agent.

Per proposal §8:
- extract_financials(document_id, fields)
- cross_validate(field, doc_a, doc_b)
- calculate_ratio(ratio_type, values)
- flag_inconsistency(description, severity)
- retrieve_context(query)
- generate_summary(findings)
"""
