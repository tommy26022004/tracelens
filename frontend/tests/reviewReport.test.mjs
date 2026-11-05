import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import ts from 'typescript';

function load(path) {
    const source = readFileSync(new URL(path, import.meta.url), 'utf8');
    const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
    const exports = {};
    new Function('exports', 'require', compiled)(exports, (name) => name === './readinessAdvisor' ? advisor : {});
    return exports;
}

const advisor = load('../src/lib/readinessAdvisor.ts');
const { buildReviewReport } = load('../src/lib/reviewReport.ts');

test('review report escapes source text and keeps decision-support warning', () => {
    const html = buildReviewReport({
        application_id: 'test-1', document_ids: [], package_inventory: {
            documents: [], total_documents: 0, extracted_documents: 0, failed_documents: 0,
            missing_core_kinds: [], missing_bank_months: [], duplicate_document_ids: []
        }, ratios: {}, five_c: {}, inconsistencies: [],
        risk_summary: { headline: '<script>alert(1)</script>', body: 'Review [1]', recommended_human_checks: [] },
        citation_sources: { '[1]': { filename: 'source.pdf', pages: [2] } }
    });
    assert.match(html, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
    assert.doesNotMatch(html, /<script>alert/);
    assert.match(html, /Decision support only/);
    assert.match(html, /source.pdf — page 2/);
});
