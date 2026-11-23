import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { AccessibilityInfo, Pressable, type PressableProps, type ViewProps } from 'react-native';
import Animated, { FadeInDown, ReduceMotion, useAnimatedStyle, useReducedMotion, useSharedValue, withSpring } from 'react-native-reanimated';

const MotionContext = createContext(true);

export function MotionProvider({ children }: { children: ReactNode }) {
  const systemPreference = useReducedMotion();
  const [reduced, setReduced] = useState(systemPreference);
  useEffect(() => {
    let mounted = true;
    void AccessibilityInfo.isReduceMotionEnabled().then(value => { if (mounted) setReduced(value); }).catch(() => { if (mounted) setReduced(true); });
    const listener = AccessibilityInfo.addEventListener('reduceMotionChanged', setReduced);
    return () => { mounted = false; listener.remove(); };
  }, []);
  return <MotionContext.Provider value={reduced}>{children}</MotionContext.Provider>;
}

export function Reveal({ delay = 0, ...props }: ViewProps & { delay?: number }) {
  const reduced = useContext(MotionContext);
  const entering = useMemo(() => FadeInDown.duration(280).delay(Math.min(delay, 220))
    .withInitialValues({ transform: [{ translateY: 10 }] })
    .reduceMotion(reduced ? ReduceMotion.Always : ReduceMotion.System), [delay, reduced]);
  return <Animated.View {...props} entering={entering} />;
}

/** Feedback stays on the UI thread and never changes the action or touch target. */
export function MotionPressable({ style, onPressIn, onPressOut, ...props }: PressableProps) {
  const reduced = useContext(MotionContext);
  const scale = useSharedValue(1);
  const feedback = useAnimatedStyle(() => ({ transform: [{ scale: reduced ? 1 : scale.get() }] }));
  const animate = (value: number) => {
    scale.set(withSpring(value, { duration: 220, dampingRatio: 1, reduceMotion: reduced ? ReduceMotion.Always : ReduceMotion.System }));
  };
  return <Animated.View style={feedback}><Pressable {...props}
    onPressIn={event => { animate(0.98); onPressIn?.(event); }}
    onPressOut={event => { animate(1); onPressOut?.(event); }}
    style={style} /></Animated.View>;
}

export function useMotionReduced() { return useContext(MotionContext); }
