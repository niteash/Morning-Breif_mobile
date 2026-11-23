import type { ComponentProps, ReactNode } from 'react';
import { StyleSheet, View, type ViewProps } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { DottedOrb } from '../DottedOrb';
import { Button, Type } from '../ui/primitives';
import { MotionPressable, Reveal } from '../ui/Motion';
import { homeGradients } from '../../theme/home';
import { useHomeTheme } from '../../theme/useHomeTheme';
import { useCopy } from '../../features/preferences/PreferencesProvider';

export function HomePanel({ tone = 'surface', style, children, ...props }: ViewProps & { tone?: keyof typeof homeGradients }) {
  const { colors: c, gradients } = useHomeTheme(), styles = makeStyles(c);
  return <View {...props} style={[styles.panel, style]}>
    <LinearGradient pointerEvents="none" colors={gradients[tone]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={[StyleSheet.absoluteFill, styles.clip]} />
    {children}
  </View>;
}

export function HomeButton({ title, onPress, disabled = false, busy = false, secondary = false, label, compact = false }: ComponentProps<typeof Button> & { compact?: boolean }) {
  const { colors: c, gradients } = useHomeTheme(), styles = makeStyles(c);
  const t = useCopy();
  return <MotionPressable accessibilityRole="button" accessibilityLabel={t(label || title)}
    accessibilityState={{ disabled: disabled || busy, busy }} disabled={disabled || busy} onPress={onPress}
    style={({ pressed }) => [styles.button, compact && styles.compactButton, secondary && styles.secondaryButton, (disabled || busy) && { opacity: 0.5 }, pressed && { opacity: 0.85 }]}>
    {!secondary ? <LinearGradient pointerEvents="none" colors={gradients.action} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={[StyleSheet.absoluteFill, { borderRadius: 100 }]} /> : null}
    <Type variant="label" style={{ color: secondary ? c.ink : c.actionText, textAlign: 'center' }}>{busy ? 'ခဏစောင့်ပါ…' : title}</Type>
  </MotionPressable>;
}

export function HomeNotice({ message, retry }: { message?: string | null; retry?: () => void }) {
  const { colors: c } = useHomeTheme(), styles = makeStyles(c);
  if (!message) return null;
  return <Reveal><HomePanel style={styles.notice}>
    <Type accessibilityRole="alert" style={{ color: c.ink }}>{message}</Type>
    {retry ? <HomeButton secondary title="ပြန်ကြိုးစားမယ်" onPress={retry} /> : null}
  </HomePanel></Reveal>;
}

// Static placeholders with one short reveal: no perpetual shimmer or JS timers.
export function HomeLoading() {
  const { colors: c } = useHomeTheme(), styles = makeStyles(c);
  return <Reveal accessibilityState={{ busy: true }} style={{ gap: 12, paddingVertical: 8 }}>
    <View accessible={false} accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={{ gap: 10 }}>
      <View style={[styles.skeleton, { width: '78%' }]} /><View style={[styles.skeleton, { width: '52%' }]} />
    </View>
    <Type variant="muted" style={{ color: c.muted }}>ခဏစောင့်ပါ…</Type>
  </Reveal>;
}

export function EmptyNews({ refresh }: { refresh: () => void }) {
  const { colors: c } = useHomeTheme();
  return <Reveal><HomePanel tone="highlight" style={{ alignItems: 'center' }}>
    <DottedOrb size={64} />
    <Type variant="label" style={{ color: c.ink, textAlign: 'center' }}>သတင်း မရရှိသေးပါ။</Type>
    <Type variant="muted" style={{ color: c.muted, textAlign: 'center' }}>လတ်တလော သတင်း မရှိသေးပါ။ ခဏအကြာတွင် ပြန်စစ်နိုင်ပါသည်။</Type>
    <HomeButton secondary title="အခြေအနေ ပြန်စစ်မယ်" onPress={refresh} />
  </HomePanel></Reveal>;
}

export function CategoryChip({ children, index }: { children: ReactNode; index: number }) {
  const { colors: c } = useHomeTheme(), styles = makeStyles(c);
  // These are saved-interest labels, not selection controls.
  return <Reveal delay={index * 35} style={styles.chip}><Type variant="muted" style={{ color: c.accent }}>{children}</Type></Reveal>;
}

const makeStyles = (c: ReturnType<typeof useHomeTheme>['colors']) => StyleSheet.create({
  panel: { borderRadius: 18, borderWidth: 1, borderColor: c.border, padding: 22, gap: 14,
    backgroundColor: c.cream, shadowColor: '#000000', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.025, shadowRadius: 10, elevation: 1 },
  clip: { borderRadius: 18 },
  button: { minHeight: 56, paddingHorizontal: 24, paddingVertical: 12, borderRadius: 22, borderWidth: 1, borderColor: c.heroText,
    alignItems: 'center', justifyContent: 'center', backgroundColor: c.gold },
  compactButton: { minHeight: 48, paddingHorizontal: 18, paddingVertical: 8, borderRadius: 18 },
  secondaryButton: { backgroundColor: c.cream, borderColor: c.border, borderWidth: 1 },
  notice: { borderLeftWidth: 3, borderLeftColor: c.accent, shadowOpacity: 0, elevation: 0 },
  skeleton: { height: 12, borderRadius: 8, backgroundColor: c.border },
  chip: { maxWidth: '100%', minHeight: 44, justifyContent: 'center', paddingHorizontal: 16, paddingVertical: 8,
    borderRadius: 24, borderWidth: 1, borderColor: c.border, backgroundColor: c.cream },
});
