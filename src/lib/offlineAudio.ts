import type { Recording } from './playback';
export type OfflineEntry = Omit<Recording, 'audio_url'> & { key: string; saved_at: number };
export type OfflinePort = {
  read(): Promise<OfflineEntry[]>; write(entries: OfflineEntry[]): Promise<void>;
  download(url: string, key: string): Promise<void>; exists(key: string): Promise<boolean>;
  cancel(): Promise<void>; uri(key: string): string; remove(key: string): Promise<void>; clear(): Promise<void>;
};
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export function offlineKey(record: Pick<Recording, 'id' | 'generated_at'>) {
  if (!uuid.test(record.id) || !record.generated_at || !Number.isFinite(Date.parse(record.generated_at))) throw Error('Invalid recording');
  return `${record.id}-${Date.parse(record.generated_at)}`;
}
/** Only an authenticated owner may instantiate this cache. No signed URL is persisted. */
export function createOfflineAudio(owner: string, port: OfflinePort, now = Date.now) {
  let version = 0;
  let maxEntries = 5;
  let disposed = false, entries: OfflineEntry[] = [], pending: Promise<void> | null = null;
  const current = () => { if (disposed) throw Error('Account is no longer active'); };
  return {
    async list() {
      current();
      if (pending) await pending;
      const revision = version;
      const stored = await port.read(); current();
      const valid: OfflineEntry[] = [];
      for (const item of stored) {
        if (!item || typeof item !== 'object') continue;
        if (item.user_id !== owner || item.status !== 'ready' || !Number.isFinite(item.saved_at) || item.saved_at > now() || now() - item.saved_at > 7 * 86400_000) {
          try { if (item.key === offlineKey(item)) await port.remove(item.key); } catch { /* Invalid paths cannot be removed. */ }
          continue;
        }
        try { if (item.key === offlineKey(item) && await port.exists(item.key)) valid.push(item); } catch { /* Corrupt entries are never used. */ }
      }
      current(); if (revision === version) entries = valid.slice(0, maxEntries); return [...entries];
    },
    async save(record: Recording) {
      current();
      if (pending) throw Error('A download is already running');
      if (record.user_id !== owner || record.status !== 'ready' || !record.audio_url) throw Error('Audio unavailable');
      const key = offlineKey(record);
      if (entries.length >= maxEntries && !entries.some(item => item.id === record.id)) throw Error('Remove a download before saving another');
      version++;
      const work = (async () => {
        if (entries.some(item => item.key === key) && await port.exists(key)) return;
        current();
        try {
          await port.download(record.audio_url!, key); current();
          const entry: OfflineEntry = { id: record.id, user_id: owner, briefing_date: record.briefing_date, status: 'ready',
            generated_at: record.generated_at, duration_seconds: record.duration_seconds, script: record.script, key, saved_at: now() };
          const next = [...entries.filter(item => item.id !== record.id), entry];
          await port.write(next); current();
          const replaced = entries.filter(item => item.id === record.id && item.key !== key);
          entries = next;
          for (const item of replaced) await port.remove(item.key);
        } catch (error) { await port.remove(key).catch(() => {}); throw error; }
      })();
      pending = work;
      try { await work; } finally { if (pending === work) pending = null; }
    },
    async open(id: string): Promise<Recording> {
      current();
      const item = entries.find(entry => entry.id === id);
      if (!item || now() - item.saved_at > 7 * 86400_000 || !await port.exists(item.key)) throw Error('Download unavailable');
      current();
      return { ...item, audio_url: port.uri(item.key), offline: true };
    },
    async remove(id: string) {
      current(); version++; if (pending) throw Error('Wait for the download');
      const item = entries.find(entry => entry.id === id);
      if (item) await port.remove(item.key);
      const next = entries.filter(entry => entry.id !== id);
      await port.write(next); current(); entries = next;
    },
    async clear() {
      disposed = true;
      // A late network completion cannot recreate private files after logout.
      await port.cancel().catch(() => {});
      await pending?.catch(() => {});
      await port.clear(); entries = [];
    },
    setLimit(value: number) {
      current();
      maxEntries = Number.isFinite(value) ? Math.max(1, Math.floor(value)) : Number.MAX_SAFE_INTEGER;
    },
  };
}
