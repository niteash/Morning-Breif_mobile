import { Stack } from 'expo-router';
import { AuthGate } from '../../components/AuthGate';
import { PlaybackProvider } from '../../features/playback/PlaybackProvider';
import { usePalette } from '../../features/preferences/PreferencesProvider';
function MainStack() {
  const colors = usePalette();
  return <PlaybackProvider><Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.background } }}>
    <Stack.Screen name="(tabs)" />
    <Stack.Screen name="player" />
    <Stack.Screen name="category-preferences" />
    <Stack.Screen name="legal" />
  </Stack></PlaybackProvider>;
}
export default function MainLayout() { return <AuthGate requireOnboarding><MainStack /></AuthGate>; }
