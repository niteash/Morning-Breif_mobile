import { useEffect, useMemo, useState } from 'react';
import { router } from 'expo-router';
import { StyleSheet, View } from 'react-native';
import { MotionPressable } from '../../components/ui/Motion';
import { Button, CircleButton, Loading, Notice, Panel, Screen, Type } from '../../components/ui/primitives';
import { MiniPlayer } from '../../components/PlaybackControls';
import { getCategories } from '../../services/categoryApi';
import { getMyCategories, updateMyCategories } from '../../services/userApi';
import { useBriefing } from '../../features/playback/PlaybackProvider';
import { usePalette, usePreferences } from '../../features/preferences/PreferencesProvider';

type Category = { id: string; slug: string; name_en: string; name_my: string; active: boolean };

export default function CategoryPreferencesScreen() {
  const colors = usePalette(), { language } = usePreferences();
  const { generating, playback, controller, markCategorySelectionChanged, generate } = useBriefing();
  const styles = makeStyles(colors);
  const [categories, setCategories] = useState<Category[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [original, setOriginal] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const playbackActive = playback.playing || playback.intentPlaying;
  const locked = saving || generating || playbackActive;

  const dirty = useMemo(() => [...selected].sort().join(',') !== [...original].sort().join(','), [original, selected]);

  async function load() {
    setLoading(true); setError(null);
    try {
      const [available, saved] = await Promise.all([getCategories(), getMyCategories()]);
      const active = available.categories.filter(item => item.active);
      const ids = saved.categories.map(item => item.category_id).filter(id => active.some(item => item.id === id));
      setCategories(active); setSelected(ids); setOriginal(ids);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'သတင်းကဏ္ဍများကို ရယူမရပါ။ ပြန်ကြိုးစားပါ။');
    } finally { setLoading(false); }
  }

  useEffect(() => {
    // Begin the initial request; loading already represents this state.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, []);

  function leave() {
    if (dirty && !confirmDiscard) { setConfirmDiscard(true); return; }
    if (router.canGoBack()) router.back(); else router.replace('/settings');
  }

  function toggle(id: string) {
    if (locked) return;
    setConfirmDiscard(false);
    setSelected(current => current.includes(id) ? current.filter(value => value !== id) : [...current, id]);
  }

  async function save() {
    if (!dirty || !selected.length || locked) return;
    setSaving(true); setError(null);
    try {
      await updateMyCategories(selected);
      controller.clear();
      await markCategorySelectionChanged();
      setOriginal(selected);
      router.replace('/home');
      void generate();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'သတင်းကဏ္ဍများ သိမ်းမရပါ။ ပြန်ကြိုးစားပါ။');
    } finally { setSaving(false); }
  }

  return <Screen contentContainerStyle={styles.screen}>
    <CircleButton label="နောက်သို့" disabled={saving} onPress={leave}>‹</CircleButton>
    <View style={styles.heading}>
      <Type variant="title">သတင်းကဏ္ဍများ</Type>
      <Type variant="muted">အသံကို ခေတ္တရပ်ပြီးမှ သတင်းကဏ္ဍများ ပြောင်းနိုင်ပါသည်။ ရွေးချယ်မှုအသစ်ကို နောက်တစ်ကြိမ်ပြင်ဆင်သည့် အနှစ်ချုပ်တွင် အသုံးပြုပါမည်။</Type>
    </View>
    <MiniPlayer />
    {playbackActive ? <Panel><Type variant="label">အသံကို ခေတ္တရပ်ပါ</Type><Type variant="muted">နားဆင်နေစဉ် ကဏ္ဍရွေးချယ်မှုကို မပြောင်းနိုင်ပါ။ အပေါ်ရှိ အသံဖွင့်စက်တွင် ခေတ္တရပ်ပြီး ဆက်လုပ်ပါ။</Type></Panel> : null}
    {generating ? <Panel><Type variant="label">အနှစ်ချုပ် ပြင်ဆင်နေသည်</Type><Type variant="muted">အခု ပြင်ဆင်နေသော အနှစ်ချုပ်ပြီးမှ ကဏ္ဍပြောင်းနိုင်ပါမည်။ လက်ရှိရွေးချယ်မှုနှင့် အသံကို တစ်သမတ်တည်းထားရန် ဖြစ်ပါသည်။</Type></Panel> : null}
    {loading ? <Loading label="သတင်းကဏ္ဍများကို ရယူနေသည်…" /> : null}
    <Notice message={error} retry={() => void load()} />
    {confirmDiscard ? <Panel><Type>မသိမ်းရသေးသော ပြောင်းလဲမှုများကို ပယ်ဖျက်မလား?</Type><Button title="မသိမ်းဘဲ ပြန်မယ်" onPress={leave} /><Button secondary title="ဆက်ပြင်မယ်" onPress={() => setConfirmDiscard(false)} /></Panel> : null}
    <View style={styles.list}>
      {categories.map(category => {
        const checked = selected.includes(category.id);
        return <MotionPressable key={category.id} accessibilityRole="checkbox" accessibilityState={{ checked, disabled: locked }} disabled={locked} onPress={() => toggle(category.id)} style={({ pressed }) => [styles.row, checked && styles.selectedRow, locked && styles.locked, pressed && styles.pressed]}>
          <View style={{ flex: 1 }}><Type variant="label">{language === 'my' ? category.name_my : category.name_en}</Type><Type variant="muted">{language === 'my' ? category.name_en : category.name_my}</Type></View>
          <View style={[styles.check, checked && styles.checked]}><Type translate={false} style={{ color: checked ? colors.surface : colors.text }}>{checked ? '✓' : ''}</Type></View>
        </MotionPressable>;
      })}
    </View>
    {!loading && !categories.length && !error ? <Type variant="muted">ရွေးချယ်ရန် သတင်းကဏ္ဍ မရှိသေးပါ။</Type> : null}
    {!selected.length ? <Notice message="အနည်းဆုံး သတင်းကဏ္ဍတစ်ခု ရွေးချယ်ပါ။" /> : null}
    <Button title="ရွေးချယ်မှု သိမ်းမယ်" busy={saving} disabled={!dirty || !selected.length || loading || generating || playbackActive || Boolean(error)} onPress={() => void save()} />
  </Screen>;
}

const makeStyles = (colors: ReturnType<typeof usePalette>) => StyleSheet.create({
  screen: { gap: 20 }, heading: { gap: 5 }, list: { gap: 10 },
  row: { minHeight: 78, paddingHorizontal: 18, paddingVertical: 13, borderRadius: 20, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surface, flexDirection: 'row', alignItems: 'center', gap: 14 },
  selectedRow: { borderWidth: 2, borderColor: colors.text }, pressed: { opacity: 0.72 },
  locked: { opacity: 0.46 },
  check: { width: 30, height: 30, borderRadius: 15, borderWidth: 1, borderColor: colors.text, alignItems: 'center', justifyContent: 'center' },
  checked: { backgroundColor: colors.text },
});
