import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/lib/http.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } });
const { requestJson } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);

test('parses successful responses', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => Response.json({ briefing: null }));
  assert.deepEqual(await requestJson('https://example.invalid'), { briefing: null });
});

test('does not expose server secrets or proxy pages', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => new Response('secret-token', { status: 500 }));
  await assert.rejects(requestJson('https://example.invalid'), (error) => {
    assert.match(error.message, /temporarily unavailable/);
    assert.doesNotMatch(error.message, /secret-token/);
    return true;
  });
});

test('aborts stalled requests with a retryable message', async (t) => {
  t.mock.method(globalThis, 'fetch', async (_url, { signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
  }));
  await assert.rejects(requestJson('https://example.invalid', {}, 5), /timed out/);
});

test('exposes HTTP status for missing-profile handling without server detail', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => Response.json({ detail: 'private data' }, { status: 404 }));
  await assert.rejects(requestJson('https://example.invalid'), (error) => {
    assert.equal(error.status, 404);
    assert.doesNotMatch(error.message, /private data/);
    return true;
  });
});

for (const [code, status, expected] of [
  ['generation_cooldown', 409, /previous generation failed/],
  ['generation_in_progress', 409, /being prepared/],
  ['no_recent_news', 409, /No fresh stories/],
  ['generation_limit_reached', 429, /latest ready audio/],
  ['generation_disabled', 503, /disabled on this staging backend/],
]) {
  test(`classifies ${code} without automatic retry or raw error disclosure`, async (t) => {
    let calls = 0;
    t.mock.method(globalThis, 'fetch', async () => {
      calls++;
      return Response.json({ detail: { code, retry_after_seconds: 45, message: 'secret-provider-detail' } }, { status });
    });
    await assert.rejects(requestJson('https://example.invalid'), error => {
      assert.match(error.message, expected);
      assert.doesNotMatch(error.message, /secret-provider-detail/);
      assert.equal(error.code, code);
      assert.equal(error.retryAfterSeconds, 45);
      return true;
    });
    assert.equal(calls, 1);
  });
}
