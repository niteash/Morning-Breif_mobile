import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { Brand, Button, CircleButton, Field, Notice, Panel, Screen, Type } from '../../components/ui/primitives';
import { usePalette } from '../../features/preferences/PreferencesProvider';
import { createEmailAccount, sendEmailLink, signInEmail } from '../../lib/emailAuth';
import { signInWithGoogle } from '../../lib/googleAuth';
import { supabase } from '../../lib/supabase';

type AuthMode = 'login' | 'signup' | 'forgot';

export default function EmailLoginScreen() {
  const colors = usePalette();
  const styles = makeStyles(colors);
  const [mode, setMode] = useState<AuthMode>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  function changeMode(next: AuthMode) {
    setMode(next); setError(null); setMessage(null); setPassword(''); setConfirmPassword('');
  }

  async function handleSubmit() {
    if (loading) return;
    setLoading(true); setError(null); setMessage(null);
    try {
      if (mode === 'signup') {
        if (password !== confirmPassword) throw new Error('စကားဝှက်နှစ်ခု မတူညီပါ။');
        await createEmailAccount(supabase, email, password);
        setMessage('အကောင့်ဖွင့်ရန် အတည်ပြုအီးမေးလ် ပို့ထားပါသည်။ သင့်အီးမေးလ်ကို စစ်ဆေးပါ။');
      } else if (mode === 'login') {
        await signInEmail(supabase, email, password);
        router.replace('/home');
      } else {
        await sendEmailLink(supabase, email, true);
        setMessage('စကားဝှက်ပြန်လည်သတ်မှတ်ရန် လင့်ခ်တောင်းဆိုပြီးပါပြီ။ အီးမေးလ်ကို စစ်ဆေးပါ။');
      }
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'လုပ်ဆောင်မှု မအောင်မြင်ပါ။');
    } finally { setLoading(false); }
  }

  async function handleGoogle() {
    if (loading) return;
    setLoading(true); setError(null); setMessage(null);
    try {
      const session = await signInWithGoogle(supabase);
      if (session) router.replace('/home');
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Google အကောင့်ဖြင့် ဝင်ရောက်မရပါ။');
    } finally { setLoading(false); }
  }

  async function resendVerification() {
    if (loading) return;
    setLoading(true); setError(null); setMessage(null);
    try {
      await sendEmailLink(supabase, email, false);
      setMessage('အတည်ပြုအီးမေးလ် ပြန်လည်တောင်းဆိုပြီးပါပြီ။');
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'အီးမေးလ် ပြန်ပို့မရပါ။');
    } finally { setLoading(false); }
  }

  const title = mode === 'login' ? 'ပြန်လည်ကြိုဆိုပါတယ်။' : mode === 'signup' ? 'အကောင့်အသစ် ဖွင့်မယ်' : 'စကားဝှက် မေ့နေပါသလား?';
  const subtitle = mode === 'login' ? 'သင့်သတင်းနှင့် နားဆင်မှတ်တမ်းကို ပြန်လည်ရယူရန် အကောင့်ဝင်ပါ။' : mode === 'signup' ? 'အီးမေးလ်နှင့် စကားဝှက်ဖြင့် စတင်ပါ။' : 'ပြန်လည်သတ်မှတ်ရန် သင့်အီးမေးလ်ကို ထည့်ပါ။';

  return <Screen keyboard contentContainerStyle={styles.screen}>
    <View style={styles.header}>
      <CircleButton label="နောက်သို့" onPress={() => mode !== 'login' ? changeMode('login') : router.canGoBack() ? router.back() : router.replace('/')}>‹</CircleButton>
      <Brand />
    </View>

    <View style={styles.intro}>
      <Type variant="title">{title}</Type>
      <Type variant="muted">{subtitle}</Type>
    </View>

    <Panel style={styles.authCard}>
      {mode === 'login' ? <>
        <Button title="Google ဖြင့် ဆက်လုပ်မယ်" busy={loading} disabled={loading} onPress={() => void handleGoogle()} />
        <View style={styles.divider}><View style={styles.dividerLine} /><Type variant="muted" style={styles.dividerText}>သို့မဟုတ်</Type><View style={styles.dividerLine} /></View>
      </> : null}

      <View style={styles.fields}>
        <Field label="အီးမေးလ်" value={email} onChangeText={setEmail} editable={!loading} placeholder="you@example.com" keyboardType="email-address" autoCapitalize="none" autoComplete="email" />
        {mode !== 'forgot' ? <Field label="စကားဝှက်" value={password} onChangeText={setPassword} editable={!loading} placeholder="စကားဝှက် ထည့်ပါ" secureTextEntry autoCapitalize="none" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} /> : null}
        {mode === 'signup' ? <>
          <Field label="စကားဝှက် အတည်ပြုရန်" value={confirmPassword} onChangeText={setConfirmPassword} editable={!loading} placeholder="စကားဝှက် ထပ်ထည့်ပါ" secureTextEntry autoCapitalize="none" autoComplete="new-password" />
          <Type variant="muted">အနည်းဆုံး စာလုံး ၁၂ လုံး ပါရမည်။</Type>
        </> : null}
      </View>

      {mode === 'login' ? <TextAction title="စကားဝှက် မေ့နေပါသလား?" disabled={loading} align="right" onPress={() => changeMode('forgot')} /> : null}
      <Notice message={error} />
      {message ? <View style={styles.message}><Type variant="muted">{message}</Type></View> : null}

      <Button
        title={loading ? 'လုပ်ဆောင်နေပါသည်…' : mode === 'login' ? 'အကောင့်ဝင်မယ်' : mode === 'signup' ? 'အကောင့်ဖွင့်မယ်' : 'စကားဝှက် ပြန်လည်ရယူမယ်'}
        busy={loading}
        disabled={loading || !email.trim() || (mode !== 'forgot' && !password)}
        onPress={handleSubmit}
      />
      {mode === 'signup' && message ? <Button secondary title="အတည်ပြုအီးမေးလ် ပြန်ပို့မယ်" disabled={loading} onPress={resendVerification} /> : null}
    </Panel>

    <View style={styles.footerAction}>
      <Type variant="muted">{mode === 'login' ? 'အကောင့်မရှိသေးပါသလား?' : 'အကောင့်ရှိပြီးသားလား?'}</Type>
      <TextAction title={mode === 'login' ? 'အကောင့်ဖွင့်မယ်' : 'အကောင့်ဝင်ရန် ပြန်သွားမယ်'} disabled={loading} onPress={() => changeMode(mode === 'login' ? 'signup' : 'login')} />
    </View>
  </Screen>;
}

