import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
import { useBriefing } from '../features/playback/PlaybackProvider';
import { activeStory, clockTime, storyChapters } from '../lib/playback';
import { CircleButton, Notice, Type } from './ui/primitives';
import { usePalette, useCopy } from '../features/preferences/PreferencesProvider';

export function MiniPlayer() {
  const colors = usePalette(), t = useCopy();
  const { playback, controller } = useBriefing();
  if (!playback.record) return null;
  return <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 16, paddingVertical: 12, borderTopWidth: 1, borderColor: colors.border, backgroundColor: colors.surface }}>
    <Pressable accessibilityRole="button" accessibilityLabel={t('အသံဖွင့်စက်ကို ဖွင့်မယ်')} onPress={() => router.push('/player')} style={{ flex: 1, minHeight: 52, justifyContent: 'center' }}>
      <Type variant="label">နေ့သစ် · {playback.record.briefing_date}</Type>
      <Type variant="muted">{playback.loading || playback.refreshing ? 'အသံ ပြင်ဆင်နေသည်…' : `${clockTime(playback.position)} / ${clockTime(playback.duration)}`}{playback.error ? ' · ပြန်စစ်ရန်' : ''}</Type>
    </Pressable>
    <CircleButton dark label={playback.intentPlaying ? 'ခေတ္တရပ်မယ်' : 'နားဆင်မယ်'} onPress={() => playback.intentPlaying ? controller.pause() : void controller.play()}>{playback.intentPlaying ? 'Ⅱ' : '▶'}</CircleButton>
  </View>;
}
export function PlaybackControls() {
  const colors = usePalette(), t = useCopy();
  const { playback: p, controller, sleepTimerEndsAt, setSleepTimer } = useBriefing();
  const [trackWidth, setTrackWidth] = useState(1);
  const [dragPosition, setDragPosition] = useState<number | null>(null);
  const [speedOptions, setSpeedOptions] = useState(false);
  const [sleepOptions, setSleepOptions] = useState(false);
  const displayPosition = dragPosition ?? p.position;
  const progress = p.duration ? Math.min(1, displayPosition / p.duration) : 0;
  const canSeek = p.duration > 0 && !p.loading;
  const stories = storyChapters(p.record);
  const active = activeStory(p.record, p.position);
  const activeIndex = active ? stories.findIndex(item => item.id === active.id) : -1;
  const positionAt = (x: number) => Math.max(0, Math.min(1, x / trackWidth)) * p.duration;
  return <View style={styles.root}>
    <View accessible accessibilityRole="adjustable" accessibilityLabel={t('နားဆင်သည့်နေရာ')} accessibilityState={{ disabled: !canSeek }} accessibilityValue={{ min: 0, max: Math.round(p.duration), now: Math.round(displayPosition), text: `${clockTime(displayPosition)} / ${clockTime(p.duration)}` }} accessibilityActions={[{ name: 'increment', label: t('ရှေ့ ၁၅ စက္ကန့်') }, { name: 'decrement', label: t('နောက် ၁၅ စက္ကန့်') }]} onAccessibilityAction={event => { if (canSeek) void controller.seek(p.position + (event.nativeEvent.actionName === 'increment' ? 15 : -15)); }} onLayout={event => setTrackWidth(event.nativeEvent.layout.width)} onStartShouldSetResponder={() => canSeek} onMoveShouldSetResponder={() => canSeek} onResponderGrant={event => setDragPosition(positionAt(event.nativeEvent.locationX))} onResponderMove={event => setDragPosition(positionAt(event.nativeEvent.locationX))} onResponderTerminationRequest={() => false} onResponderTerminate={() => setDragPosition(null)} onResponderRelease={event => { if (canSeek) void controller.seek(positionAt(event.nativeEvent.locationX)); setDragPosition(null); }} style={{ minHeight: 48, justifyContent: 'center' }}>
      <View pointerEvents="none" style={{ height: 5, borderRadius: 5, backgroundColor: colors.border }}><View style={{ width: `${progress * 100}%`, height: 5, backgroundColor: colors.text, borderRadius: 5 }} /></View>
      <View pointerEvents="none" style={{ position: 'absolute', left: progress * Math.max(0, trackWidth - 14), width: 14, height: 14, borderRadius: 7, backgroundColor: colors.text }} />
    </View>
    <View style={styles.timeRow}><Type variant="muted">{clockTime(displayPosition)}</Type><Type variant="muted">{clockTime(p.duration)}</Type></View>
    {p.buffering || p.loading || p.refreshing ? <Type variant="muted" accessibilityLiveRegion="polite">အသံ ပြင်ဆင်နေသည်…</Type> : null}
    {active ? <Type variant="muted" numberOfLines={2}>{active.category_name} · {active.title}</Type> : null}
    <View style={styles.transport}>
      <CircleButton label="ယခင်သတင်း" disabled={activeIndex <= 0} onPress={() => void controller.seek(stories[activeIndex - 1]?.start_seconds ?? 0)}>‹</CircleButton>
      <CircleButton label="နောက် ၁၅ စက္ကန့်" disabled={!canSeek} onPress={() => void controller.seek(p.position - 15)}>−15</CircleButton>
      <CircleButton dark label={p.intentPlaying ? 'ခေတ္တရပ်မယ်' : 'နားဆင်မယ်'} onPress={() => p.intentPlaying ? controller.pause() : void controller.play()}>{p.intentPlaying ? 'Ⅱ' : '▶'}</CircleButton>
      <CircleButton label="နောက်သတင်း" disabled={activeIndex < 0 || activeIndex >= stories.length - 1} onPress={() => void controller.seek(stories[activeIndex + 1]?.start_seconds ?? p.position)}>›</CircleButton>
    </View>
    <View style={[styles.tools, { borderTopColor: colors.border }]}>
      <ControlIcon icon={`${p.rate}×`} label={t('နားဆင်နှုန်း')} selected={speedOptions} onPress={() => { setSpeedOptions(value => !value); setSleepOptions(false); }} />
      <ControlIcon icon="◷" label={t('အိပ်ချိန် အလိုအလျောက်ရပ်ရန်')} selected={sleepOptions || Boolean(sleepTimerEndsAt)} onPress={() => { setSleepOptions(value => !value); setSpeedOptions(false); }} />
      {!p.record?.offline ? <ControlIcon icon="↻" label={t('အသံလင့်ခ် ပြန်ရယူမယ်')} busy={p.refreshing} disabled={p.loading} onPress={() => void controller.refresh()} /> : null}
    </View>
    {speedOptions ? <View style={styles.optionRow} accessibilityLabel={t('နားဆင်နှုန်း')}>
      {[0.75, 1, 1.25, 1.5, 2].map(rate => <Pressable key={rate} accessibilityRole="radio" accessibilityState={{ checked: rate === p.rate }} accessibilityLabel={`${rate}× ${t('နားဆင်နှုန်း')}`} onPress={() => controller.setRate(rate)} style={{ minWidth: 52, minHeight: 48, borderRadius: 24, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 12, backgroundColor: p.rate === rate ? colors.text : colors.background }}><Type style={{ color: p.rate === rate ? colors.surface : colors.text }}>{rate}×</Type></Pressable>)}
    </View> : null}
    {sleepOptions ? <View style={styles.optionRow} accessibilityLabel={t('အိပ်ချိန် အလိုအလျောက်ရပ်ရန်')}>
      {[15, 30, 45].map(minutes => <Pressable key={minutes} accessibilityRole="button" onPress={() => setSleepTimer(minutes)} style={{ minHeight: 48, minWidth: 64, borderRadius: 24, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background }}><Type>{minutes} မိနစ်</Type></Pressable>)}
      {sleepTimerEndsAt ? <Pressable accessibilityRole="button" onPress={() => setSleepTimer(null)} style={{ minHeight: 48, minWidth: 64, borderRadius: 24, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.text }}><Type style={{ color: colors.surface }}>ပိတ်မယ်</Type></Pressable> : null}
    </View> : null}
    {sleepTimerEndsAt ? <Type variant="muted" accessibilityLiveRegion="polite">အိပ်ချိန် အလိုအလျောက်ရပ်မှု ဖွင့်ထားပါသည်။</Type> : null}
    <Notice message={p.error} />
  </View>;
}

