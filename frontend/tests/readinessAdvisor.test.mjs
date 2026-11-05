import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import ts from 'typescript';

const source = readFileSync(new URL('../src/lib/readinessAdvisor.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
const exports = {};
new Function('exports', compiled)(exports);
const { buildReadinessActions } = exports;

function result(overrides = {}) {
    return {
        package_inventory: {
            documents: [{ document_id: 'bank', kind: 'bank_statement' }],
            missing_core_kinds: [], missing_bank_months: [], failed_documents: 0,
            duplicate_document_ids: [], ...overrides
        },
        ratios: { financial_ratios: [{ dsr: { value: null } }] }
    };
}

test('links observed inventory gaps to review actions without a credit score', () => {
    const actions = buildReadinessActions(result({
        missing_core_kinds: ['ssm_registration'],
        missing_bank_months: ['2025-02', '2025-03'],
        failed_documents: 1,
        duplicate_document_ids: ['duplicate.pdf']
    }));
    assert.deepEqual(actions.map(({ id }) => id), [
        'missing-ssm_registration', 'bank-coverage', 'failed-documents', 'duplicates', 'repayment-schedule'
    ]);
    assert.deepEqual(actions[1].dimensions, ['Character', 'Capacity']);
    assert.match(actions[1].detail, /2025-02, 2025-03/);
});

test('a gap-free inventory does not imply credit approval', () => {
    const actions = buildReadinessActions({
        ...result(), ratios: { financial_ratios: [{ dsr: { value: '1.2' } }] }
    });
    assert.deepEqual(actions, []);
});
