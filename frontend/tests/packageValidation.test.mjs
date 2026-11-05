import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import ts from 'typescript';

const source = readFileSync(new URL('../src/lib/packageValidation.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
const exports = {};
new Function('exports', compiled)(exports);
const { validatePackage } = exports;

test('rejects missing, non-PDF, empty and oversized packages before upload', () => {
    assert.match(validatePackage([]), /at least one PDF/);
    assert.match(validatePackage([{ name: 'notes.txt', size: 10 }]), /Only PDF/);
    assert.match(validatePackage([{ name: 'empty.pdf', size: 0 }]), /empty/);
    assert.match(validatePackage(Array.from({ length: 51 }, (_, index) => ({ name: `${index}.pdf`, size: 10 }))), /at most 50/);
    assert.match(validatePackage([{ name: 'large.pdf', size: 100 * 1024 * 1024 + 1 }]), /100 MB/);
    assert.equal(validatePackage([{ name: 'demo.PDF', size: 1024 }]), null);
});
