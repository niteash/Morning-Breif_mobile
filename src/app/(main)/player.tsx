import { BriefingSources } from '../../components/BriefingSources';
import { useOfflineAudio } from '../../hooks/useOfflineAudio';
import { AudioProgressVisual } from '../../components/AudioProgressVisual';
import { useEffect, useRef, useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { useBriefing } from '../../features/playback/PlaybackProvider';
import { useAccountId } from '../../components/AuthGate';
import { getHistoricalBriefing, reportPronunciation } from '../../services/briefingApi';
import { Screen, Panel, Type, Button, CircleButton, Notice, Field } from '../../components/ui/primitives';
import { PlaybackControls } from '../../components/PlaybackControls';
import { SunriseOrb } from '../../components/ui/SunriseMotion';
import { ActivityIndicator, Linking, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { useCopy, usePalette } from '../../features/preferences/PreferencesProvider';
export default function PlayerScreen() {
  const offline = useOfflineAudio();
  const { playback, controller, profile } = useBriefing();
  const colors = usePalette();
  const t = useCopy();
  const styles = makeStyles(colors);
  const owner = useAccountId();
  const { briefingId: rawBriefingId } = useLocalSearchParams<{ briefingId?: string | string[] }>();
  const briefingId = Array.isArray(rawBriefingId) ? rawBriefingId[0] : rawBriefingId;
  const [transcript, setTranscript] = useState(false);
  const [notificationError, setNotificationError] = useState<string | null>(null);
  const [showReport, setShowReport] = useState(false);
  const [reportPhrase, setReportPhrase] = useState('');
  const [reportNotes, setReportNotes] = useState('');
  const [reportBusy, setReportBusy] = useState(false);
  const [reportMessage, setReportMessage] = useState<string | null>(null);
  const handledBriefing = useRef<string | null>(null);
  const downloaded = Boolean(playback.record && (playback.record.offline || offline.downloads.data?.some(item => item.id === playback.record?.id)));
  useEffect(() => {
    if (!briefingId || !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(briefingId) || handledBriefing.current === briefingId) return;
    handledBriefing.current = briefingId;
    let active = true;
    setNotificationError(null);
    void getHistoricalBriefing(briefingId).then(({ briefing }) => {
      if (!active) return;
      if (briefing.user_id !== owner || briefing.status !== 'ready' || !briefing.audio_url) throw new Error('Unavailable');
      return controller.select(briefing, true, true);
    }).catch(() => {
      if (active) setNotificationError('ဤအနှစ်ချုပ်ကို ဖွင့်မရပါ။ ပင်မစာမျက်နှာမှ ပြန်စစ်ပါ။');
    });
    return () => { active = false; };
  }, [briefingId, controller, owner]);
  return <Screen contentContainerStyle={styles.screen}>
    <CircleButton label="နောက်သို့" onPress={() => router.canGoBack() ? router.back() : router.replace('/home')}>‹</CircleButton>
    <Notice message={notificationError} />
    {playback.record ? <>
      <View style={styles.nowPlaying}>
        <View style={styles.globeStage}><SunriseOrb size={108} active={playback.intentPlaying} /></View>
        <View style={styles.playerCopy}>
          <View style={styles.statusRow}><View style={[styles.statusDot, playback.intentPlaying && styles.statusDotActive]} /><Type translate={false} variant="muted" style={styles.statusLabel}>{playback.intentPlaying ? 'NOW PLAYING' : 'READY TO PLAY'}</Type></View>
          <Type variant="muted" style={styles.playerMeta}>{playback.record.briefing_date} · မြန်မာဘာသာ</Type>
          <Type variant="title" translate={false} numberOfLines={2} style={styles.playerTitle}>{playback.record.source_metadata?.title || 'နေ့သစ် သတင်းအနှစ်ချုပ်'}</Type>
        </View>
      </View>
      <AudioProgressVisual position={playback.position} duration={playback.duration} />
      <Panel style={styles.controls}><PlaybackControls /></Panel>
      {playback.record.chapters?.length ? <Panel>
        <Type variant="label">သတင်း အခန်းများ</Type>
        {playback.record.chapters.filter(chapter => chapter.type === 'story').map(chapter => <View key={chapter.id} style={styles.chapterRow}>
          <Pressable accessibilityRole="button" onPress={() => void controller.seek(chapter.start_seconds)} style={{ flex: 1, minHeight: 48, justifyContent: 'center' }}>
            <Type translate={false} variant="label" numberOfLines={2}>{chapter.title}</Type>
            <Type variant="muted">{chapter.category_name} · {Math.floor(chapter.start_seconds / 60)}:{String(chapter.start_seconds % 60).padStart(2, '0')}</Type>
          </Pressable>
          {chapter.url ? <CircleButton label="မူရင်းသတင်း ဖတ်မယ်" onPress={() => void Linking.openURL(chapter.url!)}>↗</CircleButton> : null}
        </View>)}
      </Panel> : null}
      <View style={styles.libraryActions}>
        {offline.supported ? <PlayerIconAction
          icon={downloaded ? '✓' : '↓'}
          label={t(downloaded ? 'အသံ သိမ်းပြီးပါပြီ။' : 'အင်တာနက်မရှိဘဲ နားဆင်ရန် သိမ်းမယ်')}
          selected={downloaded}
          busy={offline.busy}
          disabled={downloaded}
          onPress={() => void offline.save(playback.record!)}
        /> : null}
        <PlayerIconAction icon="▤" label={t('သိမ်းထားသော အသံများ')} onPress={() => router.push('/downloads')} />
        <PlayerIconAction icon="≡" label={t(transcript ? 'စာသားကို ပိတ်မယ်' : 'အနှစ်ချုပ် စာသားဖတ်မယ်')} selected={transcript} onPress={() => setTranscript(value => !value)} />
        <PlayerIconAction icon="◌" label={t(showReport ? 'အသံထွက် တင်ပြချက် ပိတ်မယ်' : 'အသံထွက် မမှန်တာ တင်ပြမယ်')} selected={showReport} onPress={() => { setShowReport(value => !value); setReportMessage(null); }} />
      </View>
      <Notice message={offline.error} />
      {playback.record.offline ? <Type variant="muted">သိမ်းထားသော အသံကို နားဆင်နေသည်။</Type> : null}
      {transcript ? <Panel><Type variant="label">AI ဖြင့် ရေးသားထားသော အနှစ်ချုပ်</Type><ScrollView nestedScrollEnabled persistentScrollbar showsVerticalScrollIndicator style={styles.transcript} contentContainerStyle={{ paddingRight: 8 }}>{playback.record.script ? <Type translate={false} selectable>{playback.record.script}</Type> : <Type>စာသား မရရှိပါ။</Type>}</ScrollView></Panel> : null}
      {showReport ? <Panel>
        <Type variant="label">အသံထွက် ပြင်ဆင်ရန် တင်ပြပါ</Type>
        <Type variant="muted">မမှန်သည့် စကားလုံး သို့မဟုတ် အမည်ကိုသာ ထည့်ပါ။ သုံးသပ်ပြီး မြန်မာအသံထွက်စာရင်းတွင် ပြင်ဆင်ပါမည်။</Type>
        <Field label="စကားလုံး / အမည်" value={reportPhrase} onChangeText={setReportPhrase} maxLength={160} editable={!reportBusy} />
        <Field label="မှတ်ချက် (မလိုအပ်ပါ)" value={reportNotes} onChangeText={setReportNotes} maxLength={500} editable={!reportBusy} multiline />
        <Button title="တင်ပြမယ်" busy={reportBusy} disabled={!reportPhrase.trim()} onPress={() => {
          if (!playback.record || reportBusy) return;
          setReportBusy(true); setReportMessage(null);
          void reportPronunciation(playback.record.id, reportPhrase.trim(), reportNotes).then(() => {
            setReportPhrase(''); setReportNotes(''); setReportMessage('တင်ပြချက် လက်ခံပြီးပါပြီ။');
          }).catch(error => setReportMessage(error instanceof Error ? error.message : 'တင်ပြမရပါ။')).finally(() => setReportBusy(false));
        }} />
        {reportMessage ? <Type accessibilityLiveRegion="polite">{reportMessage}</Type> : null}
      </Panel> : null}
      <BriefingSources metadata={playback.record.source_metadata} dataSaver={profile.data?.data_saver_enabled === true} />
    </> : <Panel><Type>နားဆင်ရန် အနှစ်ချုပ်တစ်ခု ရွေးချယ်ပါ။</Type><Button title="ပင်မသို့" onPress={() => router.replace('/home')} /></Panel>}
  </Screen>;
}

function PlayerIconAction({ icon, label, onPress, selected = false, busy = false, disabled = false }: { icon: string; label: string; onPress: () => void; selected?: boolean; busy?: boolean; disabled?: boolean }) {
  const colors = usePalette();
  return <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ selected, busy, disabled: disabled || busy }} disabled={disabled || busy} onPress={onPress} style={({ pressed }) => [stylesForAction.button, { borderColor: colors.border, backgroundColor: selected ? colors.text : colors.surface }, pressed && stylesForAction.pressed, (disabled || busy) && !selected && stylesForAction.disabled]}>
    {busy ? <ActivityIndicator color={colors.text} /> : <Type translate={false} style={{ color: selected ? colors.surface : colors.text, fontSize: 23, lineHeight: 27 }}>{icon}</Type>}
  </Pressable>;
}

