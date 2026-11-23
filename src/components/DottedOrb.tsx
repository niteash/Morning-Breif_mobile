import { memo, useEffect, useRef, useState } from 'react';
import { AccessibilityInfo, Animated, AppState, Easing, View } from 'react-native';
import { usePalette } from '../features/preferences/PreferencesProvider';

// Deterministic Fibonacci sphere projected into 2D. Decorative, not audio amplitude.
const dots = Array.from({ length: 240 }, (_, i) => {
  const y = 1 - 2 * (i + 0.5) / 240;
  const ring = Math.sqrt(1 - y * y), angle = i * Math.PI * (3 - Math.sqrt(5));
  const z = Math.cos(angle) * ring;
  return { x: Math.sin(angle) * ring, y, z };
});
export const DottedOrb = memo(function DottedOrb({ size = 160, playing = false, active = true }: { size?: number; playing?: boolean; active?: boolean }) {
  const colors = usePalette();
  const [reduceMotion, setReduceMotion] = useState(true);
  const [foreground, setForeground] = useState(AppState.currentState === 'active');
  const phase = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    let mounted = true;
    void AccessibilityInfo.isReduceMotionEnabled().then(value => { if (mounted) setReduceMotion(value); }).catch(() => { /* Keep motion disabled when preference is unavailable. */ });
    const motion = AccessibilityInfo.addEventListener('reduceMotionChanged', setReduceMotion);
    const app = AppState.addEventListener('change', state => setForeground(state === 'active'));
    return () => { mounted = false; motion.remove(); app.remove(); };
  }, []);
  useEffect(() => {
    if (!playing || !active || !foreground || reduceMotion) { phase.setValue(0); return; }
    const loop = Animated.loop(Animated.sequence([
      Animated.timing(phase, { toValue: 1, duration: 2600, easing: Easing.inOut(Easing.sin), useNativeDriver: true, isInteraction: false }),
      Animated.timing(phase, { toValue: 0, duration: 2600, easing: Easing.inOut(Easing.sin), useNativeDriver: true, isInteraction: false }),
    ]));
    loop.start();
    return () => { loop.stop(); phase.setValue(0); };
  }, [playing, active, foreground, reduceMotion, phase]);
  return <View accessible={false} accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={{ alignItems: 'center', justifyContent: 'center', height: size + 12 }}>
    <Animated.View style={{ width: size, height: size, opacity: phase.interpolate({ inputRange: [0, 1], outputRange: [0.65, 0.9] }), transform: [{ scale: phase.interpolate({ inputRange: [0, 1], outputRange: [0.97, 1.03] }) }, { rotate: phase.interpolate({ inputRange: [0, 1], outputRange: ['-3deg', '3deg'] }) }] }}>
      {dots.map((dot, i) => { const width = 1.5 + (dot.z + 1) * 0.8; return <View key={i} style={{ position: 'absolute', left: (dot.x + 1) * (size - 6) / 2, top: (dot.y + 1) * (size - 6) / 2, width, height: width, borderRadius: width, backgroundColor: colors.text, opacity: 0.12 + (dot.z + 1) * 0.35 }} />; })}
    </Animated.View>
  </View>;
});
