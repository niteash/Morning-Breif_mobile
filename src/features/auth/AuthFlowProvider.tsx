import { clearOfflineAudio } from '../../services/offlineAudioStorage';
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import * as Linking from 'expo-linking';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { router } from 'expo-router';
import { supabase } from '../../lib/supabase';
import { createCallbackConsumer } from '../../lib/emailAuth';

const consume = createCallbackConsumer(supabase);
const recoveryKey = `nay-thit:password-recovery:${process.env.EXPO_PUBLIC_SUPABASE_URL}`;
type State = { initializing: boolean; processing: boolean; recoveryUser: string | null; error: string | null };
const Context = createContext<State & { finishRecovery(): Promise<void> }>({ initializing: true, processing: false, recoveryUser: null, error: null, finishRecovery: async () => {} });
export const useAuthFlow = () => useContext(Context);

export function AuthFlowProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>({ initializing: true, processing: false, recoveryUser: null, error: null });
  useEffect(() => {
    let active = true, processing = false;
    async function handle(url: string | null) {
      if (!url?.startsWith('morningbrief://auth/callback')) return;
      processing = true;
      setState(previous => ({ ...previous, processing: true, error: null }));
      router.replace('/auth/callback');
      try {
        const result = await consume(url);
        if (!active) return;
        if (result.recovery) {
          await AsyncStorage.setItem(recoveryKey, result.userId);
          if (!active) return;
          setState(previous => ({ ...previous, recoveryUser: result.userId, processing: false }));
          router.replace('/reset-password');
        } else {
          const recoveryUser = await AsyncStorage.getItem(recoveryKey);
          if (!active) return;
          setState(previous => ({ ...previous, processing: false }));
          router.replace(recoveryUser === result.userId ? '/reset-password' : result.flow === 'email_change' ? '/link-email' : '/home');
        }
      } catch {
        if (active) setState(previous => ({ ...previous, processing: false, error: 'လင့်ခ် သက်တမ်းကုန်သွားခြင်း သို့မဟုတ် ဤဖုန်းမှ မတောင်းခဲ့ခြင်း ဖြစ်နိုင်ပါသည်။ ဤဖုန်းမှ လင့်ခ်အသစ် တောင်းပါ။' }));
      } finally { processing = false; }
    }
    const subscription = supabase.auth.onAuthStateChange((event, session) => {
      if (event === 'PASSWORD_RECOVERY' && session) {
        setState(previous => ({ ...previous, recoveryUser: session.user.id }));
        // No awaited Auth call inside the SDK's locked auth callback.
        void AsyncStorage.setItem(recoveryKey, session.user.id).catch(() => {
          if (active) setState(previous => ({ ...previous, error: 'ပြန်လည်ရယူမှုကို သိမ်းမရပါ။ စကားဝှက်ပြောင်းခြင်းကို ယခုပြီးစီးပါ။' }));
        });
      } else if (event === 'SIGNED_OUT') {
        void clearOfflineAudio().catch(() => {});
        setState(previous => ({ ...previous, recoveryUser: null }));
        void AsyncStorage.removeItem(recoveryKey).catch(() => {});
      }
    }).data.subscription;
    const links = Linking.addEventListener('url', event => { void handle(event.url); });
    void (async () => {
      try {
        const initial = await Linking.getInitialURL();
        if (initial?.startsWith('morningbrief://auth/callback')) await handle(initial);
        else {
          const remembered = await AsyncStorage.getItem(recoveryKey);
          const { data } = await supabase.auth.getSession();
          if (active && !processing && remembered && data.session?.user.id === remembered) {
            setState(previous => ({ ...previous, recoveryUser: remembered }));
            router.replace('/reset-password');
          }
        }
      } catch { if (active) setState(previous => ({ ...previous, error: 'အကောင့်လင့်ခ်ကို စစ်ဆေးမရပါ။ ပြန်ကြိုးစားပါ။' })); }
      finally { if (active) setState(previous => ({ ...previous, initializing: false })); }
    })();
    return () => { active = false; links.remove(); subscription.unsubscribe(); };
  }, []);
  async function finishRecovery() {
    await AsyncStorage.removeItem(recoveryKey);
    setState(previous => ({ ...previous, recoveryUser: null, error: null }));
  }
  return <Context.Provider value={{ ...state, finishRecovery }}>{children}</Context.Provider>;
}
