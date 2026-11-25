import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

async function loadModule(path) {
  const source = await readFile(new URL(path, import.meta.url), 'utf8');
  const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } });
  return import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
}
const { createPlayback, availability, assetIdentity, localDay } = await loadModule('../src/lib/playback.ts');
const { createAutoPlayGate, isForegroundAutoPlayDue } = await loadModule('../src/lib/autoPlay.ts');
const { createReadResource } = await loadModule('../src/lib/readResource.ts');
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
const record = (extra = {}) => ({ id: 'brief-1', user_id: 'owner', briefing_date: '2026-11-14', status: 'ready', script: 'First transcript', audio_url: 'https://audio.invalid/one.mp3?token=first', generated_at: '2026-11-14T00:00:00Z', duration_seconds: 120, ...extra });

test('foreground auto-play requires opt-in, current owned ready briefing and delivery time', () => {
  const now = new Date('2026-11-16T07:00:00Z');
  const profile = { timezone: 'UTC', delivery_hour: 7, delivery_minute: 0, auto_play_when_open: true };
  const enabled = (...args) => isForegroundAutoPlayDue(...args, true);
  assert.equal(enabled(profile, record({ briefing_date: '2026-11-16' }), 'owner', 'active', now), true);
  assert.equal(enabled({ ...profile, auto_play_when_open: false }, record({ briefing_date: '2026-11-16' }), 'owner', 'active', now), false);
  assert.equal(enabled(profile, record({ briefing_date: '2026-11-16' }), 'owner', 'background', now), false);
  assert.equal(enabled(profile, record({ briefing_date: '2026-11-16' }), 'another-user', 'active', now), false);
  assert.equal(enabled(profile, record({ briefing_date: '2026-11-15' }), 'owner', 'active', now), false);
  assert.equal(enabled(profile, record({ briefing_date: '2026-11-16', audio_url: null }), 'owner', 'active', now), false);
  assert.equal(enabled(profile, record({ briefing_date: '2026-11-16' }), 'owner', 'active', new Date('2026-11-16T06:59:00Z')), false);
  assert.equal(isForegroundAutoPlayDue(profile, record({ briefing_date: '2026-11-16' }), 'owner', 'active', now), false);
});

test('weekdays-only foreground auto-play stays off on weekends and invalid timezones fail closed', () => {
  const profile = { timezone: 'UTC', delivery_hour: 0, delivery_minute: 0, delivery_schedule: 'weekdays', auto_play_when_open: true };
  assert.equal(isForegroundAutoPlayDue(profile, record({ briefing_date: '2026-11-14' }), 'owner', 'active', new Date('2026-11-14T01:00:00Z'), true), false);
  assert.equal(isForegroundAutoPlayDue({ ...profile, timezone: 'bad/zone' }, record({ briefing_date: '2026-11-16' }), 'owner', 'active', new Date('2026-11-16T01:00:00Z'), true), false);
});

test('automatic start gate is persistent, account scoped, and fails closed on storage errors', async () => {
  const values = new Map();
  const storage = { getItem: async key => values.get(key) ?? null, setItem: async (key, value) => values.set(key, value) };
  const gate = createAutoPlayGate(storage, 'staging');
  assert.equal(await gate.claim('owner', 'brief-1'), true);
  assert.equal(await gate.claim('owner', 'brief-1'), false);
  assert.equal(await gate.claim('other', 'brief-1'), true);
  const failing = createAutoPlayGate({ getItem: async () => { throw Error(); }, setItem: async () => {} }, 'staging');
  assert.equal(await failing.claim('owner', 'brief-2'), false);
});
function setup(fetch = async () => record()) {
  const calls = [];
  const port = {
    prepare: async () => {}, load: async url => { calls.push(['load', url]); }, cancelLoad() {},
    play: () => calls.push(['play']), pause: () => calls.push(['pause']),
    seek: async value => { calls.push(['seek', value]); }, rate: value => calls.push(['rate', value]), stop: () => calls.push(['stop']),
  };
  const controller = createPlayback('owner', port, fetch, () => 1_000_000);
  const tick = (position, playing = true, extra = {}) => controller.status({ currentTime: position, duration: 120, playing, isLoaded: true, isBuffering: false, ...extra });
  return { controller, port, calls, tick };
}

