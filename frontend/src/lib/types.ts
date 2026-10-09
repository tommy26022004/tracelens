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

export interface InventoryDocument {
	document_id: string;
	kind: string;
	page_count: number;
	extraction_status: string;
	duplicate_of: string | null;
}

export interface PackageInventory {
	documents: InventoryDocument[];
	total_documents: number;
	total_pages: number;
	extracted_documents: number;
	failed_documents: number;
	documents_by_kind: Record<string, number>;
	bank_coverage_by_account: Record<string, string[]>;
	missing_bank_months: string[];
	financial_years: number[];
	missing_core_kinds: string[];
	duplicate_document_ids: string[];
	complete: boolean;
}

export interface AnalysisResponse {
    tax_returns?: { company_name: string; tax_reference_number: string; year_of_assessment: number; gross_business_income: string; chargeable_income: string; tax_payable: string; chunk_id: string }[];
    retrieval?: RetrievalBundle;
    citation_sources?: Record<string, CitationReference>;
	application_id: string;
	document_ids: string[];
	document_kinds: Record<string, string>;
	needs_ocr_pages: Record<string, number[]>;
	inconsistencies: Inconsistency[];
	ratios: {
		financial_ratios?: { document_id: string; period_end: string; source_display_unit?: string; canonical_unit?: string; unit_multiplier?: string; inputs?: Record<string, string>; current_ratio: FinancialRatio; debt_to_equity: FinancialRatio; net_profit_margin: FinancialRatio; interest_coverage: FinancialRatio; dsr: FinancialRatio }[];
		bank_statement_metrics?: BankStatementMetrics[];
		package_cash_flow?: Record<string, unknown>;
		financial_trend?: Record<string, unknown>;
	};
	five_c: FiveC | Record<string, never>;
	risk_summary: RiskSummary | null;
	trace: TraceItem[];
	errors: AgentErrorItem[];
	package_inventory: PackageInventory | Record<string, never>;
}

export interface FinancialRatio {
    name: string;
    value: string | null;
    band: string;
    formula: string;
    explanation: string;
}

export interface AnalysisJobResponse {
	job_id: string;
	status: 'queued' | 'processing' | 'completed' | 'failed';
	progress: number;
	phase: string;
	result: AnalysisResponse | null;
	error: string | null;
}

export interface ChunkDetail {
	chunk_id: string;
	document_id: string;
	kind: string;
	text: string;
    page: number | null;
    source_metadata: Record<string, unknown>;
    filename: string;
    source_pages: number[];
    source_locations: SourceLocation[];
    pdf_url: string | null;
    preview_url: string | null;
}

export interface CitationReference {
    document_id: string;
    filename: string;
    pages: number[];
}

export interface SourceLocation {
    field: string;
    page: number;
    text: string;
    bbox: number[];
}

export interface RetrievedEvidence {
	chunk_id: string;
	document_id: string;
	document_kind: string;
	filename: string;
	pages: number[];
	score: number;
	text: string;
	truncated: boolean;
	evidence_type: string;
}

export interface RetrievalBundle {
	application_id: string;
	embedding_space: string;
	status: string;
	consumed_by: string[];
	warnings: string[];
	evidence: RetrievedEvidence[];
	queries: {
		topic: string;
		query: string;
		document_kinds: string[];
		status: string;
		selected_chunk_ids: string[];
		rejected_hits: number;
	}[];
}
