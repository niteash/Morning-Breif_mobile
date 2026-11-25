import { getEntitlement } from '../../../services/entitlementApi';
import { Skeleton } from '../../../components/ui/Skeleton';
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, RefreshControl, StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
import { Brand, Screen, Type } from '../../../components/ui/primitives';
import { MotionProvider, Reveal } from '../../../components/ui/Motion';
import { CategoryChip, EmptyNews, HomeButton as Button, HomeNotice as Notice, HomePanel as Panel } from '../../../components/home/HomePresentation';
import { RotatingGlobe } from '../../../components/ui/RotatingGlobe';
import { ArticleCard } from '../../../components/ArticleCard';
import { useBriefing } from '../../../features/playback/PlaybackProvider';
import { availability, clockTime, localDay, type Availability } from '../../../lib/playback';
import { useReadRefresh, useReadResource } from '../../../hooks/useReadResource';
import { getMyCategories } from '../../../services/userApi';
import { getNews } from '../../../services/newsApi';
import { useHomeTheme } from '../../../theme/useHomeTheme';
import { usePreferences, useCopy } from '../../../features/preferences/PreferencesProvider';
import { SponsoredBanner } from '../../../components/ads/SponsoredBanner';

const messages: Record<Availability, string> = {
  loading: 'အနှစ်ချုပ်ကို ရှာဖွေနေသည်…', absent: 'ယနေ့အတွက် အနှစ်ချုပ် ပြင်ဆင်မလား?',
  pending: 'အနှစ်ချုပ် စောင့်ဆိုင်းနေသည်', generating: 'အနှစ်ချုပ် ပြင်ဆင်နေသည်',
  ready: 'နားဆင်ရန် အသင့်ရှိပါပြီ', failed: 'အနှစ်ချုပ် ပြင်ဆင်မှု မအောင်မြင်ပါ',
  'audio-unavailable': 'အသံလင့်ခ် မရရှိသေးပါ',
};
export default function HomeScreen() {
  return <MotionProvider><HomeContent /></MotionProvider>;
}

