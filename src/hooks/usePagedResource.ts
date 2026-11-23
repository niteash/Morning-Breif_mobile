import { useEffect, useMemo, useSyncExternalStore } from 'react';
import { createPagedResource } from '../lib/pagedResource';
export function usePagedResource<T extends { id: string }>(loader: (offset: number) => Promise<{ items: T[]; next_offset: number | null }>) {
  const resource = useMemo(() => createPagedResource(loader, item => item.id), [loader]);
  const state = useSyncExternalStore(resource.subscribe, resource.getSnapshot, resource.getSnapshot);
  useEffect(() => { resource.activate(); void resource.refresh(); return () => resource.dispose(); }, [resource]);
  return { ...state, refresh: resource.refresh, more: resource.more };
}
