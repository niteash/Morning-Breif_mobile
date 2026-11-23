import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/lib/authenticatedRequest.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } });
const { authenticatedRequest, SessionRequiredError, SessionRefreshUnavailableError } = await import(
  `data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`
);

const user = { id: 'account-a', is_anonymous: false };
const oldSession = { access_token: 'old-access-token', expires_at: 8_000, user };
const newSession = { access_token: 'new-access-token', expires_at: 9_999, user };
const ok = { status: 200, value: { ok: true } };
const unauthorized = { status: 401, error: new Error('unauthorized') };
const unavailable = { status: 503, error: new Error('unavailable') };
const now = () => 4_000_000;

test('expired and near-expiry sessions refresh before a request is sent', async () => {
  let refreshes = 0;
  const sent = [];
  const result = await authenticatedRequest({
    path: '/api/v1/news?limit=3', method: 'GET', now,
    getSession: async () => ({ session: { ...oldSession, expires_at: 4_030 } }),
    refreshSession: async () => { refreshes++; return { session: newSession }; },
    send: async (session) => { sent.push(session.access_token); return ok; },
  });
  assert.equal(result, ok);
  assert.equal(refreshes, 1);
  assert.deepEqual(sent, ['new-access-token']);
});

test('an expired access token is never sent if refresh succeeds', async () => {
  const sent = [];
  const result = await authenticatedRequest({
    path: '/api/v1/news', method: 'GET', now,
    getSession: async () => ({ session: { ...oldSession, expires_at: 3_999 } }),
    refreshSession: async () => ({ session: newSession }),
    send: async (session) => { sent.push(session.access_token); return ok; },
  });
  assert.equal(result.status, 200);
  assert.deepEqual(sent, ['new-access-token']);
});

test('a 401 retries once with a refreshed token and keeps the request id', async () => {
  const sent = [];
  const diagnostics = [];
  let refreshes = 0;
  const result = await authenticatedRequest({
    path: '/api/v1/users/me/preferences', method: 'GET', now, requestId: () => 'request-test-1',
    getSession: async () => ({ session: oldSession }),
    refreshSession: async () => { refreshes++; return { session: newSession }; },
    send: async (session, requestId) => {
      sent.push([session.access_token, requestId]);
      return session.access_token === 'old-access-token' ? unauthorized : ok;
    },
    onDiagnostic: (event) => diagnostics.push(event),
  });
  assert.equal(result, ok);
  assert.equal(refreshes, 1);
  assert.deepEqual(sent, [['old-access-token', 'request-test-1'], ['new-access-token', 'request-test-1']]);
  assert.deepEqual(diagnostics.map((event) => event.category), ['api_unauthorized', 'retry_recovered']);
  assert.equal(diagnostics[0].tokenExpiry, 'valid');
});

test('concurrent 401 responses share one refresh and retry independently', async () => {
  let refreshes = 0;
  const sent = [];
  const run = (id) => authenticatedRequest({
    path: '/api/v1/users/me/categories', method: 'GET', now, requestId: () => id,
    getSession: async () => ({ session: oldSession }),
    refreshSession: async () => {
      refreshes++;
      await new Promise((resolve) => setTimeout(resolve, 10));
      return { session: newSession };
    },
    send: async (session, requestId) => {
      sent.push([session.access_token, requestId]);
      return session.access_token === 'old-access-token' ? unauthorized : ok;
    },
  });
  const [first, second] = await Promise.all([run('parallel-1'), run('parallel-2')]);
  assert.equal(first.status, 200);
  assert.equal(second.status, 200);
  assert.equal(refreshes, 1);
  assert.equal(sent.filter(([token]) => token === 'new-access-token').length, 2);
});

test('a read-only 503 retries once with the same session and request id', async () => {
  const sent = [], diagnostics = [];
  const result = await authenticatedRequest({
    path: '/api/v1/news?limit=3', method: 'GET', now, requestId: () => 'read-retry-1',
    getSession: async () => ({ session: oldSession }),
    refreshSession: async () => { throw new Error('must not refresh for a 503'); },
    waitBeforeReadRetry: async () => {},
    send: async (session, requestId) => {
      sent.push([session.access_token, requestId]);
      return sent.length === 1 ? unavailable : ok;
    },
    onDiagnostic: event => diagnostics.push(event),
  });
  assert.equal(result, ok);
  assert.deepEqual(sent, [['old-access-token', 'read-retry-1'], ['old-access-token', 'read-retry-1']]);
  assert.equal(diagnostics[0].category, 'read_retry_recovered');
});

test('mutating requests never retry a 503 automatically', async () => {
  let sends = 0;
  const result = await authenticatedRequest({
    path: '/api/v1/users/me/preferences', method: 'PUT', now,
    getSession: async () => ({ session: oldSession }),
    refreshSession: async () => ({ session: newSession }),
    send: async () => { sends++; return unavailable; },
    waitBeforeReadRetry: async () => { throw new Error('must not wait'); },
  });
  assert.equal(result.status, 503);
  assert.equal(sends, 1);
});

test('missing sessions and account changes never send a request with another account token', async () => {
  let sends = 0;
  await assert.rejects(authenticatedRequest({
    path: '/api/v1/news', method: 'GET', getSession: async () => ({ session: null }),
    refreshSession: async () => ({ session: null }), send: async () => { sends++; return ok; },
  }), SessionRequiredError);

  let reads = 0;
  const response = await authenticatedRequest({
    path: '/api/v1/news', method: 'GET', now,
    getSession: async () => ({ session: reads++ === 0 ? oldSession : { ...newSession, user: { id: 'account-b' } } }),
    refreshSession: async () => { throw new Error('must not refresh another account'); },
    send: async () => { sends++; return unauthorized; },
  });
  assert.equal(response.status, 401);
  assert.equal(sends, 1);
});

test('logout during a request never restores a session or replays with the old token', async () => {
  let reads = 0;
  let refreshes = 0;
  let sends = 0;
  const response = await authenticatedRequest({
    path: '/api/v1/users/me/preferences', method: 'GET', now,
    getSession: async () => ({ session: reads++ === 0 ? oldSession : null }),
    refreshSession: async () => { refreshes++; return { session: newSession }; },
    send: async () => { sends++; return unauthorized; },
  });
  assert.equal(response.status, 401);
  assert.equal(sends, 1);
  assert.equal(refreshes, 0);
});

test('refresh infrastructure failures do not become authenticated requests', async () => {
  await assert.rejects(authenticatedRequest({
    path: '/api/v1/news', method: 'GET', now,
    getSession: async () => ({ session: { ...oldSession, expires_at: 4_030 } }),
    refreshSession: async () => { throw new Error('private refresh failure'); },
    send: async () => { throw new Error('must not send stale token'); },
  }), SessionRefreshUnavailableError);
});
