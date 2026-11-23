/** Deduplicates read-only refreshes and ignores completions after the owner unmounts. */
export function createReadResource<T>(load: () => Promise<T>, now = Date.now) {
  let snapshot: { data: T | undefined; loading: boolean; error: string | null } = { data: undefined, loading: true, error: null };
  let pending: Promise<void> | undefined, active = true, lastRead = -Infinity, epoch = 0;
  const listeners = new Set<() => void>();
  const publish = (patch: Partial<typeof snapshot>) => { snapshot = { ...snapshot, ...patch }; listeners.forEach(fn => fn()); };
  return {
    getSnapshot: () => snapshot,
    activate() { active = true; },
    subscribe(fn: () => void) { listeners.add(fn); return () => { listeners.delete(fn); }; },
    refresh(force = false): Promise<void> {
      if (!active) return Promise.resolve();
      if (pending) return pending;
      if (!force && now() - lastRead < 5000) return Promise.resolve();
      const version = epoch;
      const valid = () => active && version === epoch;
      publish({ loading: true, error: null });
      pending = load().then(data => { if (valid()) { lastRead = now(); publish({ data }); } }).catch(() => {
        if (valid()) publish({ error: 'အချက်အလက် ရယူမရပါ။ အင်တာနက်ကို စစ်ပြီး ပြန်ကြိုးစားပါ။' });
      }).finally(() => { if (valid()) pending = undefined; if (valid()) publish({ loading: false }); });
      return pending;
    },
    dispose() { active = false; epoch++; pending = undefined; listeners.clear(); },
  };
}