test('availability requires ready status and an audio URL, never script alone', () => {
  assert.equal(availability(null, true), 'loading');
  assert.equal(availability(null, false), 'absent');
  for (const status of ['pending', 'generating', 'failed']) assert.equal(availability(record({ status }), false), status);
  assert.equal(availability(record({ audio_url: null }), false), 'audio-unavailable');
  assert.equal(availability(record({ status: 'unknown' }), false), 'audio-unavailable');
  assert.equal(availability(record(), false), 'ready');
});
test('identity ignores signed query parameters but distinguishes regenerated files and owners', () => {
  assert.equal(assetIdentity(record()), assetIdentity(record({ audio_url: 'https://audio.invalid/one.mp3?token=second' })));
  for (const patch of [{ id: 'other' }, { user_id: 'other' }, { generated_at: 'later' }, { audio_url: 'https://audio.invalid/two.mp3' }]) assert.notEqual(assetIdentity(record()), assetIdentity(record(patch)));
});
test('selecting the same asset across player surfaces keeps a single loaded source and position', async () => {
  const { controller: c, calls, tick } = setup();
  await c.select(record()); tick(31); c.pause();
  await c.select(record({ audio_url: 'https://audio.invalid/one.mp3?token=new' }));
  assert.equal(calls.filter(([name]) => name === 'load').length, 1);
  assert.equal(c.getSnapshot().position, 31);
  assert.equal(c.getSnapshot().intentPlaying, true);
});
test('an explicit player open restarts the same recording from the beginning', async () => {
  const { controller: c, calls, tick } = setup();
  await c.select(record()); tick(47); c.pause();
  await c.select(record({ audio_url: 'https://audio.invalid/one.mp3?token=new' }), true, true);
  assert.equal(c.getSnapshot().position, 0);
  assert.deepEqual(calls.filter(([name]) => name === 'seek').at(-1), ['seek', 0]);
  assert.equal(calls.filter(([name]) => name === 'load').length, 1);
  assert.equal(c.getSnapshot().intentPlaying, true);
});
test('same-asset URL refresh preserves latest position and a pause during the fetch', async () => {
  const response = deferred();
  const { controller: c, calls, tick } = setup(() => response.promise);
  await c.select(record()); tick(20);
  const request = c.refresh();
  assert.equal(c.refresh(), request);
  tick(35); c.pause();
  const before = calls.filter(([name]) => name === 'play').length;
  response.resolve(record({ audio_url: 'https://audio.invalid/one.mp3?token=renewed' }));
  await request;
  assert.equal(c.getSnapshot().position, 35);
  assert.equal(c.getSnapshot().intentPlaying, false);
  assert.equal(calls.filter(([name]) => name === 'play').length, before);
  assert.deepEqual(calls.filter(([name]) => name === 'seek').at(-1), ['seek', 35]);
});
test('pause while native load is pending wins over an earlier autoplay intent', async () => {
  const load = deferred(); const { controller: c, port, calls } = setup();
  port.load = () => load.promise;
  const selecting = c.select(record()); await Promise.resolve(); c.pause();
  load.resolve(); await selecting;
  assert.equal(c.getSnapshot().intentPlaying, false);
  assert.equal(calls.filter(([name]) => name === 'play').length, 0);
});
test('refresh resumes an actively playing recording at its previous position', async () => {
  const { controller: c, calls, tick } = setup(); await c.select(record()); tick(28);
  await c.refresh();
  assert.deepEqual(calls.filter(([name]) => name === 'seek').at(-1), ['seek', 28]);
  assert.equal(calls.filter(([name]) => name === 'play').length, 2);
});
test('new day or regenerated asset from refresh never silently replaces the selected recording', async () => {
  const { controller: c, calls, tick } = setup(async () => record({ id: 'brief-2', script: 'New transcript', audio_url: 'https://audio.invalid/two.mp3' }));
  await c.select(record()); tick(50); await c.refresh();
  assert.equal(c.getSnapshot().record.script, 'First transcript');
  assert.equal(c.getSnapshot().position, 50);
  assert.equal(c.getSnapshot().playing, true);
  assert.ok(c.getSnapshot().error);
  assert.equal(calls.filter(([name]) => name === 'load').length, 1);
});
test('explicit new recording selection resets position and replaces transcript together', async () => {
  const { controller: c, tick } = setup(); await c.select(record()); tick(60);
  await c.select(record({ audio_url: 'https://audio.invalid/two.mp3', generated_at: 'new', script: 'Matching new transcript' }), false);
  assert.equal(c.getSnapshot().position, 0);
  assert.equal(c.getSnapshot().record.script, 'Matching new transcript');
  assert.equal(c.getSnapshot().intentPlaying, false);
});
test('clearing after a category change unloads old audio and resets playback state', async () => {
  const { controller: c, calls, tick } = setup();
  await c.select(record()); tick(44); c.clear();
  assert.equal(c.getSnapshot().record, null);
  assert.equal(c.getSnapshot().position, 0);
  assert.equal(c.getSnapshot().intentPlaying, false);
  assert.equal(calls.filter(([name]) => name === 'stop').length, 1);
});
test('stale refresh after source replacement cannot override new transcript, position or intent', async () => {
  const response = deferred(); const { controller: c, tick } = setup(() => response.promise);
  await c.select(record()); const refreshing = c.refresh();
  await c.select(record({ id: 'next', audio_url: 'https://audio.invalid/next.mp3', script: 'Next' }), false); tick(17, false);
  response.resolve(record()); await refreshing;
  assert.equal(c.getSnapshot().record.script, 'Next'); assert.equal(c.getSnapshot().position, 17);
  assert.equal(c.getSnapshot().intentPlaying, false);
});
test('logout disposes audio and ignores outstanding refresh and foreign-account sources', async () => {
  const response = deferred(); const { controller: c, calls } = setup(() => response.promise);
  await c.select(record()); const refreshing = c.refresh(); c.dispose();
  response.resolve(record()); await refreshing;
  await c.select(record({ user_id: 'someone-else' }));
  assert.equal(c.getSnapshot().record, null);
  assert.equal(calls.filter(([name]) => name === 'stop').length, 1);
  assert.equal(calls.filter(([name]) => name === 'load').length, 1);
});
test('dispose during asynchronous preparation never loads or starts audio', async () => {
  const preparation = deferred(); const { controller: c, port, calls } = setup();
  port.prepare = () => preparation.promise;
  const selecting = c.select(record()); c.dispose(); preparation.resolve(); await selecting;
  assert.equal(calls.filter(([name]) => name === 'play' || name === 'load').length, 0);
});
test('an active player rejects selections and refreshed data belonging to another account', async () => {
  const { controller: c, calls } = setup(async () => record({ user_id: 'other' }));
  await c.select(record({ user_id: 'other' })); assert.equal(c.getSnapshot().record, null);
  await c.select(record()); await c.refresh();
  assert.equal(c.getSnapshot().record.user_id, 'owner'); assert.ok(c.getSnapshot().error);
  assert.equal(calls.filter(([name]) => name === 'load').length, 1);
});
test('late native load failure cannot mark a replacement recording failed', async () => {
  const old = deferred(); const { controller: c, port } = setup(); let loads = 0;
  port.load = () => ++loads === 1 ? old.promise : Promise.resolve();
  const first = c.select(record()); await Promise.resolve();
  await c.select(record({ id: 'replacement', audio_url: 'https://audio.invalid/replacement.mp3', script: 'Replacement' }), false);
  old.reject(Error('obsolete load')); await first;
  assert.equal(c.getSnapshot().record.script, 'Replacement');
  assert.equal(c.getSnapshot().error, null); assert.equal(c.getSnapshot().intentPlaying, false);
});
test('refresh failures stop actual playback and allow a user initiated retry', async () => {
  let fails = true; const { controller: c, calls, tick } = setup(async () => { if (fails) throw Error('private provider detail'); return record(); });
  await c.select(record()); tick(42); await c.refresh();
  assert.equal(c.getSnapshot().playing, false); assert.equal(c.getSnapshot().intentPlaying, false);
  assert.equal(calls.at(-1)[0], 'pause'); assert.doesNotMatch(c.getSnapshot().error, /private/);
  fails = false; await c.refresh(); assert.equal(c.getSnapshot().error, null);
  assert.equal(c.getSnapshot().position, 42); assert.equal(c.getSnapshot().intentPlaying, false);
});
test('failed first native load is recoverable by selecting the same recording again', async () => {
  const { controller: c, port } = setup(); let fails = true;
  port.load = async () => { if (fails) throw Error('expired'); };
  await c.select(record()); assert.ok(c.getSnapshot().error);
  fails = false; await c.select(record()); assert.equal(c.getSnapshot().error, null);
  assert.equal(c.getSnapshot().intentPlaying, true);
});
test('native playback and completion update UI intent; seek and speed are bounded', async () => {
  const { controller: c, tick, calls } = setup(); await c.select(record(), false);
  tick(1, true); assert.equal(c.getSnapshot().intentPlaying, true);
  tick(120, false, { didJustFinish: true }); assert.equal(c.getSnapshot().intentPlaying, false);
  await c.seek(-5); assert.equal(c.getSnapshot().position, 0);
  await c.seek(500); assert.equal(c.getSnapshot().position, 120);
  c.setRate(1.5); c.setRate(20); assert.equal(c.getSnapshot().rate, 1.5);
  assert.deepEqual(calls.filter(([name]) => name === 'rate').at(-1), ['rate', 1.5]);
});
test('profile timezone controls calendar rollover', () => {
  const date = new Date('2026-11-14T18:00:00Z');
  assert.equal(localDay('Asia/Yangon', date), '2026-11-15');
  assert.equal(localDay('UTC', date), '2026-11-14');
});
test('read resources deduplicate in-flight and recent focus events; explicit retry bypasses cooldown', async () => {
  const response = deferred(); let count = 0;
  const resource = createReadResource(async () => { count++; return response.promise; }, () => 1000);
  const first = resource.refresh(); assert.equal(resource.refresh(true), first);
  response.resolve({ value: 1 }); await first; await resource.refresh(); assert.equal(count, 1);
  await resource.refresh(true); assert.equal(count, 2);
  assert.deepEqual(resource.getSnapshot().data, { value: 1 });
});
test('resource refresh failure retains independent known data without exposing provider detail', async () => {
  let fail = false; const resource = createReadResource(async () => { if (fail) throw Error('secret'); return 'known audio'; });
  await resource.refresh(); fail = true; await resource.refresh(true);
  assert.equal(resource.getSnapshot().data, 'known audio'); assert.equal(resource.getSnapshot().loading, false);
  assert.doesNotMatch(resource.getSnapshot().error, /secret/);
});
test('disposed/reactivated resources ignore stale responses from their former lifetime', async () => {
  const old = deferred(); let calls = 0;
  const resource = createReadResource(() => ++calls === 1 ? old.promise : Promise.resolve('new account'));
  const pending = resource.refresh(); resource.dispose(); resource.activate(); await resource.refresh();
  old.resolve('old account'); await pending;
  assert.equal(resource.getSnapshot().data, 'new account');
});

test('URL renewal requests the selected historical record and preserves position', async () => {
  const old = record({id:'historical',briefing_date:'2026-11-01'});
  let requested;
  const {controller,tick}=setup(async selected => {requested=selected; return {...old,audio_url:'https://audio.invalid/one.mp3?token=renewed'};});
  await controller.select(old);
  tick(45);
  await controller.refresh();
  assert.equal(requested.id,'historical');
  assert.equal(controller.getSnapshot().record.briefing_date,'2026-11-01');
  assert.equal(controller.getSnapshot().position,45);
});

test('historical source snapshots survive signed URL renewal with their transcript', async () => {
  const source_metadata = { title: 'Saved briefing', sections: [{ category_id: 'myanmar', narration: 'First transcript', sources: [{ id: 'old-article', title: 'Original title', source: 'Publisher', url: 'https://publisher.invalid/original' }] }] };
  const { controller: c } = setup(async () => record({ source_metadata, audio_url: 'https://audio.invalid/one.mp3?token=renewed' }));
  await c.select(record({ source_metadata }), false);
  await c.refresh();
  assert.deepEqual(c.getSnapshot().record.source_metadata, source_metadata);
  assert.equal(c.getSnapshot().record.script, 'First transcript');
  c.dispose();
});
