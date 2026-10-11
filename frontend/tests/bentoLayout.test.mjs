import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const page = readFileSync(new URL('../src/routes/+page.svelte', import.meta.url), 'utf8');

test('variable-height assessment cards use content-driven bento columns', () => {
    assert.match(page, /bento-flow bento-flow-two/);
    assert.match(page, /bento-flow bento-flow-three/);
    assert.match(page, /\.bento-item\s*{[^}]*break-inside:\s*avoid/s);
    assert.match(page, /\.bento-flow-three\s*{\s*columns:\s*3/s);
    assert.doesNotMatch(page, /mt-6 grid items-start gap-5 md:grid-cols-2 xl:grid-cols-3/);
});
