import { Platform } from 'react-native';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useAccountId } from '../components/AuthGate';
import { getOfflineAudio } from '../services/offlineAudioStorage';
import type { Recording } from '../lib/playback';
import { useReadResource } from './useReadResource';
import { getEntitlement } from '../services/entitlementApi';
export function useOfflineAudio() {
  const owner = useAccountId();
  const cache = useMemo(() => getOfflineAudio(owner), [owner]);
  const entitlement = useReadResource(useCallback(() => getEntitlement(), []));
  useEffect(() => { cache.setLimit(entitlement.data?.entitlement_kind === 'purchase' ? Infinity : 5); }, [cache, entitlement.data?.entitlement_kind]);
  const downloads = useReadResource(useCallback(() => cache.list(), [cache]));
  const [busy, setBusy] = useState(false), [error, setError] = useState<string | null>(null);
  async function save(record: Recording) {
    if (busy) return;
    setBusy(true); setError(null);
    // The player already holds a freshly authenticated, owner-scoped signed URL.
    // Re-fetching the same briefing added a second failure point before download.
    try { await cache.save(record); await downloads.refresh(); }
    catch { setError(entitlement.data?.entitlement_kind === 'purchase' ? 'အသံ သိမ်းမရပါ။ အင်တာနက်နှင့် ဖုန်းနေရာလွတ်ကို စစ်ပါ။' : 'အသံ သိမ်းမရပါ။ အင်တာနက်နှင့် နေရာလွတ်ကို စစ်ပါ။ Free တွင် ဖိုင် ၅ ခုအထိ သိမ်းနိုင်သည်။'); }
    finally { setBusy(false); }
  }
  async function remove(id: string) {
    setBusy(true); setError(null);
    try { await cache.remove(id); await downloads.refresh(); }
    catch { setError('လုပ်ဆောင်မှု မအောင်မြင်ပါ။'); }
    finally { setBusy(false); }
  }
  return { supported: Platform.OS !== 'web', downloads, save, remove, busy, error, open: cache.open };
}
