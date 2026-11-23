import { useCallback, useState } from 'react';
import { supabase } from '../lib/supabase';
import { addEmailToAccount, sendEmailLink } from '../lib/emailAuth';
import { useAccountId } from './AuthGate';
import { useReadResource } from '../hooks/useReadResource';
import { Button, Field, Notice, Panel, Type } from './ui/primitives';
export function AccountSettings() {
  const owner = useAccountId();
  const account = useReadResource(useCallback(async () => {
    const { data, error } = await supabase.auth.getUser();
    if (error || !data.user || data.user.id !== owner) throw Error();
    return {
      email: data.user.email,
      verified: Boolean(data.user.email_confirmed_at),
      providers: [...new Set((data.user.identities ?? []).map(identity => identity.provider))],
    };
  }, [owner]));
  const [draft, setDraft] = useState(''), [busy, setBusy] = useState(false), [error, setError] = useState<string | null>(null), [message, setMessage] = useState<string | null>(null);
  async function update(recovery: boolean) {
    if (busy) return;
    setBusy(true); setError(null); setMessage(null);
    try {
      if (recovery && account.data?.email) await sendEmailLink(supabase, account.data.email, true);
      else await addEmailToAccount(supabase, owner, draft);
      setMessage('လင့်ခ်တောင်းဆိုပြီးပါပြီ။ အီးမေးလ်ကို စစ်ဆေးပါ။'); setDraft('');
    } catch (e) { setError(e instanceof Error ? e.message : 'လုပ်ဆောင်မှု မအောင်မြင်ပါ။'); }
    finally { setBusy(false); }
  }
  return <Panel><Type variant="label">အကောင့်ဝင်နည်းများ</Type>
    <Notice message={account.error} retry={() => void account.refresh()} />
    {account.data ? <>
      <Type translate={false}>{account.data.email || '—'}</Type>
      <Type variant="muted" translate={false}>{account.data.providers.map(provider => provider === 'google' ? 'Google' : provider === 'email' ? 'Email & password' : provider).join(' · ') || 'Email'}</Type>
      {!account.data.verified ? <Type>အီးမေးလ်ကို အတည်ပြုပါ</Type> : null}
    </> : null}
    <Field label="အီးမေးလ်" value={draft} onChangeText={setDraft} autoCapitalize="none" autoCorrect={false} keyboardType="email-address" editable={!busy} />
    <Button secondary title="အီးမေးလ် ပြောင်းမယ်" busy={busy} disabled={!draft.trim() || Boolean(account.error)} onPress={() => void update(false)} />
    <Button secondary title="စကားဝှက် ပြန်လည်ရယူမယ်" busy={busy} disabled={!account.data?.email || Boolean(account.error)} onPress={() => void update(true)} />
    <Notice message={error} />{message ? <Type accessibilityLiveRegion="polite">{message}</Type> : null}
  </Panel>;
}
