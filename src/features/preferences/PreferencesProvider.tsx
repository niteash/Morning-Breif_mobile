import { createContext, useContext, useEffect, useState, useSyncExternalStore, type ReactNode } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { createPreferences, type Preferences } from '../../lib/preferences';
import { translate } from '../../theme/copy';
const palettes = {
  light: { background: '#FFFFFF', surface: '#FFFFFF', text: '#000000', secondary: '#656565', border: '#DADADA' },
  dark: { background: '#000000', surface: '#0B0B0B', text: '#FFFFFF', secondary: '#A6A6A6', border: '#2B2B2B' },
};
type ContextValue = Preferences & { error: boolean; ready: boolean; set(patch: Partial<Preferences>): Promise<void> };
const Context = createContext<ContextValue>({ language: 'my', theme: 'light', ready: false, error: false, set: async () => {} });
export function PreferencesProvider({ children }: { children: ReactNode }) {
  const [controller] = useState(() => createPreferences(AsyncStorage));
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  useEffect(() => { void controller.hydrate(); }, [controller]);
  return <Context.Provider value={{ ...state, set: controller.set }}>{children}</Context.Provider>;
}
export const usePreferences = () => useContext(Context);
export function usePalette() { return palettes[usePreferences().theme]; }
export function useCopy() { const { language } = usePreferences(); return (copy: string) => translate(copy, language); }
