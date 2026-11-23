import { router } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { supabase } from '../lib/supabase';
import { Button, Notice, Screen, Type } from '../components/ui/primitives';
import { Reveal } from '../components/ui/Motion';
import { RotatingGlobe } from '../components/ui/RotatingGlobe';
import { usePalette } from '../features/preferences/PreferencesProvider';
export default function Welcome() {
  const colors = usePalette();
  const styles = makeStyles(colors);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function start() {
    if (loading) return;
    setLoading(true); setError(null);
    try {
      const { data: { session }, error: failure } = await supabase.auth.getSession();
      if (failure) throw failure;
      router.push(session && !session.user.is_anonymous ? '/home' : '/sign-in');
    } catch { setError('အကောင့်ကို စစ်ဆေးမရပါ။ ပြန်ကြိုးစားပါ။'); }
    finally { setLoading(false); }
  }
  return <Screen contentContainerStyle={styles.screen}>
    <View style={styles.cornerMark}><View style={styles.cornerDot} /><Type translate={false} variant="muted" style={styles.cornerText}>01 / MORNING</Type></View>
    <View style={styles.identity}>
      <Reveal><RotatingGlobe size={232} /></Reveal>
      <Reveal delay={90} style={styles.wordmark}>
        <Type variant="title" style={styles.burmeseName}>နေ့သစ်</Type>
      </Reveal>
      <Reveal delay={170}>
        <Type translate={false} variant="muted" style={styles.tagline}>YOUR PERSONAL NEWS APP</Type>
      </Reveal>
    </View>
    <Reveal delay={220} style={styles.action}>
      <Notice message={error} />
      <Button title="စတင်မယ်" busy={loading} onPress={start} />
      <Type variant="muted" style={styles.caption}>နောက်ဆုံးသတင်းများကို မြန်မာဘာသာဖြင့် နားဆင်ပါ</Type>
    </Reveal>
  </Screen>;
}

const makeStyles = (colors: ReturnType<typeof usePalette>) => StyleSheet.create({
  screen: { justifyContent: 'space-between', gap: 28, paddingTop: 18 },
  cornerMark: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  cornerDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: colors.text },
  cornerText: { fontSize: 11, letterSpacing: 2.4, color: colors.secondary },
  identity: { alignItems: 'center', gap: 12 },
  wordmark: { alignItems: 'center', marginTop: 8 },
  burmeseName: { color: colors.text, fontSize: 34, lineHeight: 48, textAlign: 'center' },
  tagline: { color: colors.secondary, fontSize: 11, lineHeight: 18, letterSpacing: 3.2, textAlign: 'center' },
  action: { gap: 14 },
  caption: { textAlign: 'center', fontSize: 13 },
});
