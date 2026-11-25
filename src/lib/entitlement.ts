export type Trial = {
  status: 'subscription_active' | 'trial_active' | 'trial_ended' | 'verification_required' | 'onboarding_required' | 'claim_required' | 'claim_unavailable';
  expires_at: string | null; can_generate: boolean; claim_mode: 'staging_account' | 'device_required';
  entitlement_kind?: 'purchase';
  generation_usage?: { used: number; limit: number; remaining: number } | null;
};
export const trialMessages: Record<Trial['status'], string> = {
  subscription_active: 'အဖွဲ့ဝင်ခွင့် အသုံးပြုနေသည်',
  trial_active: 'အခမဲ့ စမ်းသပ်ခွင့် အသုံးပြုနေသည်', trial_ended: 'အခမဲ့ စမ်းသပ်ခွင့် ပြီးဆုံးပါပြီ',
  verification_required: 'အီးမေးလ်ကို အတည်ပြုပါ', onboarding_required: 'စတင်အသုံးပြုရန် စနစ်ပြင်ဆင်မှု လိုအပ်သည်',
  claim_unavailable: 'စက်အတည်ပြုမှု မရရှိသေးပါ', claim_required: 'စမ်းသပ်ခွင့် ရယူပါ',
};
export function parseTrial(input: unknown): Trial {
  const data = input as Trial | null;
  if (!data || !Object.hasOwn(trialMessages, data.status) || typeof data.can_generate !== 'boolean'
      || !['staging_account', 'device_required'].includes(data.claim_mode)
      || !(data.expires_at === null || typeof data.expires_at === 'string' && Number.isFinite(Date.parse(data.expires_at)))
      || data.can_generate && !['trial_active', 'subscription_active'].includes(data.status)
      || data.entitlement_kind !== undefined && data.entitlement_kind !== 'purchase'
      || data.generation_usage !== undefined && data.generation_usage !== null && (
        !Number.isInteger(data.generation_usage.used) || !Number.isInteger(data.generation_usage.limit)
        || !Number.isInteger(data.generation_usage.remaining) || data.generation_usage.limit < 1
        || data.generation_usage.used < 0 || data.generation_usage.remaining < 0
      )
      || data.status === 'trial_active' && data.expires_at === null) {
    throw Error('စမ်းသပ်ခွင့် အခြေအနေကို ရယူမရပါ။ ပြန်စစ်ပါ။');
  }
  return data;
}
