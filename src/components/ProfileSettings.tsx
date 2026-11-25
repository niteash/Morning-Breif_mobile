import { useEffect, useState } from 'react';
import { Image, StyleSheet, View } from 'react-native';
import type { Preferences } from '../lib/onboarding';
import { supabase } from '../lib/supabase';
import { useAccountId } from './AuthGate';
import { updateMyProfile } from '../services/userApi';
import { removeProfileImage, signedProfileImage, uploadProfileImage } from '../services/profileImage';
import { Button, Field, Notice, Panel, Type } from './ui/primitives';
import { usePalette } from '../features/preferences/PreferencesProvider';

export function ProfileSettings({ profile, refresh }: { profile: Preferences; refresh(): Promise<unknown> }) {
  const owner = useAccountId();
  const colors = usePalette();
  const [name, setName] = useState(profile.name ?? '');
  const [phone, setPhone] = useState(profile.phone_number ?? '');
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [fallbackAvatar, setFallbackAvatar] = useState<string | null>(null);
  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void supabase.auth.getUser().then(({ data }) => {
      if (!active || data.user?.id !== owner) return;
      setEmail(data.user.email ?? '');
      const candidate = data.user.user_metadata?.avatar_url;
      setFallbackAvatar(typeof candidate === 'string' && /^https:\/\/[^\s]+$/i.test(candidate) ? candidate : null);
    });
    return () => { active = false; };
  }, [owner]);

  useEffect(() => {
    let active = true;
    if (!profile.avatar_path) return () => { active = false; };
    void signedProfileImage(profile.avatar_path).then(url => { if (active) setAvatarUrl(url); })
      .catch(() => { if (active) setError('ပရိုဖိုင်ပုံကို ဖွင့်မရပါ။'); });
    return () => { active = false; };
  }, [profile.avatar_path]);

  function normalizedPhone() {
    const value = phone.trim().replace(/[\s()-]/g, '');
    if (!value) return null;
    if (!/^\+[1-9][0-9]{6,14}$/.test(value)) throw new Error('ဖုန်းနံပါတ်ကို နိုင်ငံကုဒ်ဖြင့် ထည့်ပါ။ ဥပမာ +959123456789');
    return value;
  }

  async function saveDetails() {
    if (busy) return;
    setBusy(true); setError(null); setMessage(null);
    try {
      await updateMyProfile({ name: name.trim() || null, phone_number: normalizedPhone() });
      await refresh();
      setMessage('ပရိုဖိုင်ကို သိမ်းပြီးပါပြီ။');
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'ပရိုဖိုင်ကို သိမ်းမရပါ။');
    } finally { setBusy(false); }
  }

  async function chooseAvatar() {
    if (busy) return;
    setBusy(true); setError(null); setMessage(null);
    let uploaded: string | null = null;
    try {
      // Keep Settings usable in an older installed development build. The
      // native picker becomes available after rebuilding the app binary.
      let ImagePicker: typeof import('expo-image-picker');
      try {
        ImagePicker = await import('expo-image-picker');
      } catch {
        throw new Error('ပရိုဖိုင်ပုံရွေးရန် အက်ပ်ဗားရှင်းအသစ်ကို ထည့်သွင်းပါ။');
      }
      const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], allowsEditing: true, aspect: [1, 1], quality: 0.82 });
      if (result.canceled) return;
      const asset = result.assets[0];
      if (asset.fileSize && asset.fileSize > 5 * 1024 * 1024) throw new Error('ပရိုဖိုင်ပုံသည် 5 MB အောက် ဖြစ်ရပါမည်။');
      uploaded = await uploadProfileImage(owner, asset.uri, asset.mimeType);
      const previous = profile.avatar_path;
      await updateMyProfile({ avatar_path: uploaded });
      await refresh();
      setAvatarUrl(await signedProfileImage(uploaded));
      if (previous) await removeProfileImage(previous).catch(() => {});
      setMessage('ပရိုဖိုင်ပုံကို ပြောင်းပြီးပါပြီ။');
    } catch (failure) {
      if (uploaded) await removeProfileImage(uploaded).catch(() => {});
      setError(failure instanceof Error ? failure.message : 'ပရိုဖိုင်ပုံကို ပြောင်းမရပါ။');
    } finally { setBusy(false); }
  }

  async function clearAvatar() {
    if (busy || !profile.avatar_path) return;
    setBusy(true); setError(null); setMessage(null);
    const previous = profile.avatar_path;
    try {
      await updateMyProfile({ avatar_path: null });
      await refresh();
      setAvatarUrl(null);
      await removeProfileImage(previous).catch(() => {});
      setMessage('စိတ်ကြိုက်ပရိုဖိုင်ပုံကို ဖယ်ရှားပြီးပါပြီ။');
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'ပရိုဖိုင်ပုံကို ဖယ်ရှားမရပါ။');
    } finally { setBusy(false); }
  }

  const displayAvatar = (profile.avatar_path ? avatarUrl : null) || fallbackAvatar;
  const initial = (name.trim() || email || 'N').slice(0, 1).toUpperCase();
  return <Panel style={styles.panel}>
    <View style={styles.identity}>
      {displayAvatar ? <Image accessibilityIgnoresInvertColors source={{ uri: displayAvatar }} style={[styles.avatar, { backgroundColor: colors.background }]} />
        : <View style={[styles.avatar, styles.initial, { backgroundColor: colors.text }]}><Type translate={false} style={[styles.initialText, { color: colors.background }]}>{initial}</Type></View>}
      <View style={styles.identityCopy}>
        <Type variant="label" translate={false}>{name.trim() || 'Your profile'}</Type>
        <Type variant="muted" translate={false} numberOfLines={1}>{email}</Type>
      </View>
    </View>
    <View style={styles.photoActions}>
      <View style={styles.action}><Button secondary title="ပုံရွေးမယ်" disabled={busy} onPress={() => void chooseAvatar()} /></View>
      {profile.avatar_path ? <View style={styles.action}><Button secondary title="ပုံဖယ်မယ်" disabled={busy} onPress={() => void clearAvatar()} /></View> : null}
    </View>
    <Field label="အမည်" value={name} onChangeText={setName} editable={!busy} maxLength={80} autoCapitalize="words" />
    <Field label="မိုဘိုင်းနံပါတ် (မဖြစ်မနေ မဟုတ်ပါ)" value={phone} onChangeText={setPhone} editable={!busy} keyboardType="phone-pad" placeholder="+959123456789" maxLength={16} />
    <Type variant="muted">မိုဘိုင်းနံပါတ်ကို အကောင့်ဝင်ရန် သို့မဟုတ် OTP ပို့ရန် အသုံးမပြုပါ။</Type>
    <Button title="ပရိုဖိုင် သိမ်းမယ်" busy={busy} disabled={busy} onPress={() => void saveDetails()} />
    <Notice message={error} />
    {message ? <Type accessibilityLiveRegion="polite">{message}</Type> : null}
  </Panel>;
}

const styles = StyleSheet.create({
  panel: { gap: 16 },
  identity: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  avatar: { width: 72, height: 72, borderRadius: 36 },
  initial: { alignItems: 'center', justifyContent: 'center' },
  initialText: { fontSize: 28, lineHeight: 36 },
  identityCopy: { flex: 1, gap: 2 },
  photoActions: { flexDirection: 'row', gap: 8 },
  action: { flex: 1 },
});
