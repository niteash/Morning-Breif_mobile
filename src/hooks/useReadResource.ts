import { useCallback, useEffect, useMemo, useSyncExternalStore } from 'react';
import { AppState } from 'react-native';
import { useFocusEffect } from 'expo-router';
import { createReadResource } from '../lib/readResource';

// Callers pass a stable useCallback loader. Each owner has a separate resource lifetime.
export function useReadResource<T>(loader: () => Promise<T>) {
  const resource = useMemo(() => createReadResource(loader), [loader]);
  const state = useSyncExternalStore(resource.subscribe, resource.getSnapshot, resource.getSnapshot);
  useEffect(() => { resource.activate(); void resource.refresh(); return () => resource.dispose(); }, [resource]);
  const refresh = useCallback((force = true) => resource.refresh(force), [resource]);
  return { ...state, refresh };
}
export function useReadRefresh(refresh: () => void) {
  useFocusEffect(useCallback(() => {
    refresh();
    const listener = AppState.addEventListener('change', value => { if (value === 'active') refresh(); });
    return () => listener.remove();
  }, [refresh]));
}
