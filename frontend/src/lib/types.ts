/** Shared types mirroring `app.api.applications.AnalysisResponse`. */

export type Severity = 'info' | 'warning' | 'critical';

export type Rating = 'strong' | 'adequate' | 'weak' | 'insufficient_data';

export interface Inconsistency {
	code: string;
	severity: Severity;
	message: string;
	citations: string[];
}

export interface Dimension {
	name: string;
	rating: Rating;
	reasoning: string;
	evidence_chunk_ids: string[];
	flags_for_human_review: string[];
}

export interface FiveC {
	character: Dimension;
	capacity: Dimension;
	capital: Dimension;
	collateral: Dimension;
	conditions: Dimension;
}

export interface RiskSummary {
	headline: string;
	body: string;
	recommended_human_checks: string[];
	cited_chunk_ids: string[];
}

export interface TraceItem {
	node: string;
	duration_ms: number;
	summary: string;
}

export interface AgentErrorItem {
	node: string;
	message: string;
	recoverable: boolean;
}

export interface BankStatementMetrics {
	document_id: string;
	period_days: number;
	transaction_count: number;
	total_credits: string;
	total_debits: string;
	net_change: string;
	avg_daily_inflow: string;
	avg_daily_outflow: string;
	deposit_count: number;
	withdrawal_count: number;
	largest_credit: string | null;
	largest_debit: string | null;
	end_of_period_balance: string;
	balance_volatility: string;
}

export interface AnalysisResponse {
	application_id: string;
	document_ids: string[];
	document_kinds: Record<string, string>;
	needs_ocr_pages: Record<string, number[]>;
	inconsistencies: Inconsistency[];
	ratios: { bank_statement_metrics?: BankStatementMetrics[] };
	five_c: FiveC | Record<string, never>;
	risk_summary: RiskSummary | null;
	trace: TraceItem[];
	errors: AgentErrorItem[];
}

export interface ChunkDetail {
	chunk_id: string;
	document_id: string;
	kind: string;
	text: string;
	page: number;
	source_metadata: Record<string, unknown>;
}
