import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import ts from 'typescript';

const source = readFileSync(new URL('../src/lib/citations.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 }
}).outputText;
const { segmentise, citationLabel, citationTitle, groupCitations } = await import(
    'data:text/javascript;base64,' + Buffer.from(compiled).toString('base64')
);

test('groups adjacent citations without combining different claims', () => {
    assert.deepEqual(groupCitations('A [one:page:1] [two:page:2]. B [one:page:1]'), [
        { kind: 'text', value: 'A ' },
        { kind: 'sources', chunkIds: ['one:page:1', 'two:page:2'] },
        { kind: 'text', value: '. B ' },
        { kind: 'sources', chunkIds: ['one:page:1'] }
    ]);
});

test('preserves normal brackets, trailing whitespace and prose in grouped citations', () => {
    assert.deepEqual(groupCitations('[estimated] [one:period:0]  '), [
        { kind: 'text', value: '[estimated] ' },
        { kind: 'sources', chunkIds: ['one:period:0'] },
        { kind: 'text', value: '  ' }
    ]);
});

test('deduplicates adjacent full IDs while retaining distinct documents and later claims', () => {
    const segments = segmentise('A [one:summary:0, one:summary:0][two:summary:0] [one:summary:0]. B [one:summary:0]');
    assert.deepEqual(
        segments.filter(segment => segment.kind === 'citation').map(segment => segment.chunkId),
        ['one:summary:0', 'two:summary:0', 'one:summary:0']
    );
});

test('recognises supporting page references and preserves ordinary brackets', () => {
    const segments = segmentise('Evidence [package/facility:page:4] [estimated]');
    assert.equal(segments[1].chunkId, 'package/facility:page:4');
    assert.equal(segments[2].value, ' [estimated]');
});

test('numbers sources consistently and displays verified page metadata', () => {
    const references = {
        'one:summary:0': { filename: 'Bank July.pdf', pages: [1, 4] },
        'two:summary:0': { filename: 'Bank August.pdf', pages: [2] }
    };
    assert.equal(citationLabel('one:summary:0', references), '[1]');
    assert.equal(citationLabel('two:summary:0', references), '[2]');
    assert.equal(citationTitle('one:summary:0', references), 'Bank July.pdf · pp. 1, 4');
    assert.equal(citationTitle('two:summary:0', references), 'Bank August.pdf · p. 2');
});
