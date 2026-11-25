import { Children, createContext, useContext, type ReactNode } from 'react';
import { ActivityIndicator, KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, TextInput, View, type TextProps, type TextInputProps, type ViewProps, type ScrollViewProps } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { useCopy, usePalette } from '../../features/preferences/PreferencesProvider';
import { MotionPressable } from './Motion';

export const FontReadyContext = createContext(false);
export function Type({ variant = 'body', style, children, translate = true, ...props }: TextProps & { variant?: 'body' | 'title' | 'hero' | 'label' | 'muted'; translate?: boolean }) {
  const colors = usePalette(), t = useCopy(), styles = makeStyles(colors);
  const ready = useContext(FontReadyContext);
  const bold = ['title', 'hero', 'label'].includes(variant);
  return <Text {...props} accessibilityLabel={props.accessibilityLabel ? t(props.accessibilityLabel) : undefined} style={[styles.text, styles[variant], ready && { fontFamily: bold ? 'PadaukBold' : 'Padauk', fontWeight: 'normal' }, style]}>{translate ? Children.map(children, child => typeof child === 'string' ? t(child) : child) : children}</Text>;
}
export function Screen({ children, keyboard = false, refreshControl, ...props }: ScrollViewProps & { keyboard?: boolean }) {
  const colors = usePalette(), styles = makeStyles(colors);
  const insets = useSafeAreaInsets();
  return <SafeAreaView style={styles.screen} edges={['top', 'left', 'right']}>
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
      <ScrollView {...props} keyboardShouldPersistTaps="handled" keyboardDismissMode={keyboard ? 'on-drag' : 'none'} refreshControl={refreshControl} contentContainerStyle={[styles.content, { paddingBottom: Math.max(40, insets.bottom + 24) }, props.contentContainerStyle]}>{children}</ScrollView>
    </KeyboardAvoidingView>
  </SafeAreaView>;
}
export function Panel({ style, ...props }: ViewProps) {
  const colors = usePalette(), styles = makeStyles(colors); return <View {...props} style={[styles.panel, style]} />; }
export function Button({ title, onPress, disabled = false, busy = false, secondary = false, label }: { title: string; onPress: () => void; disabled?: boolean; busy?: boolean; secondary?: boolean; label?: string }) {
  const colors = usePalette(), t = useCopy(), styles = makeStyles(colors);
  return <MotionPressable accessibilityRole="button" accessibilityLabel={t(label || title)} accessibilityState={{ disabled: disabled || busy, busy }} disabled={disabled || busy} onPress={onPress} style={({ pressed }) => [styles.button, secondary && styles.secondaryButton, (disabled || busy) && styles.disabled, pressed && { opacity: 0.7 }]}>
    {busy ? <ActivityIndicator color={secondary ? colors.text : colors.surface} /> : null}
    <Type variant="label" style={{ color: secondary ? colors.text : colors.surface, textAlign: 'center', flexShrink: 1 }}>{title}</Type>
  </MotionPressable>;
}
export function CircleButton({ label, children, onPress, disabled = false, dark = false }: { label: string; children: ReactNode; onPress: () => void; disabled?: boolean; dark?: boolean }) {
  const colors = usePalette(), t = useCopy(), styles = makeStyles(colors);
  return <MotionPressable accessibilityRole="button" accessibilityLabel={t(label)} accessibilityState={{ disabled }} disabled={disabled} onPress={onPress} style={({ pressed }) => [styles.circle, dark && { backgroundColor: colors.text }, disabled && styles.disabled, pressed && { opacity: 0.65 }]}>
    <Text style={{ fontSize: 21, color: dark ? colors.surface : colors.text }}>{children}</Text>
  </MotionPressable>;
}
export function Field({ label, style, ...props }: TextInputProps & { label: string }) {
  const colors = usePalette(), t = useCopy(), styles = makeStyles(colors);
  const ready = useContext(FontReadyContext);
  return <View style={{ gap: 8 }}><Type variant="label">{label}</Type><TextInput {...props} accessibilityLabel={t(props.accessibilityLabel || label)} placeholder={props.placeholder ? t(props.placeholder) : undefined} placeholderTextColor={colors.secondary} style={[styles.field, ready && { fontFamily: 'Padauk' }, style]} /></View>;
}
export function Notice({ message, retry, action = 'ပြန်ကြိုးစားမယ်' }: { message?: string | null; retry?: () => void; action?: string }) {
  const colors = usePalette(), styles = makeStyles(colors);
  if (!message) return null;
  return <View style={styles.notice}><Type accessibilityRole="alert">{message}</Type>{retry ? <Button title={action} onPress={retry} secondary /> : null}</View>;
}
export function Loading({ label = 'ခဏစောင့်ပါ…' }: { label?: string }) {
  const colors = usePalette(), styles = makeStyles(colors); return <View style={styles.loading}><ActivityIndicator color={colors.text} /><Type variant="muted">{label}</Type></View>; }
export function Brand() {
  return <View><Type translate={false} variant="title" style={{ letterSpacing: -1 }}>NAY THIT</Type><Type variant="muted" style={{ letterSpacing: 2.4, fontSize: 11 }}>နေ့သစ် · PERSONAL NEWS</Type></View>; }
const makeStyles = (colors: ReturnType<typeof usePalette>) => StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: 24, paddingBottom: 40, gap: 24, flexGrow: 1 },
  text: { color: colors.text, fontSize: 17, lineHeight: 30, flexShrink: 1, includeFontPadding: true },
  body: {}, muted: { color: colors.secondary, fontSize: 15, lineHeight: 27 },
  label: { fontWeight: '600', fontSize: 16, lineHeight: 28 },
  title: { fontSize: 28, lineHeight: 46, fontWeight: '700' },
  hero: { fontSize: 36, lineHeight: 58, fontWeight: '700' },
  panel: { backgroundColor: colors.surface, borderRadius: 18, padding: 24, gap: 16, borderWidth: 1, borderColor: colors.border },
  button: { minHeight: 56, paddingHorizontal: 24, paddingVertical: 12, borderRadius: 22, backgroundColor: colors.text, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 12 },
  secondaryButton: { backgroundColor: 'transparent', borderColor: colors.border, borderWidth: 1 },
  disabled: { opacity: 0.45 },
  circle: { width: 52, height: 52, alignSelf: 'flex-start', borderRadius: 26, padding: 10, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: colors.border },
  field: { minHeight: 60, borderRadius: 14, paddingHorizontal: 18, paddingVertical: 14, color: colors.text, backgroundColor: colors.surface, borderColor: colors.border, borderWidth: 1, fontSize: 18, lineHeight: 30 },
  notice: { borderLeftWidth: 2, borderColor: colors.text, paddingLeft: 16, gap: 12 },
  loading: { paddingVertical: 16, flexDirection: 'row', alignItems: 'center', gap: 12 },
});
