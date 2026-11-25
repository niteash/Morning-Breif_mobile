import { useEffect } from 'react';
import { View, AppState } from 'react-native';
import Animated, { cancelAnimation, useAnimatedStyle, useSharedValue, withRepeat, withTiming } from 'react-native-reanimated';
import { useMotionReduced } from './Motion';
import { usePalette, useCopy } from '../../features/preferences/PreferencesProvider';
export function Skeleton({ count = 3 }: { count?: number }) {
  const colors = usePalette(), t = useCopy();
  const reduced = useMotionReduced(), opacity = useSharedValue(0.6);
  useEffect(() => {
    const update = (active: boolean) => { cancelAnimation(opacity); opacity.set(active && !reduced ? withRepeat(withTiming(1, { duration: 850 }), -1, true) : 0.8); };
    update(AppState.currentState === 'active');
    const sub = AppState.addEventListener('change', value => update(value === 'active'));
    return () => { sub.remove(); cancelAnimation(opacity); };
  }, [opacity, reduced]);
  const animated = useAnimatedStyle(() => ({ opacity: opacity.get() }));
  return <View accessibilityLabel={t('ခဏစောင့်ပါ…')} accessibilityState={{ busy: true }} style={{ gap: 16 }}>
    {Array.from({ length: count }, (_, i) => <Animated.View key={i} importantForAccessibility="no-hide-descendants" style={[{ borderRadius: 24, padding: 24, gap: 14, backgroundColor: colors.surface }, animated]}>
      {[45, 100, 75].map(width => <View key={width} style={{ width: `${width}%`, height: 16, borderRadius: 8, backgroundColor: colors.border }} />)}
    </Animated.View>)}
  </View>;
}
