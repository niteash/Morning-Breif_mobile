export type Preferences = { language: 'my' | 'en'; theme: 'light' | 'dark' };
export const defaultPreferences: Preferences = { language: 'my', theme: 'light' };
export function parsePreferences(raw: string | null): Preferences {
  try { const value = JSON.parse(raw || '{}'); return { language: value?.language === 'en' ? 'en' : 'my', theme: value?.theme === 'dark' ? 'dark' : 'light' }; }
  catch { return defaultPreferences; }
}
export function createPreferences(storage: { getItem(key: string): Promise<string | null>; setItem(key: string, value: string): Promise<void> }) {
  const key = 'nay-thit:appearance:v1';
  let state = { ...defaultPreferences, ready: false, error: false }, revision = 0, writes = Promise.resolve();
  const listeners = new Set<() => void>();
  const emit = () => listeners.forEach(fn => fn());
  return {
    getSnapshot: () => state,
    subscribe(fn: () => void) { listeners.add(fn); return () => { listeners.delete(fn); }; },
    async hydrate() {
      const version = revision;
      try { const value = parsePreferences(await storage.getItem(key)); if (version === revision) { state = { ...state, ...value, ready: true }; emit(); } }
      catch { if (version === revision) { state = { ...state, ready: true, error: true }; emit(); } }
    },
    set(patch: Partial<Preferences>) {
      revision++;
      const version = revision;
      const value = parsePreferences(JSON.stringify({ ...state, ...patch }));
      state = { ...value, ready: true, error: false }; emit();
      writes = writes.catch(() => {}).then(() => storage.setItem(key, JSON.stringify(value))).catch(() => {
        if (version === revision) { state = { ...state, error: true }; emit(); }
      });
      return writes;
    },
  };
}
