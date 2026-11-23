import { useState } from 'react';
import { Image, Pressable, ScrollView, StyleSheet, useWindowDimensions, View } from 'react-native';
import * as Linking from 'expo-linking';
import { Panel, Type, Notice } from './ui/primitives';
import { useCopy, usePalette } from '../features/preferences/PreferencesProvider';
import { setBookmark, setStoryFeedback, type StoryFeedbackAction } from '../services/newsApi';
export type SourceMetadata = { title: string; generated_at?: string; sections: { category_id: string; category_name: string; narration: string; source_ids?: string[]; sources: { id: string; title: string; source: string; url: string; image_url?: string | null; description?: string | null; published_at?: string | null }[] }[] };
export function BriefingSources({ metadata, dataSaver = false }: { metadata?: SourceMetadata | null; dataSaver?: boolean }) {
  const colors = usePalette(), t = useCopy();
  const { width } = useWindowDimensions();
  const cardWidth = Math.min(380, Math.max(304, width - 64));
  const [error, setError] = useState<string | null>(null);
  const [failedImages, setFailedImages] = useState<Set<string>>(() => new Set());
  const [savedFeedback, setSavedFeedback] = useState<Record<string, string>>({});
  const [openOptions, setOpenOptions] = useState<Set<string>>(() => new Set());
  async function feedback(id: string, action: StoryFeedbackAction) {
    try { setError(null); await setStoryFeedback(id, action); setSavedFeedback(current => ({ ...current, [id]: action })); }
    catch { setError('ရွေးချယ်မှုကို သိမ်းမရပါ။ ပြန်ကြိုးစားပါ။'); }
  }
  async function save(id: string) {
    const next = savedFeedback[id] !== 'saved';
    try { setError(null); await setBookmark(id, next); setSavedFeedback(current => ({ ...current, [id]: next ? 'saved' : 'removed' })); }
    catch { setError('သတင်းကို သိမ်းမရပါ။ ပြန်ကြိုးစားပါ။'); }
  }
  async function open(url: string) {
    try {
      const parsed = new URL(url);
      if (!['http:', 'https:'].includes(parsed.protocol) || !parsed.hostname || parsed.username || parsed.password) throw Error();
      setError(null); await Linking.openURL(url);
    } catch { setError('ဆောင်းပါးကို ဖွင့်မရပါ။ ပြန်ကြိုးစားပါ။'); }
  }
  const seen = new Set<string>();
  return <View style={styles.container}>
    <View style={styles.heading}>
      <Type variant="title">သတင်းအရင်းအမြစ်များ</Type>
      <Type variant="muted">AI ဖြင့် ရေးသားထားသော အနှစ်ချုပ် · နောက်ဆုံးစစ်ဆေးချိန် {metadata?.generated_at?.slice(0, 16).replace('T', ' ') || 'မရရှိပါ'}</Type>
    </View>
    <Notice message={error} />
    {!metadata?.sections?.length ? <Type variant="muted">ဤအနှစ်ချုပ်တွင် အရင်းအမြစ်မှတ်တမ်း မရရှိပါ။</Type> : metadata.sections.map((section, index) => {
      const sources = section.sources.filter(source => { if (seen.has(source.id)) return false; seen.add(source.id); return true; });
      return sources.length ? <View key={`${section.category_id}-${index}`} style={styles.section}>
        <Type variant="label" translate={false}>{section.category_name}</Type>
        <ScrollView horizontal directionalLockEnabled showsHorizontalScrollIndicator={false} contentContainerStyle={styles.scroller}>
          {sources.map((source, sourceIndex) => <Panel key={source.id} style={[styles.card, { width: cardWidth, borderColor: colors.border }]}>
            {!dataSaver && source.image_url && /^https?:\/\/[^\s]+$/i.test(source.image_url) && !failedImages.has(source.id) ? <Image
              accessibilityIgnoresInvertColors
              accessibilityLabel={`${source.title} သတင်းပုံ`}
              source={{ uri: source.image_url }}
              resizeMode="cover"
              onError={() => setFailedImages(current => new Set(current).add(source.id))}
              style={[styles.image, { backgroundColor: colors.background }]}
            /> : null}
            <View style={styles.sourceMeta}>
              <Type variant="muted">{section.source_ids?.includes(source.id) ? 'မူရင်း အရင်းအမြစ်' : 'ဤဖြစ်ရပ်ကို ဖော်ပြထားသည့် အခြားသတင်းဌာန'} · {sourceIndex + 1} / {sources.length}</Type>
              <Type variant="muted" translate={false}>{source.source}{source.published_at ? ` · ${source.published_at.slice(0, 10)}` : ''}</Type>
            </View>
            <Type variant="label" translate={false} numberOfLines={3} style={styles.sourceTitle}>{source.title}</Type>
            <View style={[styles.summary, { borderColor: colors.border, backgroundColor: colors.background }]}>
              <Type variant="muted" style={styles.summaryLabel}>သတင်းအကျဉ်း · အပေါ်အောက် ဆွဲဖတ်ပါ</Type>
              <ScrollView
                nestedScrollEnabled
                directionalLockEnabled
                showsVerticalScrollIndicator
                persistentScrollbar
                style={styles.summaryScroll}
                contentContainerStyle={styles.summaryContent}
              >
                {source.description
                  ? <Type translate={false} style={styles.description} selectable>{source.description}</Type>
                  : <Type style={styles.description}>အကျဉ်းချုပ် မရရှိပါ။ မူရင်းသတင်းကို ဖတ်ရှုပါ။</Type>}
              </ScrollView>
            </View>
            <View style={[styles.actionBar, { borderTopColor: colors.border }]}>
              <SourceAction icon="↗" label={t('မူရင်းဆောင်းပါး ဖတ်မယ် ↗')} onPress={() => void open(source.url)} />
              <SourceAction icon={savedFeedback[source.id] === 'saved' ? '★' : '☆'} label={t(savedFeedback[source.id] === 'saved' ? 'သိမ်းထားမှု ဖယ်မယ်' : 'သိမ်းမယ်')} onPress={() => void save(source.id)} />
              <SourceAction icon="↑" label={t('ပိုပြပါ')} onPress={() => void feedback(source.id, 'more_like_this')} />
              <SourceAction icon="↓" label={t('လျှော့ပြပါ')} onPress={() => void feedback(source.id, 'less_like_this')} />
              <SourceAction icon="⋯" label={t('ရွေးချယ်စရာများ')} selected={openOptions.has(source.id)} onPress={() => setOpenOptions(current => { const next = new Set(current); if (next.has(source.id)) next.delete(source.id); else next.add(source.id); return next; })} />
            </View>
            {openOptions.has(source.id) ? <View style={[styles.optionTray, { backgroundColor: colors.background }]}>
              <OptionAction icon="⚑" label="အမှားတင်ပြမယ်" onPress={() => void feedback(source.id, 'report_incorrect')} />
              <OptionAction icon="◌" label="ဤကဏ္ဍကို ဖျောက်မယ်" onPress={() => void feedback(source.id, 'hide_topic')} />
              <OptionAction icon="⊘" label="ဤသတင်းဌာနကို ဖျောက်မယ်" onPress={() => void feedback(source.id, 'hide_publisher')} />
            </View> : null}
            {savedFeedback[source.id] ? <Type variant="muted">{savedFeedback[source.id] === 'removed' ? 'သိမ်းထားမှု ဖယ်ပြီးပါပြီ။' : 'ရွေးချယ်မှု သိမ်းပြီးပါပြီ။'}</Type> : null}
          </Panel>)}
        </ScrollView>
      </View> : null;
    })}
  </View>;
}