function ControlIcon({ icon, label, onPress, selected = false, busy = false, disabled = false }: { icon: string; label: string; onPress: () => void; selected?: boolean; busy?: boolean; disabled?: boolean }) {
  const colors = usePalette();
  return <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ selected, busy, disabled: disabled || busy }} disabled={disabled || busy} onPress={onPress} style={({ pressed }) => [styles.toolButton, { borderColor: colors.border, backgroundColor: selected ? colors.text : colors.background }, pressed && { opacity: 0.62 }, (disabled || busy) && { opacity: 0.42 }]}>
    <Type translate={false} style={{ color: selected ? colors.surface : colors.text, fontSize: icon.length > 2 ? 14 : 21, lineHeight: 24 }}>{busy ? '…' : icon}</Type>
  </Pressable>;
}

const styles = StyleSheet.create({
  root: { gap: 18, paddingHorizontal: 2, paddingTop: 4, paddingBottom: 2 },
  timeRow: { marginTop: -8, paddingHorizontal: 2, flexDirection: 'row', justifyContent: 'space-between' },
  transport: { minHeight: 72, paddingVertical: 8, paddingHorizontal: 2, flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-evenly', gap: 10 },
  tools: { paddingTop: 12, borderTopWidth: StyleSheet.hairlineWidth, flexDirection: 'row', justifyContent: 'center', gap: 10 },
  toolButton: { width: 46, height: 46, borderRadius: 16, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  optionRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 9, paddingBottom: 2 },
});
