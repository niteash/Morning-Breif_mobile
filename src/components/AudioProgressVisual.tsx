import { View } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { homeGradients } from '../theme/home';
import { Type } from './ui/primitives';
/** Fixed-height progress ticks, not audio amplitude. Uses the native playback clock. */
export function AudioProgressVisual({ position, duration }: { position: number; duration: number }) {
  const progress = duration > 0 ? Math.max(0, Math.min(1, position / duration)) : 0;
  return <LinearGradient colors={homeGradients.hero} style={{ padding: 24, borderRadius: 18, gap: 16 }}>
    <View accessible={false} importantForAccessibility="no-hide-descendants" style={{ flexDirection: 'row', gap: 3, height: 40 }}>
      {Array.from({ length: 40 }, (_, i) => <View key={i} style={{ flex: 1, height: 40, borderRadius: 2, backgroundColor: (i + 1) / 40 <= progress ? '#FFFFFF' : '#4B4B4B' }} />)}
    </View>
    <Type variant="muted" style={{ color: '#A6A6A6' }}>နားဆင်မှု တိုးတက်မှု</Type>
  </LinearGradient>;
}