function SourceAction({ icon, label, onPress, selected = false }: { icon: string; label: string; onPress: () => void; selected?: boolean }) {
  const colors = usePalette();
  return <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ selected }} onPress={onPress} style={({ pressed }) => [styles.iconAction, { borderColor: colors.border, backgroundColor: selected ? colors.text : 'transparent' }, pressed && { opacity: 0.6 }]}>
    <Type translate={false} style={{ color: selected ? colors.surface : colors.text, fontSize: 19, lineHeight: 22 }}>{icon}</Type>
  </Pressable>;
}

function OptionAction({ icon, label, onPress }: { icon: string; label: string; onPress: () => void }) {
  const colors = usePalette();
  return <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={onPress} style={({ pressed }) => [styles.optionAction, { borderColor: colors.border }, pressed && { opacity: 0.6 }]}>
    <Type translate={false} style={styles.optionIcon}>{icon}</Type><Type variant="muted" numberOfLines={2}>{label}</Type>
  </Pressable>;
}

const styles = StyleSheet.create({
  container: { gap: 18 }, heading: { gap: 2 }, section: { gap: 8 },
  scroller: { gap: 12, paddingRight: 20, paddingBottom: 8, alignItems: 'flex-start' },
  card: { alignSelf: 'flex-start', padding: 14, gap: 10, borderRadius: 22 },
  image: { width: '100%', aspectRatio: 16 / 8.5, maxHeight: 176, borderRadius: 15 },
  sourceMeta: { gap: 1 },
  sourceTitle: { fontSize: 16, lineHeight: 26 },
  summary: { height: 142, borderWidth: 1, borderRadius: 13, paddingHorizontal: 10, paddingTop: 8, paddingBottom: 5, gap: 3, overflow: 'hidden' },
  summaryLabel: { fontSize: 11, lineHeight: 18, letterSpacing: 0.25 },
  summaryScroll: { flex: 1 },
  summaryContent: { paddingBottom: 12 },
  description: { fontSize: 15, lineHeight: 26 },
  actionBar: { paddingTop: 9, borderTopWidth: StyleSheet.hairlineWidth, flexDirection: 'row', flexWrap: 'wrap', gap: 7 },
  iconAction: { width: 42, height: 42, borderRadius: 14, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  optionTray: { padding: 8, borderRadius: 14, gap: 5 },
  optionAction: { minHeight: 44, borderBottomWidth: StyleSheet.hairlineWidth, flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 5 },
  optionIcon: { width: 24, textAlign: 'center', fontSize: 18 },
});
