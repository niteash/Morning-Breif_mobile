import { router } from 'expo-router';
import { useState } from 'react';
import { Image, Linking, Pressable, StyleSheet, View } from 'react-native';
import type { NewsItem } from '../services/newsApi';
import { setBookmark } from '../services/newsApi';
import { Type } from './ui/primitives';
import { usePalette, useCopy, usePreferences } from '../features/preferences/PreferencesProvider';
import { useHomeTheme } from '../theme/useHomeTheme';
import { MotionPressable } from './ui/Motion';
import { useBriefing } from '../features/playback/PlaybackProvider';
export function ArticleCard({ article, compact = false, appearance = 'default', initialSaved = false, onBookmarkChange }: { article: NewsItem; compact?: boolean; appearance?: 'default' | 'sunrise'; initialSaved?: boolean; onBookmarkChange?: (saved: boolean) => void }) {
  const colors = usePalette(), t = useCopy(), { language } = usePreferences();
  const { profile } = useBriefing();
  const dataSaver = profile.data?.data_saver_enabled === true;
  const { colors: homeColors } = useHomeTheme();
  const warm = appearance === 'sunrise';
  const LinkControl = warm ? MotionPressable : Pressable;
  const [imageFailed, setImageFailed] = useState(false);
  const [saved, setSaved] = useState(initialSaved);
  const [bookmarkBusy, setBookmarkBusy] = useState(false);
  const [options, setOptions] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const date = article.published_at ? new Date(article.published_at) : null;
  const view = () => router.push({ pathname: '/article/[id]', params: { id: article.id } });
  async function toggleSaved() {
    if (bookmarkBusy) return;
    setBookmarkBusy(true); setError(null);
    try { const next = !saved; await setBookmark(article.id, next); setSaved(next); onBookmarkChange?.(next); }
    catch { setError(t('သိမ်းဆည်းမရပါ။ ပြန်ကြိုးစားပါ။')); }
    finally { setBookmarkBusy(false); }
  }
  async function openPublisher() {
    try {
      const url = new URL(article.url);
      if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password) throw Error();
      await Linking.openURL(url.href);
    } catch { setError(t('သတင်းလင့်ခ် ဖွင့်မရပါ။ ပြန်ကြိုးစားပါ။')); }
  }
  return <View style={{ backgroundColor: warm ? homeColors.cream : colors.surface, borderRadius: 18, padding: 20, gap: 12, borderWidth: 1, borderColor: warm ? homeColors.border : colors.border }}>
    <LinkControl accessibilityRole="link" accessibilityLabel={`${article.title} — ${t('သတင်းအသေးစိတ် →')}`} onPress={view} style={{ gap: 12, minHeight: 48 }}>
      {!compact && !dataSaver && article.image_url && /^https?:\/\//.test(article.image_url) && !imageFailed ? <Image accessibilityIgnoresInvertColors source={{ uri: article.image_url }} onError={() => setImageFailed(true)} style={{ width: '100%', height: 160, borderRadius: 16, backgroundColor: colors.background }} /> : null}
      <Type translate={false} variant="muted">{article.source}{date && Number.isFinite(date.getTime()) ? ` · ${date.toLocaleString(language === 'my' ? 'my-MM' : 'en-GB', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}` : ''}</Type>
      <Type translate={false} variant="label" style={{ fontSize: 19, lineHeight: 32, color: warm ? homeColors.ink : colors.text }}>{article.title}</Type>
      {!compact && article.description ? <Type translate={false} variant="muted" numberOfLines={3}>{article.description}</Type> : null}
    </LinkControl>
    <View style={[styles.actions, { borderTopColor: warm ? homeColors.border : colors.border }]}>
      <CardAction icon="↗" label={t('ကြည့်မယ်')} onPress={view} />
      <CardAction icon={saved ? '★' : '☆'} label={t(saved ? 'သိမ်းထားမှု ဖယ်မယ်' : 'သတင်း သိမ်းမယ်')} busy={bookmarkBusy} onPress={() => void toggleSaved()} />
      <CardAction icon="⋯" label={t('ရွေးချယ်စရာများ')} selected={options} onPress={() => setOptions(value => !value)} />
    </View>
    {options ? <View style={[styles.options, { backgroundColor: warm ? '#F1EDE4' : colors.background }]}>
      <Pressable accessibilityRole="link" onPress={() => void openPublisher()} style={styles.publisherLink}><Type variant="label">⌁</Type><Type variant="muted">မူရင်းသတင်း ဖတ်မယ် ↗</Type></Pressable>
    </View> : null}
    {error ? <Type variant="muted" accessibilityRole="alert">{error}</Type> : null}
  </View>;
}

function CardAction({ icon, label, onPress, selected = false, busy = false }: { icon: string; label: string; onPress: () => void; selected?: boolean; busy?: boolean }) {
  const colors = usePalette();
  return <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ selected, busy, disabled: busy }} disabled={busy} onPress={onPress} style={({ pressed }) => [styles.action, { borderColor: colors.border, backgroundColor: selected ? colors.text : 'transparent' }, pressed && { opacity: 0.6 }, busy && { opacity: 0.45 }]}>
    <Type translate={false} style={{ color: selected ? colors.surface : colors.text, fontSize: 20, lineHeight: 23 }}>{icon}</Type>
  </Pressable>;
}

const styles = StyleSheet.create({
  actions: { paddingTop: 10, borderTopWidth: StyleSheet.hairlineWidth, flexDirection: 'row', justifyContent: 'flex-end', gap: 8 },
  action: { width: 44, height: 44, borderRadius: 15, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  options: { borderRadius: 14, paddingHorizontal: 12 },
  publisherLink: { minHeight: 46, flexDirection: 'row', alignItems: 'center', gap: 9 },
});
