import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { Button, Loading, Notice, Screen } from "./ui/primitives";
import { Redirect, router } from "expo-router";
import { supabase } from "../lib/supabase";
import { needsOnboarding } from "../lib/onboarding";
import { getMyCategories, getOptionalPreferences } from "../services/userApi";
import { useAuthFlow } from '../features/auth/AuthFlowProvider';

const AccountContext = createContext("");
export const useAccountId = () => useContext(AccountContext);

export function AuthGate({ children, requireOnboarding = false }: {
  children: ReactNode;
  requireOnboarding?: boolean;
}) {
  const authFlow = useAuthFlow();
  const [userId, setUserId] = useState<string | null | undefined>(undefined);
  const [retry, setRetry] = useState(0);
  const [setup, setSetup] = useState<{ userId: string; retry: number; needed?: boolean; error?: string }>();
  useEffect(() => {
    let active = true;
    let authEventReceived = false;
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      authEventReceived = true;
      if (active) setUserId(session && !session.user.is_anonymous ? session.user.id : null);
    });
    void supabase.auth.getSession().then(({ data, error }) => {
      if (active && !authEventReceived) setUserId(!error && data.session && !data.session.user.is_anonymous ? data.session.user.id : null);
    }).catch(() => {
      if (active && !authEventReceived) setUserId(null);
    });
    return () => { active = false; subscription.unsubscribe(); };
  }, []);

  // Fetch outside the auth callback; ignore results belonging to a previous user.
  useEffect(() => {
    if (!userId || !requireOnboarding) return;
    let active = true;
    void needsOnboarding(getOptionalPreferences, getMyCategories).then((needed) => {
      if (active) setSetup({ userId, retry, needed });
    }).catch((error) => {
      if (active) setSetup({ userId, retry, error: error instanceof Error ? error.message : "Unable to load your setup. Please try again." });
    });
    return () => { active = false; };
  }, [userId, requireOnboarding, retry]);

  if (authFlow.initializing || authFlow.processing) return <Screen><Loading /></Screen>;
  if (authFlow.recoveryUser) return <Redirect href="/reset-password" />;
  if (userId === null) return <Redirect href="/sign-in" />;
  if (userId === undefined || (requireOnboarding && (setup?.userId !== userId || setup?.retry !== retry))) {
    return <Screen><Loading /></Screen>;
  }
  if (requireOnboarding && setup?.error) return <Screen>
    <Notice message={setup.error} retry={() => setRetry(value => value + 1)} />
    <Button secondary title="အကောင့်ဖျက်သိမ်းမှု အခြေအနေ" onPress={() => router.replace("/delete-account")} />
  </Screen>;
  if (requireOnboarding && setup?.needed) return <Redirect href="/categories" />;
  return <AccountContext.Provider key={userId} value={userId}>{children}</AccountContext.Provider>;
}