function HomeContent() {
  const { colors: c } = useHomeTheme(), { language } = usePreferences();
  const styles = makeStyles(c), t = useCopy();
  const data = useBriefing();
  const { saved, profile, generating, generationStartedAt, generationError, generationErrorCode,
    generationJob, categorySelectionChanged, generate, controller } = data;
  const news = useReadResource(useCallback(() => getNews({ limit: 3 }), []));
  const interests = useReadResource(useCallback(() => getMyCategories(), []));
  const entitlement = useReadResource(useCallback(() => getEntitlement(), []));
  const trial = entitlement.data;
  const [now, setNow] = useState(() => new Date());
  const [confirmRegenerate, setConfirmRegenerate] = useState(false);
  const [generationNow, setGenerationNow] = useState(() => Date.now());
  useEffect(() => {
    if (!generating) return;
    const timer = setInterval(() => setGenerationNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [generating]);
  const refresh = data.refresh, refreshNews = news.refresh, refreshInterests = interests.refresh, refreshTrial = entitlement.refresh;
  useReadRefresh(useCallback(() => {
    setNow(new Date()); refresh(); void refreshNews(false); void refreshInterests(false); void refreshTrial(false);
  }, [refresh, refreshNews, refreshInterests, refreshTrial]));

  const record = saved.data || null;
  const state = generating ? 'generating' : categorySelectionChanged ? 'absent' : availability(record, saved.loading);
  const timezone = profile.data?.timezone;
  const day = timezone ? localDay(timezone, now) : null;
  const oldDate = record && day && record.briefing_date !== day;
  // Cached entitlement must never enable an action after a failed status refresh.
  const authorized = trial?.can_generate === true && !entitlement.error && !entitlement.loading;
  const canGenerate = authorized && !saved.error && !saved.loading && !generating && ['absent', 'failed'].includes(state);
  const generationSeconds = generating && generationStartedAt
    ? Math.max(0, Math.floor((generationNow - generationStartedAt) / 1000))
    : 0;
  const elapsed = `${Math.floor(generationSeconds / 60)}:${String(generationSeconds % 60).padStart(2, '0')}`;
  async function listen() { if (!record) return; await controller.select(record, true, true); router.push('/player'); }
  function refreshHome() {
    void saved.refresh(); void profile.refresh(); void news.refresh(); void interests.refresh(); void refreshTrial(); setNow(new Date());
  }
  return <Screen contentContainerStyle={styles.content} refreshControl={<RefreshControl
    refreshing={saved.loading && Boolean(saved.data)} onRefresh={refreshHome} tintColor={c.accent} colors={[c.accent]} />}>
    <Reveal style={{ gap: 12 }}>
      <View style={styles.header}>
        <Brand />
        <View style={styles.greeting}><View style={styles.sun} accessible={false} /><Type variant="label" style={{ color: c.accent }}>မင်္ဂလာပါ။</Type></View>
      </View>
      <Type variant="muted" style={{ color: c.muted }}>{day ? `${day} · ${timezone}` : 'သင့်ဒေသစံတော်ချိန်ကို ရယူနေသည်…'}</Type>
    </Reveal>
    <Notice message={profile.error} retry={() => void profile.refresh()} />
    <Notice message={entitlement.error ? 'အသံပြင်ဆင်ခွင့်ကို စစ်ဆေးမရပါ။ ပြန်ကြိုးစားပါ။' : null} retry={() => void refreshTrial()} />
    <Reveal delay={45}><Panel tone="hero" style={styles.briefingPanel}>
      <Type variant="muted" style={{ color: c.heroText, opacity: 0.68 }}>{oldDate ? `${record.briefing_date} · ${t('နောက်ဆုံးရရှိသော အနှစ်ချုပ်')}` : 'ယနေ့ သတင်းအနှစ်ချုပ်'}</Type>
      <View style={styles.heroHeading}>
        <Reveal key={state} style={{ flex: 1, minWidth: 140 }}>
          <Type variant="title" accessibilityLiveRegion="polite" style={[styles.heroTitle, { color: c.heroText }]}>{messages[state]}</Type>
        </Reveal>
        <View style={styles.orb}><RotatingGlobe size={58} /></View>
      </View>
      {record?.duration_seconds && !categorySelectionChanged ? <Type variant="muted" style={{ color: c.heroText, opacity: 0.68 }}>နားဆင်ချိန် {clockTime(record.duration_seconds)}</Type> : null}
      {categorySelectionChanged && !generating ? <Type variant="muted" style={{ color: c.heroText, opacity: 0.78 }}>သတင်းကဏ္ဍများ ပြောင်းထားပါသည်။ အသံဟောင်းကို ရပ်ထားပြီး ရွေးချယ်မှုအသစ်အတွက် အနှစ်ချုပ် ပြင်ဆင်ရန် လိုပါသည်။</Type> : null}
      {state === 'loading' ? <Skeleton count={1} /> : null}
      <Notice message={saved.error} retry={() => void saved.refresh()} />
      {state === 'ready' ? <Button compact title="နားဆင်မယ်" onPress={listen} /> : null}
      {['pending', 'generating', 'audio-unavailable'].includes(state) ? <>
        {state === 'generating' ? <View accessibilityRole="progressbar" accessibilityLabel="အသံအနှစ်ချုပ် ပြင်ဆင်နေသည်" style={styles.generationStatus}>
          <ActivityIndicator color={c.heroText} />
          <View style={{ flex: 1 }}>
            <Type variant="label" style={{ color: c.heroText }}>{generationJob?.message || 'ပြင်ဆင်မှု စတင်နေသည်…'}</Type>
            <View style={[styles.stageTrack, { borderColor: c.heroText + '40' }]}><View style={[styles.stageFill, { backgroundColor: c.heroText, width: `${generationJob?.progress ?? 4}%` }]} /></View>
            <Type translate={false} variant="muted" style={{ color: c.heroText, opacity: 0.72 }}>{generationJob?.progress ?? 0}% · {t('ကြာချိန်')} {elapsed} · {t('အက်ပ်မှ ထွက်ထားလည်း ပြီးသွားချိန်တွင် အသိပေးပါမည်။')}</Type>
          </View>
        </View> : <Type variant="muted" style={{ color: c.heroText, opacity: 0.68 }}>{state === 'audio-unavailable' ? 'အသံလင့်ခ်ကို ပြန်ရယူပါ။ အနှစ်ချုပ်အသစ် ပြင်ဆင်ရန် မလိုပါ။' : 'ခဏအကြာတွင် အခြေအနေကို ပြန်စစ်နိုင်ပါသည်။'}</Type>}
        <Button compact secondary title="အခြေအနေ ပြန်စစ်မယ်" busy={saved.loading} onPress={() => void saved.refresh()} />
      </> : null}
      {canGenerate ? <Button compact secondary title="ယခု ကိုယ်တိုင် ပြင်ဆင်မယ်" onPress={() => void generate()} /> : null}
      <Notice message={generationError} />
      {generationErrorCode === 'no_recent_news' ? <Button secondary title="သတင်းကဏ္ဍ ပြောင်းမယ်" onPress={() => router.push('/category-preferences')} /> : null}
      {generationErrorCode === 'generation_limit_reached' && record?.status === 'ready' && record.audio_url ? <Button compact title="ပြင်ဆင်ပြီးသား အသံ နားဆင်မယ်" onPress={listen} /> : null}
    </Panel></Reveal>
    {state === 'ready' && !saved.error ? <>
      <Button secondary title="အနှစ်ချုပ်အသစ် ပြန်ပြင်ဆင်မယ်" disabled={!authorized || generating} onPress={() => setConfirmRegenerate(value => !value)} />
      {confirmRegenerate ? <Reveal><Panel><Type>ယနေ့အတွက် အသံဖိုင်အသစ် ပြင်ဆင်ပါမည်။ လက်ရှိနားဆင်နေသော အသံကို အလိုအလျောက် မပြောင်းပါ။</Type><Button title="အသစ်ပြင်ဆင်ရန် အတည်ပြုမယ်" disabled={!authorized || generating} onPress={() => { setConfirmRegenerate(false); void generate(); }} /><Button secondary title="မလုပ်တော့ပါ" onPress={() => setConfirmRegenerate(false)} /></Panel></Reveal> : null}
    </> : null}
    <SponsoredBanner />
    <Reveal delay={140} style={{ gap: 12 }}>
      <Type variant="label" style={{ color: c.ink }}>သင်ရွေးချယ်ထားသော ကဏ္ဍများ</Type>
      <Notice message={interests.error} retry={() => void interests.refresh()} />
      {interests.loading && !interests.data ? <Skeleton count={1} /> : <View style={styles.chips}>
        {interests.data?.categories.map((item, index) => <CategoryChip key={item.category_id} index={index}>{(language === 'my' ? item.categories?.name_my : item.categories?.name_en) || item.categories?.name_my || 'သတင်းကဏ္ဍ'}</CategoryChip>)}
      </View>}
    </Reveal>
    <Reveal delay={180}><Type variant="title" style={{ color: c.ink }}>နောက်ဆုံးသတင်းများ</Type></Reveal>
    <Notice message={news.error} retry={() => void news.refresh()} />
    {news.loading && !news.data ? <Skeleton count={1} /> : null}
    {news.data?.news.map((article, index) => <Reveal key={article.id} delay={index * 65}><ArticleCard article={article} compact appearance="sunrise" /></Reveal>)}
    {!news.loading && !news.error && !news.data?.news.length ? <EmptyNews refresh={() => void news.refresh()} /> : null}
    <Button secondary title="သတင်းအားလုံး ဖတ်မယ်" onPress={() => router.navigate('/news')} />
  </Screen>;
}

const makeStyles = (c: ReturnType<typeof useHomeTheme>['colors']) => StyleSheet.create({
  content: { backgroundColor: c.cream, gap: 18 },
  header: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: 16 },
  greeting: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 14, paddingVertical: 7, borderRadius: 100, borderWidth: 1, borderColor: c.border, backgroundColor: c.cream },
  sun: { width: 8, height: 8, borderRadius: 4, backgroundColor: c.accent },
  briefingPanel: { padding: 17, gap: 11, borderRadius: 22 },
  heroHeading: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  heroTitle: { fontSize: 23, lineHeight: 36 },
  orb: { padding: 2, borderRadius: 100 },
  generationStatus: { flexDirection: 'row', alignItems: 'center', gap: 14, borderTopWidth: 1, borderBottomWidth: 1, borderColor: c.heroText + '2A', paddingVertical: 14 },
  stageTrack: { height: 5, borderWidth: 1, borderRadius: 8, overflow: 'hidden', marginTop: 7 },
  stageFill: { height: '100%', borderRadius: 8 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
});
