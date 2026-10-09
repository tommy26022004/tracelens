import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import ts from 'typescript';

const source = readFileSync(new URL('../src/lib/historyLinks.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { linkedFollowUps } = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));

test('missing identifiers never link unrelated history entries', () => {
    assert.deepEqual(linkedFollowUps([{ id: 'run' }, { id: 'note', related_id: '' }], { id: 'bug' }), []);
});

test('only explicit record or application references link, excluding self', () => {
    const records = [{ id: 'bug', related_id: 'run' }, { id: 'test', related_id: 'app' }, { id: 'other', related_id: 'different' }, { id: 'run', related_id: 'run' }];
    assert.deepEqual(linkedFollowUps(records, { id: 'run', application_id: 'app' }).map((entry) => entry.id), ['bug', 'test']);
});
