import { usePreferences } from '../features/preferences/PreferencesProvider';
import { homeColors, homeGradients } from './home';
const darkColors = { ...homeColors, cream: '#000000', ink: '#FFFFFF', muted: '#A6A6A6', accent: '#FFFFFF', border: '#2B2B2B', heroText: '#FFFFFF', actionText: '#000000' };
const darkGradients = { hero: ['#151515', '#080808', '#151515'], action: ['#FFFFFF', '#FFFFFF'], highlight: ['#111111', '#080808'], surface: ['#000000', '#0B0B0B'] } as const;
export function useHomeTheme() {
  return usePreferences().theme === 'dark' ? { colors: darkColors, gradients: darkGradients } : { colors: homeColors, gradients: homeGradients };
}
