export function createPagedResource<T>(fetchPage: (offset: number) => Promise<{ items: T[]; next_offset: number | null }>, identity: (item: T) => string) {
  let state = { items: [] as T[], next: null as number | null, loading: false, error: null as string | null, loaded: false };
  let epoch = 0, disposed = false;
  const listeners = new Set<() => void>();
  const publish = (patch: Partial<typeof state>) => { state = { ...state, ...patch }; listeners.forEach(fn => fn()); };
  async function load(reset: boolean) {
    if (disposed || (!reset && (state.loading || state.next === null))) return;
    const version = ++epoch, offset = reset ? 0 : state.next!;
    publish({ loading: true, error: null });
    try {
      const page = await fetchPage(offset);
      if (disposed || version !== epoch) return;
      const entries = new Map((reset ? [] : state.items).map(item => [identity(item), item]));
      page.items.forEach(item => entries.set(identity(item), item));
      publish({ items: [...entries.values()], next: page.next_offset, loaded: true });
    } catch { if (!disposed && version === epoch) publish({ error: 'ဖွင့်မရပါ။ ပြန်ကြိုးစားပါ။' }); }
    finally { if (!disposed && version === epoch) publish({ loading: false }); }
  }
  return { subscribe(fn: () => void) { listeners.add(fn); return () => { listeners.delete(fn); }; }, getSnapshot: () => state,
    refresh: () => load(true), more: () => load(false), activate() { disposed = false; }, dispose() { disposed = true; epoch++; } };
}
