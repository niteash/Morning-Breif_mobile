import { useEffect } from 'react';
import { View } from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue, withTiming } from 'react-native-reanimated';
import { usePalette } from '../../features/preferences/PreferencesProvider';
import { useMotionReduced } from './Motion';
import { RotatingGlobe } from './RotatingGlobe';

/** Kept as a compatibility name for existing onboarding and player screens. */
export function SunriseOrb({ size = 180, active = true }: { size?: number; active?: boolean }) {
  return <RotatingGlobe size={size} active={active} />;
}

export function StepProgress({ step, total = 5 }: { step: number; total?: number }) {
  const colors = usePalette();
  const reduced = useMotionReduced();
  const progress = useSharedValue(step / total);
  useEffect(() => { progress.set(withTiming(step / total, { duration: reduced ? 0 : 240 })); }, [step, total, progress, reduced]);
  const style = useAnimatedStyle(() => ({ width: `${progress.get() * 100}%` }));
  return <View accessibilityRole="progressbar" accessibilityValue={{ min: 1, max: total, now: step }} style={{ height: 5, borderRadius: 5, backgroundColor: colors.border, overflow: 'hidden' }}><Animated.View style={[{ height: 5, backgroundColor: colors.text, borderRadius: 5 }, style]} /></View>;
}