const stylesForAction = StyleSheet.create({
  button: { width: 50, height: 50, borderRadius: 18, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  pressed: { opacity: 0.62 },
  disabled: { opacity: 0.45 },
});

const makeStyles = (colors: ReturnType<typeof usePalette>) => StyleSheet.create({
  screen: { gap: 18 },
  nowPlaying: { width: '100%', minHeight: 148, overflow: 'hidden', flexDirection: 'row', alignItems: 'center', gap: 14, padding: 16, borderRadius: 24, backgroundColor: '#000000', borderWidth: 1, borderColor: '#202020' },
  playerCopy: { flex: 1, minWidth: 0, gap: 5 },
  statusRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  statusDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: '#5F5F5F' },
  statusDotActive: { backgroundColor: '#FFFFFF' },
  statusLabel: { color: '#B8B8B8', fontSize: 11, lineHeight: 18, letterSpacing: 2.2 },
  globeStage: { width: 112, height: 112, alignItems: 'center', justifyContent: 'center' },
  playerMeta: { color: '#AFAFAF', fontSize: 12, lineHeight: 20, letterSpacing: 0.5 },
  playerTitle: { color: '#FFFFFF', fontSize: 20, lineHeight: 31 },
  controls: { borderRadius: 28, borderColor: colors.border, backgroundColor: colors.surface, paddingHorizontal: 20, paddingVertical: 22, marginTop: 4, marginBottom: 2 },
  libraryActions: { minHeight: 50, flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'flex-end', gap: 10, paddingHorizontal: 2, marginTop: 2 },
  chapterRow: { flexDirection: 'row', alignItems: 'center', gap: 10, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border, paddingTop: 9 },
  transcript: { maxHeight: 320 },
});
