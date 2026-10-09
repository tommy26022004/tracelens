import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import ts from 'typescript';

const source = readFileSync(new URL('../src/lib/assessmentText.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { assessmentParagraphs, assessmentHeading, assessmentGroupHeading, humanChecksForDisplay, retrievalLabel } = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));

test('recognises standalone 5C group headings without treating claims as headings', () => {
    for (const heading of ['**Provisional 5C Assessment:**', '**Provisional 5C Assessment**:', '### Provisional 5C Assessment', '5C assessment']) {
        assert.ok(assessmentGroupHeading(heading));
    }
    assert.equal(assessmentGroupHeading('Provisional 5C Assessment: Review RM900 [bank:summary:0].'), null);
    assert.equal(assessmentGroupHeading('Character: insufficient data.'), null);
    const paragraphs = assessmentParagraphs('**Provisional 5C Assessment:**\n\nCharacter: Review RM900 [bank:summary:0].');
    assert.equal(paragraphs.length, 2);
    assert.equal(paragraphs[1], 'Character: Review RM900 [bank:summary:0].');
});

test('renders bold and colon 5C labels without losing evidence', () => {
    for (const name of ['Character', 'Capacity', 'Capital', 'Collateral', 'Conditions']) {
        const [paragraph] = assessmentParagraphs(`**${name}**: Review RM120.00 [tax:summary:0].`);
        assert.equal(paragraph, `${name}: Review RM120.00 [tax:summary:0].`);
        assert.equal(assessmentHeading(paragraph), name);
    }
});

test('paragraph layout preserves amounts and citations without rewriting claims', () => {
    const text = 'Cash RM333.33 [bank:summary:0]. This is provisional. Review the source [bank:transaction:2].';
    const result = assessmentParagraphs(text);
    assert.equal(result.length, 1);
    assert.equal(result.join(' '), text);
});

test('keeps a concluding sentence with its original paragraph', () => {
    const paragraph = 'Capital needs audited financials. Paid-up capital alone is insufficient. Therefore, the data is insufficient.';
    assert.deepEqual(assessmentParagraphs(paragraph), [paragraph]);
});

test('complete retrieval is labelled as a search status, not full evidence', () => {
    assert.equal(retrievalLabel('complete'), 'Available-source search finished');
    assert.equal(retrievalLabel(), 'Not available');
});

test('preserves validation lines and paragraph boundaries', () => {
    assert.deepEqual(assessmentParagraphs('Scope.\n\nSystem validation checks:\nMISSING: example'), ['Scope.', 'System validation checks:\nMISSING: example']);
});

test('separates combined 5C assessments without changing claims or citations', () => {
    const text = 'Character is rated insufficient_data. No statements were provided. Capacity is also rated insufficient_data. Capital is rated insufficient_data; paid-up capital is RM 50,000.00 [ssm:summary:0]. Therefore, the data is insufficient. Collateral is rated insufficient_data. Conditions are rated insufficient_data.';
    const sections = assessmentParagraphs(text);
    assert.equal(sections.length, 5);
    assert.equal(sections.join(' '), text);
    assert.deepEqual(sections.map(assessmentHeading), ['Character', 'Capacity', 'Capital', 'Collateral', 'Conditions']);
    assert.ok(sections[2].endsWith('Therefore, the data is insufficient.'));
});

test('filters machine-coded and category-duplicate human checks', () => {
    const checks = humanChecksForDisplay([
        'DOCUMENT_EXTRACTION_FAILURES: 1 document failed.',
        'Missing bank statements for transactional behaviour analysis',
        'Review the missing banking history.',
        'Missing audited financials to assess cash flow',
        'Missing audited financials to evaluate capital',
        'Obtain a verified annual repayment schedule.'
    ], ['DOCUMENT_EXTRACTION_FAILURES']);
    assert.deepEqual(checks, [
        'Missing bank statements for transactional behaviour analysis',
        'Missing audited financials to assess cash flow',
        'Obtain a verified annual repayment schedule.'
    ]);
});

test('supports quoted criteria but does not split a mid-sentence mention', () => {
    const text = "The 'Character' assessment is limited. Finally, 'Conditions' is marked insufficient_data.";
    assert.deepEqual(assessmentParagraphs(text).map(assessmentHeading), ['Character', 'Conditions']);
    assert.deepEqual(assessmentParagraphs('The report states Capital is limited [ssm:summary:0].'), ['The report states Capital is limited [ssm:summary:0].']);
});

test('separates financial scope, facts and ratios without altering amounts', () => {
    const text = 'One financial report was supplied. For the financial year 2025, revenue was RM 120,000.00 [fin:period:0]. Key financial ratios include a margin of 18%. Total equity for the period was RM 100,000.00 [fin:period:0].';
    const sections = assessmentParagraphs(text);
    assert.equal(sections.length, 4);
    assert.equal(sections.join(' '), text);
});
