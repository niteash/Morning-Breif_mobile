import { Platform } from 'react-native';
import * as WebBrowser from 'expo-web-browser';
import type { SupabaseClient } from '@supabase/supabase-js';
import { parseGoogleAuthCallback } from './googleAuthCallback';

export const GOOGLE_AUTH_REDIRECT = 'morningbrief://auth/google';

WebBrowser.maybeCompleteAuthSession();

export async function signInWithGoogle(client: SupabaseClient) {
  const { data, error } = await client.auth.signInWithOAuth({
    provider: 'google',
    options: {
      redirectTo: GOOGLE_AUTH_REDIRECT,
      skipBrowserRedirect: Platform.OS !== 'web',
      queryParams: { prompt: 'select_account' },
    },
  });
  if (error) throw new Error('Google အကောင့်ဝင်ခြင်းကို စတင်မရပါ။');
  if (Platform.OS === 'web') return null;
  if (!data.url) throw new Error('Google အကောင့်လင့်ခ် မရရှိပါ။');

  const result = await WebBrowser.openAuthSessionAsync(data.url, GOOGLE_AUTH_REDIRECT);
  if (result.type === 'cancel' || result.type === 'dismiss') return null;
  if (result.type !== 'success') throw new Error('Google အကောင့်ဝင်ခြင်း မပြီးဆုံးပါ။');

  const exchanged = await client.auth.exchangeCodeForSession(parseGoogleAuthCallback(result.url));
  if (exchanged.error || !exchanged.data.session || exchanged.data.user.is_anonymous) {
    throw new Error('Google အကောင့်ဖြင့် ဝင်ရောက်မရပါ။');
  }
  return exchanged.data.session;
}
