import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

const source = await readFile(new URL('../src/lib/googleAuthCallback.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } });
const { parseGoogleAuthCallback } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);

test('accepts only the app-owned Google OAuth callback with one code', () => {
  assert.equal(parseGoogleAuthCallback('morningbrief://auth/google?code=verified-code'), 'verified-code');
  for (const value of [
    'https://auth/google?code=stolen',
    'morningbrief://evil/google?code=stolen',
    'morningbrief://auth/google?code=one&code=two',
    'morningbrief://auth/google?error=access_denied',
    'morningbrief://auth/google#code=token',
  ]) assert.throws(() => parseGoogleAuthCallback(value));
});