function TextAction({ title, onPress, disabled, align = 'center' }: { title: string; onPress: () => void; disabled?: boolean; align?: 'center' | 'right' }) {
  const colors = usePalette();
  return <Pressable accessibilityRole="button" accessibilityLabel={title} accessibilityState={{ disabled }} disabled={disabled} onPress={onPress} style={({ pressed }) => [actionStyles.root, align === 'right' && actionStyles.right, { opacity: disabled ? 0.4 : pressed ? 0.6 : 1 }]}>
    <Type variant="label" style={{ color: colors.text, textDecorationLine: 'underline' }}>{title}</Type>
  </Pressable>;
}

const actionStyles = StyleSheet.create({
  root: { minHeight: 44, alignSelf: 'center', justifyContent: 'center' },
  right: { alignSelf: 'flex-end' },
});

const makeStyles = (colors: ReturnType<typeof usePalette>) => StyleSheet.create({
  screen: { gap: 18, justifyContent: 'center', paddingTop: 18 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  intro: { gap: 3, paddingTop: 2 },
  authCard: { padding: 18, borderRadius: 24, gap: 14 },
  fields: { gap: 12 },
  divider: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  dividerLine: { flex: 1, height: StyleSheet.hairlineWidth, backgroundColor: colors.border },
  dividerText: { fontSize: 13, lineHeight: 22 },
  message: { padding: 12, borderRadius: 14, backgroundColor: colors.background, borderWidth: 1, borderColor: colors.border },
  footerAction: { minHeight: 44, flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'center', gap: 6 },
});
