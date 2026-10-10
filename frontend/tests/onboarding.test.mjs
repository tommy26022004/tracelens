import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const page = readFileSync(new URL('../src/routes/+page.svelte', import.meta.url), 'utf8');
const demo = readFileSync(new URL('../src/lib/demoPackage.ts', import.meta.url), 'utf8');

test('first-time visitors receive a repeatable guided tour', () => {
    assert.match(page, /60-second product tour/);
    assert.match(page, /tracelens-tour-seen-v1/);
    assert.match(page, /Take the 60-second tour/);
});

test('the sample package contains four clearly synthetic PDF types', () => {
    assert.match(page, /Try sample package/);
    assert.match(page, /createDemoPackage\(\)/);
    assert.deepEqual(
        [...demo.matchAll(/name: '([^']+\.pdf)'/g)].map((match) => match[1]),
        [
            'demo_bank_statement.pdf',
            'demo_ssm_registration.pdf',
            'demo_audited_financials.pdf',
            'demo_tax_return.pdf'
        ]
    );
    assert.match(demo, /SYNTHETIC TEST DATA - NOT AN OFFICIAL FINANCIAL DOCUMENT/);
    assert.match(demo, /Statement of Account/);
    assert.match(demo, /Company Registration Profile/);
    assert.match(demo, /Financial Statements/);
    assert.match(demo, /Company Tax Return/);
    assert.match(demo, /Income computation summary/);
    assert.match(demo, /Statement reconciliation/);
});
