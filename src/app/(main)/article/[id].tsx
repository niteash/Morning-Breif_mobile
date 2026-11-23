import { useCallback, useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { Image, Linking, ScrollView, StyleSheet, View } from 'react-native';
import { Button, CircleButton, Notice, Panel, Screen, Type } from '../../../components/ui/primitives';
import { Skeleton } from '../../../components/ui/Skeleton';
import { getArticle, getBookmark, setBookmark } from '../../../services/newsApi';
import { useReadResource } from '../../../hooks/useReadResource';
import { usePalette, usePreferences } from '../../../features/preferences/PreferencesProvider';
export default function ArticleDetail() {
  const params = useLocalSearchParams<{ id: string }>();
  const id = typeof params.id === 'string' ? params.id : '';
  return <ArticleContent key={id} id={id} />;
}
function ArticleContent({ id }: { id: string }) {
  const colors = usePalette(), { language } = usePreferences();
  const article = useReadResource(useCallback(() => getArticle(id), [id]));
  const bookmark = useReadResource(useCallback(() => getBookmark(id), [id]));
  const [busy, setBusy] = useState(false), [error, setError] = useState<string | null>(null);
  const [imageFailed, setImageFailed] = useState(false);
  async function toggle() {
    if (busy || !bookmark.data) return;
    setBusy(true); setError(null);
    try { await setBookmark(id, !bookmark.data.saved); await bookmark.refresh(); }
    catch { setError('သိမ်းဆည်းမရပါ။ ပြန်ကြိုးစားပါ။'); } finally { setBusy(false); }
  }
  async function open() {
    try { const url = new URL(article.data!.article.url); if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password) throw Error(); await Linking.openURL(url.href); }
    catch { setError('သတင်းလင့်ခ် ဖွင့်မရပါ။ ပြန်ကြိုးစားပါ။'); }
  }
  const item = article.data?.article;
  const published = item?.published_at ? new Date(item.published_at) : null;
  return <Screen contentContainerStyle={styles.content}><CircleButton label="နောက်သို့" onPress={() => router.canGoBack() ? router.back() : router.replace('/news')}>‹</CircleButton>
    <Notice message={article.error} retry={() => void article.refresh()} />
    {!item && article.loading ? <Skeleton /> : null}
    {item ? <><View style={styles.kicker}><Type variant="label" translate={false}>{item.source}</Type><Type variant="muted" translate={false}>{published && Number.isFinite(published.getTime()) ? published.toLocaleString(language === 'my' ? 'my-MM' : 'en-GB', { dateStyle: 'medium', timeStyle: 'short' }) : ''}</Type></View>
      <Type translate={false} variant="title" style={styles.headline}>{item.title}</Type>
      {item.author ? <Type translate={false} variant="muted">{item.author}</Type> : null}
      {item.image_url && /^https?:\/\//.test(item.image_url) && !imageFailed ? <Image accessibilityIgnoresInvertColors source={{ uri: item.image_url }} onError={() => setImageFailed(true)} style={[styles.image, { backgroundColor: colors.surface }]} /> : null}
      <Panel style={styles.reader}>
        <View style={styles.readerHeading}><Type variant="label">သတင်းအကျဉ်း</Type><Type variant="muted" style={styles.scrollHint}>အပေါ်အောက် ဆွဲဖတ်ပါ</Type></View>
        <View style={[styles.rule, { backgroundColor: colors.text }]} />
        <ScrollView nestedScrollEnabled directionalLockEnabled showsVerticalScrollIndicator persistentScrollbar style={styles.readerScroll} contentContainerStyle={styles.readerContent}>
          {item.description ? <Type translate={false} style={styles.summary} selectable>{item.description}</Type> : <Type style={styles.summary}>အကျဉ်းချုပ် မရရှိပါ။ မူရင်းသတင်းကို ဖတ်ရှုပါ။</Type>}
        </ScrollView>
      </Panel>
      <Button title="မူရင်းသတင်း ဖတ်မယ် ↗" onPress={() => void open()} />
      <Notice message={bookmark.error} retry={() => void bookmark.refresh()} />
      <Button secondary title={bookmark.data?.saved ? 'သိမ်းထားမှု ဖယ်မယ်' : 'သတင်း သိမ်းမယ်'} busy={busy} disabled={!bookmark.data || Boolean(bookmark.error)} onPress={() => void toggle()} />
    </> : null}<Notice message={error} />
  </Screen>;
}

const styles = StyleSheet.create({
  content: { gap: 20 },
  kicker: { gap: 3 },
  headline: { fontSize: 31, lineHeight: 49, letterSpacing: -0.2 },
  image: { width: '100%', aspectRatio: 16 / 9, borderRadius: 22 },
  reader: { padding: 16, gap: 10, borderRadius: 20 },
  readerHeading: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  scrollHint: { flexShrink: 1, textAlign: 'right', fontSize: 11, lineHeight: 18 },
  readerScroll: { height: 220 },
  readerContent: { paddingBottom: 18 },
  rule: { width: 42, height: 3, borderRadius: 3 },
  summary: { fontSize: 16, lineHeight: 29 },
});
