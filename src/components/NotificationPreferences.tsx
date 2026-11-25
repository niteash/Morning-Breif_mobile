import { useCallback, useState } from 'react';
import { Linking } from 'react-native';
import * as Notifications from 'expo-notifications';
import { useReadResource, useReadRefresh } from '../hooks/useReadResource';
import { Button, Notice, Panel, Type } from './ui/primitives';
export function NotificationPreferences({ enabled, disabled, onToggle }: {
  enabled: boolean;
  disabled?: boolean;
  onToggle: (enabled: boolean) => Promise<void>;
}) {
  const permission = useReadResource(useCallback(() => Notifications.getPermissionsAsync(), []));
  const [busy, setBusy] = useState(false), [error, setError] = useState<string | null>(null);
  const refresh = permission.refresh;
  useReadRefresh(useCallback(() => { void refresh(false); }, [refresh]));
  async function request() {
    setBusy(true); setError(null);
    try { await Notifications.requestPermissionsAsync(); await permission.refresh(); }
    catch { setError('လုပ်ဆောင်မှု မအောင်မြင်ပါ။'); } finally { setBusy(false); }
  }
  async function toggle() {
    setBusy(true); setError(null);
    try { await onToggle(!enabled); }
    catch { setError('လုပ်ဆောင်မှု မအောင်မြင်ပါ။ ပြန်ကြိုးစားပါ။'); }
    finally { setBusy(false); }
  }
  return <Panel><Type variant="label">အသိပေးချက်များ</Type>
    <Type>{permission.error || !permission.data ? 'မသိရသေးပါ' : permission.data.granted ? 'ခွင့်ပြုထားသည်' : permission.data.status === 'undetermined' ? 'မတောင်းရသေးပါ' : 'ခွင့်မပြုထားပါ'}</Type>
    <Notice message={permission.error || error} retry={() => void permission.refresh()} />
    <Type variant="muted">ဖုန်းခွင့်ပြုချက်သည် အသိပေးပို့ခြင်း အောင်မြင်မည်ဟု အာမမခံပါ။</Type>
    {process.env.EXPO_PUBLIC_PUSH_ENABLED === 'false' ? <Type variant="muted">ဤပတ်ဝန်းကျင်တွင် အသိပေးပို့ခြင်း ပိတ်ထားသည်။</Type> : null}
    <Type>{enabled ? 'နေ့စဉ် အသိပေးချက် ဖွင့်ထားသည်။' : 'နေ့စဉ် အသိပေးချက် ပိတ်ထားသည်။'}</Type>
    <Button secondary disabled={disabled || process.env.EXPO_PUBLIC_PUSH_ENABLED === 'false' || !permission.data?.granted} busy={busy} title={enabled ? 'နေ့စဉ်အသိပေးချက် ပိတ်မယ်' : 'နေ့စဉ်အသိပေးချက် ဖွင့်မယ်'} onPress={() => void toggle()} />
    {!permission.data?.granted && permission.data?.canAskAgain ? <Button secondary title="ခွင့်ပြုချက် တောင်းမယ်" busy={busy} onPress={() => void request()} /> : null}
    <Button secondary title="ဖုန်းဆက်တင် ဖွင့်မယ်" onPress={() => { void Linking.openSettings().catch(() => setError('ဖွင့်မရပါ။ ပြန်ကြိုးစားပါ။')); }} />
  </Panel>;
}
