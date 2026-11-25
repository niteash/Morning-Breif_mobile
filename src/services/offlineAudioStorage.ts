import { Platform } from 'react-native';
import { Directory, File, Paths } from 'expo-file-system';
import { createDownloadResumable } from 'expo-file-system/legacy';
import { createOfflineAudio, type OfflineEntry, type OfflinePort } from '../lib/offlineAudio';
const keyPattern = /^[0-9a-f-]{36}-\d+$/i;
function root(owner: string) {
  if (!/^[0-9a-f-]{36}$/i.test(owner)) throw Error('Invalid account');
  const project = new URL(process.env.EXPO_PUBLIC_SUPABASE_URL!).hostname;
  return new Directory(Paths.cache, 'nay-thit-audio', project, owner);
}
export function createNativeOfflineAudio(owner: string) {
  if (Platform.OS === 'web') {
    const unavailable = async (): Promise<never> => { throw Error('Native downloads are unavailable on web'); };
    return createOfflineAudio(owner, { read: async () => [], write: unavailable, download: unavailable,
      exists: async () => false, uri: () => '', remove: unavailable, clear: async () => {}, cancel: async () => {} });
  }
  const directory = root(owner);
  let retired = false;
  let cancelDownload: (() => Promise<void>) | null = null;
  const file = (key: string) => { if (!keyPattern.test(key)) throw Error('Invalid download'); return new File(directory, `${key}.mp3`); };
  const ensure = () => directory.create({ intermediates: true, idempotent: true });
  const active = async () => { if (retired || activeOwner !== owner) throw Error('Account changed'); await clearing; if (retired || activeOwner !== owner) throw Error('Account changed'); };
  const port: OfflinePort = {
    async read() {
      await active();
      const parent = directory.parentDirectory;
      if (parent.exists) for (const entry of parent.list()) if (entry.name !== owner) entry.delete();
      const index = new File(directory, 'index.json');
      if (!index.exists) return [];
      const value: unknown = JSON.parse(await index.text());
      if (!Array.isArray(value)) throw Error('Invalid download index');
      return value as OfflineEntry[];
    },
    async write(entries) {
      await active(); ensure();
      const temp = new File(directory, 'index.tmp'); temp.write(JSON.stringify(entries));
      const index = new File(directory, 'index.json'); if (index.exists) index.delete(); await temp.move(index);
    },
    async download(url, key) {
      await active();
      // Only signed briefing audio from this exact configured Supabase project.
      const parsed = new URL(url), expected = new URL(process.env.EXPO_PUBLIC_SUPABASE_URL!);
      const expectedPath = `/storage/v1/object/sign/briefings/${owner}/`;
      if (parsed.origin !== expected.origin || parsed.protocol !== 'https:' || !parsed.pathname.startsWith(expectedPath) || parsed.username || parsed.password) throw Error('Invalid audio source');
      ensure();
      const destination = file(key), temp = new File(directory, `${key}.part`);
      if (temp.exists) temp.delete();
      let tooLarge = false;
      const download = createDownloadResumable(url, temp.uri, {}, progress => {
        if (progress.totalBytesWritten > 40 * 1024 * 1024 || progress.totalBytesExpectedToWrite > 40 * 1024 * 1024) {
          tooLarge = true; void download.cancelAsync().catch(() => {});
        }
      });
      cancelDownload = () => download.cancelAsync();
      const timer = setTimeout(() => { void download.cancelAsync().catch(() => {}); }, 90_000);
      try {
        const result = await download.downloadAsync();
        if (!result || result.status !== 200 || tooLarge || !temp.exists || temp.size <= 0 || temp.size > 40 * 1024 * 1024) throw Error('Download incomplete');
        const contentType = Object.entries(result.headers).find(([name]) => name.toLowerCase() === 'content-type')?.[1] || '';
        if (!/^(audio\/|application\/octet-stream)/i.test(contentType)) throw Error('Invalid audio response');
        await active();
        if (!temp.exists) throw Error('Download temporary file unavailable');
        if (destination.exists) destination.delete();
        await temp.move(destination);
      } finally { cancelDownload = null; clearTimeout(timer); if (temp.exists) temp.delete(); }
    },
    async cancel() { retired = true; await cancelDownload?.(); },
    async exists(key) { return file(key).exists && file(key).size > 0; },
    uri: key => file(key).uri,
    async remove(key) { const target = file(key); if (target.exists) target.delete(); },
    async clear() { if (directory.exists) directory.delete(); },
  };
  return createOfflineAudio(owner, port);
}

let activeOwner: string | null = null;
let clearing: Promise<void> | null = null;
const caches = new Map<string, ReturnType<typeof createNativeOfflineAudio>>();
export function getOfflineAudio(owner: string) {
  activeOwner = owner;
  let cache = caches.get(owner);
  if (!cache) {
    cache = createNativeOfflineAudio(owner); caches.set(owner, cache);
  }
  return cache;
}
export function clearOfflineAudio(): Promise<void> {
  if (Platform.OS === 'web') return Promise.resolve();
  if (clearing) return clearing;
  const previous = [...caches.values()]; caches.clear(); activeOwner = null;
  const operation = (async () => {
    await Promise.all(previous.map(cache => cache.clear()));
    const parent = new Directory(Paths.cache, 'nay-thit-audio');
    if (parent.exists) parent.delete();
  })();
  clearing = operation;
  void operation.finally(() => { if (clearing === operation) clearing = null; }).catch(() => {});
  return operation;
}
