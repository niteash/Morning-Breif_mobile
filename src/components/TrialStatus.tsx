import { useCallback } from 'react';
import { useReadResource, useReadRefresh } from '../hooks/useReadResource';
import { getEntitlement } from '../services/entitlementApi';
import { trialMessages } from '../lib/entitlement';
import { usePreferences } from '../features/preferences/PreferencesProvider';
import { Loading, Notice, Panel, Type } from './ui/primitives';
export function TrialStatus() {
  const trial = useReadResource(useCallback(() => getEntitlement(), [])), { language } = usePreferences();
  const refresh = trial.refresh;
  useReadRefresh(useCallback(() => { void refresh(false); }, [refresh]));
  return <Panel><Type variant="label">စမ်းသပ်ခွင့် အခြေအနေ</Type>
    {trial.loading ? <Loading /> : null}<Notice message={trial.error} retry={() => void trial.refresh()} />
    {trial.data && !trial.error && !trial.loading ? <>
      <Type>{trialMessages[trial.data.status]}</Type>
      {trial.data.expires_at ? <Type variant="muted">သက်တမ်းကုန်မည့်အချိန် · {new Date(trial.data.expires_at).toLocaleString(language === 'my' ? 'my-MM' : 'en-GB')}</Type> : null}
      <Type variant="muted">{trial.data.can_generate ? 'အသံအသစ် ပြင်ဆင်ခွင့် ရှိသည်' : 'အသံအသစ် ပြင်ဆင်ခွင့် မရှိပါ'}</Type>
      {trial.data.generation_usage ? <Type variant="muted" translate={false}>
        {language === 'my'
          ? `ယနေ့ အသံပြင်ဆင်မှု ${trial.data.generation_usage.used}/${trial.data.generation_usage.limit} · ${trial.data.generation_usage.remaining} ကြိမ် ကျန်`
          : `Today: ${trial.data.generation_usage.used}/${trial.data.generation_usage.limit} generations · ${trial.data.generation_usage.remaining} remaining`}
      </Type> : null}
    </> : null}
  </Panel>;
}
