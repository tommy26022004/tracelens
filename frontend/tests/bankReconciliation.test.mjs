import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import ts from 'typescript';

const source = readFileSync(new URL('../src/lib/bankReconciliation.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { bankReconciliation } = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));

test('case 07 shows both movements and the 900 difference', () => {
    assert.deepEqual(bankReconciliation({total_credits: '10000', total_debits: '6000', net_change: '4900'}), {movement: '4000.00', difference: '900.00', mismatch: true});
});
test('matching cents do not create a rounding discrepancy', () => {
    assert.equal(bankReconciliation({total_credits: '0.30', total_debits: '0.20', net_change: '0.10'}).mismatch, false);
});
test('invalid numbers are not presented as reconciled', () => {
    assert.equal(bankReconciliation({total_credits: 'invalid', total_debits: '0', net_change: '0'}).mismatch, true);
});
