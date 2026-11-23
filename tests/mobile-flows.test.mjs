import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

async function loadModule(name) {
  const source = await readFile(new URL(`../src/lib/${name}.ts`, import.meta.url), 'utf8');
  const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } });
  return import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
}
const { loadOptionalPreferences, needsOnboarding } = await loadModule('onboarding');
const { createGenerationRequests } = await loadModule('generationRequest');
const { createPushLifecycle } = await loadModule('pushLifecycle');
const profile = { timezone: 'Asia/Yangon', delivery_hour: 7, delivery_minute: 30 };
const categories = [{ category_id: 'tech', categories: { id: 'tech' } }];

function memoryStorage() {
  const values = new Map();
  return {
    values,
    getItem: async (key) => values.get(key) ?? null,
    setItem: async (key, value) => { values.set(key, value); },
    removeItem: async (key) => { values.delete(key); },
  };
}

test('new, interrupted and completed onboarding route consistently', async () => {
  assert.equal(await needsOnboarding(async () => null, async () => { throw Error('should not load'); }), true);
  assert.equal(await needsOnboarding(async () => profile, async () => ({ categories: [] })), true);
  assert.equal(await needsOnboarding(async () => profile, async () => ({ categories: [{ category_id: 'removed', categories: null }] })), true);
  assert.equal(await needsOnboarding(async () => profile, async () => ({ categories })), false);
});

test('only a missing profile uses defaults; connection/auth failures preserve the error', async () => {
  assert.equal(await loadOptionalPreferences(async () => { throw Object.assign(Error('missing'), { status: 404 }); }), null);
  assert.deepEqual(await loadOptionalPreferences(async () => ({ profile })), profile);
  for (const status of [401, 403, 500, undefined]) {
    const failure = Object.assign(Error('unavailable'), { status });
    await assert.rejects(loadOptionalPreferences(async () => { throw failure; }), (error) => error === failure);
  }
  await assert.rejects(needsOnboarding(async () => profile, async () => { throw Error('offline'); }), /offline/);
});

test('a lost generation response reuses its persisted ID after app restart', async () => {
  const storage = memoryStorage();
  const sent = [];
  let nextId = 0;
  const ids = () => `intent-${++nextId}`;
  const first = createGenerationRequests(storage, ids, async (id) => { sent.push(id); throw Error('timeout'); });
  await assert.rejects(first('stage', 'alice'), /timeout/);
  const restarted = createGenerationRequests(storage, ids, async (id) => { sent.push(id); return 'saved'; });
  assert.equal(await restarted('stage', 'alice'), 'saved');
  assert.deepEqual(sent, ['intent-1', 'intent-1']);
  await restarted('stage', 'alice');
  assert.equal(sent.at(-1), 'intent-2');
});

test('double taps share one request and failed intents stay isolated by user/environment', async () => {
  const storage = memoryStorage();
  let nextId = 0;
  const sent = [];
  const request = createGenerationRequests(storage, () => `intent-${++nextId}`, async (id, userId) => {
    sent.push([id, userId]);
    throw Error('timeout');
  });
  const one = request('stage', 'alice');
  const two = request('stage', 'alice');
  assert.equal(one, two);
  await Promise.allSettled([one, two, request('stage', 'bob'), request('production', 'alice')]);
  assert.equal(sent.length, 3);
  assert.equal(new Set(sent.map(([id]) => id)).size, 3);
  await assert.rejects(request('stage', 'alice'));
  assert.equal(sent.at(-1)[0], sent[0][0]);
});

test('generation cannot start without persisting its intent; cleanup failure safely replays', async () => {
  let calls = 0;
  const storage = memoryStorage();
  const broken = createGenerationRequests({ ...storage, setItem: async () => { throw Error('disk full'); } }, () => 'id', async () => { calls++; });
  await assert.rejects(broken('stage', 'alice'), /disk full/);
  assert.equal(calls, 0);
  const sent = [];
  const request = createGenerationRequests({ ...storage, removeItem: async () => { throw Error('disk'); } }, () => 'id', async (id) => { sent.push(id); return 'saved'; });
  assert.equal(await request('stage', 'alice'), 'saved');
  assert.equal(await request('stage', 'alice'), 'saved');
  assert.deepEqual(sent, ['id', 'id']);
});

test('logout waits for pending registration and prevents late registration', async () => {
  const events = [];
  let finish;
  const lifecycle = createPushLifecycle(async () => {
    events.push('register-start');
    await new Promise((resolve) => { finish = resolve; });
    events.push('register-finish');
  }, async () => { events.push('unregister'); }, async () => { events.push('signout'); });
  const registration = lifecycle.register();
  await Promise.resolve();
  const logout = lifecycle.signOut();
  assert.equal(lifecycle.signOut(), logout);
  assert.equal(await lifecycle.register(), null);
  finish();
  await Promise.all([registration, logout]);
  assert.deepEqual(events, ['register-start', 'register-finish', 'unregister', 'signout']);
});

test('failed cleanup preserves auth and can be retried even after failed registration', async () => {
  let failCleanup = true;
  let signedOut = 0;
  const lifecycle = createPushLifecycle(async () => { throw Error('registration timed out'); }, async () => {
    if (failCleanup) throw Error('offline');
  }, async () => { signedOut++; });
  await assert.rejects(lifecycle.register(), /timed out/);
  await assert.rejects(lifecycle.signOut(), /offline/);
  assert.equal(signedOut, 0);
  failCleanup = false;
  await lifecycle.signOut();
  assert.equal(signedOut, 1);
});

const { submitAccountDeletion } = await loadModule('accountDeletion');
test('account deletion requires exact confirmation and binds the request to the displayed account', async () => {
  let calls = 0;
  const request = async (path, options, expectedUserId) => {
    calls++;
    assert.equal(path, '/api/v1/users/me');
    assert.equal(options.method, 'DELETE');
    assert.deepEqual(JSON.parse(options.body), { confirmation: 'DELETE' });
    assert.equal(expectedUserId, 'alice');
    return { status: 'requested' };
  };
  for (const text of ['', 'delete', ' DELETE']) await assert.rejects(submitAccountDeletion(text, 'alice', request));
  await assert.rejects(submitAccountDeletion('DELETE', '', request));
  assert.equal(calls, 0);
  assert.equal(await submitAccountDeletion('DELETE', 'alice', request), 'requested');
  assert.equal(calls, 1);
});

test('account deletion never claims acceptance after a timeout, account switch or malformed response', async () => {
  for (const response of [null, {}, { status: 'deleted' }, { status: 'failed' }]) {
    await assert.rejects(submitAccountDeletion('DELETE', 'alice', async () => response), /check its status/i);
  }
  for (const message of ['timeout', 'Your account changed']) {
    await assert.rejects(submitAccountDeletion('DELETE', 'alice', async () => { throw Error(message); }), new RegExp(message));
  }
});
