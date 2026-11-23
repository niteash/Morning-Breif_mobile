import type { SupabaseClient } from '@supabase/supabase-js';

export const AUTH_CALLBACK = 'morningbrief://auth/callback';
export const authRedirect = (flow: 'signup' | 'recovery' | 'email_change') => `${AUTH_CALLBACK}?flow=${flow}`;
export function normalizeEmail(value: string) {
  const email = value.trim().toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) throw Error('မှန်ကန်သော အီးမေးလ်လိပ်စာ ထည့်ပါ။');
  return email;
}
export function validatePassword(value: string) {
  if (value.length < 12) throw Error('စကားဝှက်ကို အနည်းဆုံး စာလုံး ၁၂ လုံး ထည့်ပါ။');
}
export function emailAuthError(error: { code?: string; status?: number }) {
  if (error.code === 'email_not_confirmed') return 'အီးမေးလ်ကို အတည်ပြုပြီးမှ ဝင်ရောက်ပါ။';
  if (error.code === 'invalid_credentials') return 'အီးမေးလ် သို့မဟုတ် စကားဝှက် မမှန်ပါ။ Google ဖြင့်ဖွင့်ထားသောအကောင့်ဆိုလျှင် Google ခလုတ်ကို အသုံးပြုပါ။';
  if (error.code === 'email_address_not_authorized') return 'စမ်းသပ်အီးမေးလ်ပို့စနစ်က ဤလိပ်စာသို့ မပို့နိုင်ပါ။ စီမံသူကို ဆက်သွယ်ပါ။';
  if (error.status === 429 || error.code?.includes('rate_limit')) return 'တောင်းဆိုမှု များနေပါသည်။ ခဏစောင့်ပြီး ပြန်ကြိုးစားပါ။';
  if (error.code === 'email_exists' || error.code === 'user_already_exists') return 'ဤအီးမေးလ်ကို အသုံးပြုထားပြီး ဖြစ်ပါသည်။ မူလအကောင့်သို့ ဝင်ရောက်ပါ။ အကောင့်များကို အလိုအလျောက် မပေါင်းပါ။';
  if (error.code === 'weak_password') return 'ပိုမိုခိုင်မာသော စကားဝှက်တစ်ခု ရွေးပါ။';
  return 'အကောင့်ဝန်ဆောင်မှု မရရှိသေးပါ။ ချိတ်ဆက်မှုကို စစ်ပြီး ပြန်ကြိုးစားပါ။';
}
export async function createEmailAccount(client: SupabaseClient, address: string, password: string) {
  const email = normalizeEmail(address); validatePassword(password);
  const current = await client.auth.getSession();
  if (current.data.session) throw Error('လက်ရှိအကောင့်သို့ အီးမေးလ်ထည့်ရန် ဆက်တင်ကို အသုံးပြုပါ။');
  const { data, error } = await client.auth.signUp({ email, password, options: { emailRedirectTo: authRedirect('signup') } });
  if (error) throw Error(emailAuthError(error));
  if (data.session) {
    // Misconfigured confirmation must not silently become the supported signup flow.
    await client.auth.signOut({ scope: 'local' });
    throw Error('အီးမေးလ်အတည်ပြုမှု ဆက်တင်ကို စီမံသူ စစ်ဆေးရန်လိုပါသည်။');
  }
  return email; // Deliberately does not disclose whether the address already exists.
}
export async function signInEmail(client: SupabaseClient, address: string, password: string) {
  const { data, error } = await client.auth.signInWithPassword({ email: normalizeEmail(address), password });
  if (error) throw Error(emailAuthError(error));
  if (!data.session || data.user.is_anonymous) throw Error('အကောင့်ကို ဝင်ရောက်မရပါ။');
  return data.session;
}
export async function sendEmailLink(client: SupabaseClient, address: string, recovery: boolean) {
  const email = normalizeEmail(address);
  const result = recovery
    ? await client.auth.resetPasswordForEmail(email, { redirectTo: authRedirect('recovery') })
    : await client.auth.resend({ type: 'signup', email, options: { emailRedirectTo: authRedirect('signup') } });
  if (result.error) throw Error(emailAuthError(result.error));
}
export async function addEmailToAccount(client: SupabaseClient, userId: string, address: string) {
  const { data, error } = await client.auth.getUser();
  if (error || data.user?.id !== userId) throw Error('အကောင့် ပြောင်းသွားပါသည်။ ပြန်ဝင်ပါ။');
  const result = await client.auth.updateUser({ email: normalizeEmail(address) }, { emailRedirectTo: authRedirect('email_change') });
  if (result.error) throw Error(emailAuthError(result.error));
  if (result.data.user.id !== userId) throw Error('အကောင့် ပြောင်းသွားပါသည်။ ပြန်ဝင်ပါ။');
}
export async function saveAccountPassword(client: SupabaseClient, userId: string, password: string) {
  validatePassword(password);
  const { data, error } = await client.auth.getUser();
  if (error || data.user?.id !== userId || !data.user.email || !data.user.email_confirmed_at) throw Error('သင့်အကောင့်၏ အီးမေးလ်ကို အရင်အတည်ပြုပါ။');
  const result = await client.auth.updateUser({ password });
  if (result.error) throw Error(emailAuthError(result.error));
  if (result.data.user.id !== userId) throw Error('အကောင့် ပြောင်းသွားပါသည်။ ပြန်ဝင်ပါ။');
}

export function parseAuthCallback(value: string) {
  const url = new URL(value);
  if (url.protocol !== 'morningbrief:' || url.hostname !== 'auth' || url.pathname !== '/callback' || url.username || url.password || url.port) throw Error('Invalid callback');
  if (url.hash || url.searchParams.has('error') || url.searchParams.has('error_code')) throw Error('Expired or invalid link');
  const flow = url.searchParams.get('flow'), code = url.searchParams.get('code');
  if (!['signup', 'recovery', 'email_change'].includes(flow || '') || !code || code.length > 2048 || url.searchParams.getAll('code').length !== 1) throw Error('Invalid callback');
  return { flow, code };
}
// The PKCE verifier stays in the existing SDK storage. No tokens are put in app routes.
export function createCallbackConsumer(client: SupabaseClient) {
  let lastCode: string | undefined, pending: Promise<{ userId: string; recovery: boolean; flow: string | null }> | undefined;
  return (url: string) => {
    const { flow, code } = parseAuthCallback(url);
    if (lastCode === code && pending) return pending;
    lastCode = code;
    pending = (async () => {
      const { data, error } = await client.auth.exchangeCodeForSession(code);
      if (error || !data.session || data.session.user.is_anonymous) throw Error('Link expired or opened on another device. Request a new link on this device.');
      const recovery = 'redirectType' in data && data.redirectType === 'recovery';
      if (flow === 'recovery' && !recovery) throw Error('Request a new password recovery link on this device.');
      return { userId: data.session.user.id, recovery, flow };
    })();
    return pending;
  };
}
