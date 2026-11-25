import { useEffect } from "react";
import { Stack, router } from "expo-router";
import * as Notifications from "expo-notifications";
import { useFonts } from "expo-font";
import { FontReadyContext } from "../components/ui/primitives";
import { PreferencesProvider, usePalette, usePreferences } from '../features/preferences/PreferencesProvider';
import { MotionProvider, useMotionReduced } from '../components/ui/Motion';
import { StatusBar } from 'expo-status-bar';
import { AuthFlowProvider } from '../features/auth/AuthFlowProvider';
import { AdsProvider } from '../features/ads/AdsProvider';
import { initializeAutoDownloadTask } from '../lib/autoDownloadTask';


export default function RootLayout() {
  const [fontsLoaded] = useFonts({ Padauk: require('../../assets/fonts/Padauk-Regular.ttf'), PadaukBold: require('../../assets/fonts/Padauk-Bold.ttf') });
  // Notification payloads carry an opaque briefing ID only; the authenticated
  // historical endpoint validates ownership before playback fetches any audio.
  useEffect(() => {
    void initializeAutoDownloadTask();
  }, []);
  useEffect(() => {
    let lastHandled = '';
    const openBriefing = (response: Notifications.NotificationResponse | null) => {
      if (!response) return;
      const data = response?.notification.request.content.data;
      const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
      const briefingId = typeof data?.briefing_id === 'string' && uuid.test(data.briefing_id) ? data.briefing_id : null;
      const articleId = typeof data?.article_id === 'string' && uuid.test(data.article_id) ? data.article_id : null;
      if (data?.type !== 'briefing_ready' && data?.type !== 'breaking_news') return;
      if ((data.type === 'briefing_ready' && !briefingId) || (data.type === 'breaking_news' && !articleId)) return;
      const identity = `${response.actionIdentifier}:${response.notification.request.identifier}`;
      if (identity === lastHandled) return;
      lastHandled = identity;
      if (briefingId) router.push(`/player?briefingId=${encodeURIComponent(briefingId)}`);
      else if (articleId) router.push(`/article/${encodeURIComponent(articleId)}`);
      void Notifications.clearLastNotificationResponseAsync().catch(() => {});
    };
    const responseSubscription = Notifications.addNotificationResponseReceivedListener(openBriefing);
    void Notifications.getLastNotificationResponseAsync().then(openBriefing).catch(() => {});
    return () => responseSubscription.remove();
  }, []);

  return (
    <PreferencesProvider><MotionProvider><FontReadyContext.Provider value={fontsLoaded}><AdsProvider><AuthFlowProvider><RootStack /></AuthFlowProvider></AdsProvider></FontReadyContext.Provider></MotionProvider></PreferencesProvider>
  );
}

function RootStack() {
  const colors = usePalette(), { theme } = usePreferences(), reduced = useMotionReduced();
  return <><StatusBar style={theme === 'dark' ? 'light' : 'dark'} /><Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.background }, animation: reduced ? 'none' : 'slide_from_right' }} /></>;
}
