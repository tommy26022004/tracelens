import type { AnalysisResponse } from './types';
import { buildReadinessActions } from './readinessAdvisor';

function escapeHtml(value: unknown): string {
    return String(value ?? '').replace(/[&<>"']/g, (character) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[character] ?? character);
}

export function buildReviewReport(result: AnalysisResponse): string {
    const actions = buildReadinessActions(result);
    const dimensions = ['character', 'capacity', 'capital', 'collateral', 'conditions'] as const;
    const fiveC = result.five_c as Partial<Record<(typeof dimensions)[number], { rating: string; reasoning: string }>>;
    const sources = Object.entries(result.citation_sources ?? {});
    const list = (items: string[]) => items.length
        ? `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`
        : '<p>None recorded.</p>';

    return `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>TraceLens review report — ${escapeHtml(result.application_id)}</title>
<style>body{font:14px/1.5 Arial,sans-serif;color:#17243a;max-width:820px;margin:32px auto;padding:0 24px}h1,h2{color:#263b2d}h1{margin-bottom:4px}h2{border-bottom:1px solid #cbd5d1;padding-bottom:5px;margin-top:28px}.notice{border:1px solid #bc8f43;background:#fff8e8;padding:12px}.meta{color:#506070}.card{border:1px solid #d5dfd5;border-radius:8px;padding:10px 14px;margin:10px 0}li{margin:5px 0}.toolbar{margin-bottom:24px}button{padding:9px 16px;background:#536a41;color:#fff;border:0;border-radius:5px;cursor:pointer}@media print{.toolbar{display:none}body{margin:0;max-width:none}.card{break-inside:avoid}}</style></head><body>
<div class="toolbar"><button onclick="window.print()">Print / save as PDF</button></div>
<h1>TraceLens — Human review report</h1><p class="meta">Application ID: ${escapeHtml(result.application_id)} · Generated: ${escapeHtml(new Date().toISOString())}</p>
<p class="notice"><strong>Decision support only.</strong> This report records document-reported data and provisional AI-assisted findings. It does not verify source authenticity or approve a loan. An authorised reviewer must inspect the original PDFs and resolve limitations.</p>
<h2>Package processing</h2><p>${escapeHtml(result.package_inventory?.extracted_documents ?? 0)} of ${escapeHtml(result.package_inventory?.total_documents ?? result.document_ids.length)} documents processed; ${escapeHtml(result.package_inventory?.failed_documents ?? 0)} failed.</p>
<h2>Assessment overview</h2><p><strong>${escapeHtml(result.risk_summary?.headline ?? 'No summary available')}</strong></p><p style="white-space:pre-wrap">${escapeHtml(result.risk_summary?.body ?? 'No assessment narrative available.')}</p>
<h2>Reported financial metrics</h2>${(result.ratios?.financial_ratios ?? []).length ? result.ratios.financial_ratios!.map((period) => `<div class="card"><strong>Period ending ${escapeHtml(period.period_end)}</strong>${[period.current_ratio, period.debt_to_equity, period.net_profit_margin, period.interest_coverage, period.dsr].map((ratio) => `<p>${escapeHtml(ratio.name)}: ${escapeHtml(ratio.value ?? 'Unavailable')} · ${escapeHtml(ratio.formula)}</p>`).join('')}</div>`).join('') : '<p>No financial-ratio record available.</p>'}
<h2>Document readiness actions</h2>${actions.length ? actions.map((action) => `<div class="card"><strong>${escapeHtml(action.title)}</strong><p>${escapeHtml(action.detail)}</p><small>Relevant 5Cs: ${escapeHtml(action.dimensions.join(', ') || 'General document review')}</small></div>`).join('') : '<p>No inventory gaps detected. Evidence sufficiency and authenticity still require human verification.</p>'}
<h2>Provisional 5C assessment</h2>${dimensions.map((name) => { const item = fiveC[name]; return `<div class="card"><strong>${escapeHtml(name.toUpperCase())}: ${escapeHtml(item?.rating ?? 'Unavailable')}</strong><p>${escapeHtml(item?.reasoning ?? 'No assessment available.')}</p></div>`; }).join('')}
<h2>Validation findings</h2>${list((result.inconsistencies ?? []).map((finding) => `${finding.severity.toUpperCase()} ${finding.code}: ${finding.message}`))}
<h2>Recommended human checks</h2>${list(result.risk_summary?.recommended_human_checks ?? [])}
<h2>Source index</h2>${sources.length ? list(sources.map(([chunkId, source]) => `${chunkId}: ${source.filename} — ${source.pages.length ? `page ${source.pages.join(', ')}` : 'page unverified'}`)) : '<p>No source index available. Review the original documents in TraceLens.</p>'}
<p class="meta">Generated from the saved analysis state. Re-running the package may produce different results. This printout is not a signed credit decision.</p></body></html>`;
}
