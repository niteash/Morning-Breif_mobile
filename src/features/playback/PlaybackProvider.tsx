import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, useSyncExternalStore, type ReactNode } from 'react';
import { setAudioModeAsync, useAudioPlayer } from 'expo-audio';
import * as Notifications from 'expo-notifications';
import { AppState } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { createPlayback, type AudioPort } from '../../lib/playback';
import { getSavedTodayBriefing, getHistoricalBriefing, generateBriefing, getGenerationRequest, type GenerationJob } from '../../services/briefingApi';
import { getMyPreferences, updateListeningProgress } from '../../services/userApi';
import { useReadResource } from '../../hooks/useReadResource';
import { useAccountId } from '../../components/AuthGate';
import { createAutoPlayGate, isForegroundAutoPlayDue } from '../../lib/autoPlay';
import { ApiError } from '../../lib/http';
import { configureAutoDownload } from '../../lib/autoDownloadTask';

function createAudioPort(player: ReturnType<typeof useAudioPlayer>): AudioPort {
  let cancel: (() => void) | undefined;
    return {
      async prepare() { await setAudioModeAsync({ playsInSilentMode: true, shouldPlayInBackground: true, interruptionMode: 'doNotMix' }); },
      load(url) {
        cancel?.();
        return new Promise<void>((resolve, reject) => {
          let finished = false;
          const done = (error?: Error) => {
            if (finished) return;
            finished = true; clearTimeout(timer); listener.remove(); cancel = undefined;
            if (error) reject(error); else resolve();
          };
          const listener = player.addListener('playbackStatusUpdate', status => {
            if (status.error) done(Error('Audio unavailable'));
            else if (status.isLoaded) done();
          });
          const timer = setTimeout(() => done(Error('Audio loading timed out')), 20_000);
          cancel = () => done(Error('Source superseded'));
          try { player.replace({ uri: url }); } catch { done(Error('Audio unavailable')); }
        });
      },
      cancelLoad() { cancel?.(); },
      play() { player.setActiveForLockScreen(true, { title: 'နေ့သစ် — Nay Thit', artist: 'နေ့စဉ် သတင်းအနှစ်ချုပ်' }, { showSeekBackward: true, showSeekForward: true }); player.play(); },
      pause() { player.pause(); }, seek(seconds) { return player.seekTo(seconds); }, rate(value) { player.setPlaybackRate(value); },
      stop() { try { player.pause(); player.setActiveForLockScreen(false); player.replace(null); } catch { /* Native hook may already be released. */ } },
      metadata(value) { try { player.updateLockScreenMetadata(value); } catch { /* Metadata is optional. */ } },
    };
}

function usePlaybackOwner() {
  const owner = useAccountId();
  // A constant source keeps one native player; URL replacement is coordinated explicitly.
  const player = useAudioPlayer(null);
  const port = useMemo(() => createAudioPort(player), [player]);
  const controller = useMemo(() => createPlayback(owner, port, async record => (await getHistoricalBriefing(record.id)).briefing), [owner, port]);
  const playback = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  useEffect(() => {
    controller.activate();
    const listener = player.addListener('playbackStatusUpdate', controller.status);
    return () => { listener.remove(); controller.dispose(); };
  }, [controller, player]);
  return { playback, controller };
}
function useBriefingData() {
  const owner = useAccountId();
  const saved = useReadResource(useCallback(async () => (await getSavedTodayBriefing()).briefing, []));
  const profile = useReadResource(useCallback(async () => (await getMyPreferences()).profile, []));
  const [generating, setGenerating] = useState(false);
  const [generationStartedAt, setGenerationStartedAt] = useState<number | null>(null);
  const [generationError, setGenerationError] = useState<string | null>(null);
  const [generationErrorCode, setGenerationErrorCode] = useState<string | null>(null);
  const [generationJob, setGenerationJob] = useState<GenerationJob | null>(null);
  const [categorySelectionChanged, setCategorySelectionChanged] = useState(false);
  const mounted = useRef(true), generationLock = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const refreshSaved = saved.refresh, refreshProfile = profile.refresh;
  const refresh = useCallback(() => { void refreshSaved(false); void refreshProfile(false); }, [refreshSaved, refreshProfile]);
  useEffect(() => {
    const notification = Notifications.addNotificationReceivedListener(event => {
      if (event.request.content.data?.type === 'briefing_ready') void refreshSaved(true);
    });
    const response = Notifications.addNotificationResponseReceivedListener(event => {
      if (event.notification.request.content.data?.type === 'briefing_ready') void refreshSaved(true);
    });
    const foreground = AppState.addEventListener('change', state => { if (state === 'active') refresh(); });
    return () => { notification.remove(); response.remove(); foreground.remove(); };
  }, [refresh, refreshSaved]);
  const activeKey = `active-generation:${process.env.EXPO_PUBLIC_SUPABASE_URL ?? 'unknown'}:${owner}`;
  const categoryStaleKey = `briefing-category-stale:${process.env.EXPO_PUBLIC_SUPABASE_URL ?? 'unknown'}:${owner}`;
  useEffect(() => {
    let alive = true;
    void AsyncStorage.getItem(categoryStaleKey).then(value => {
      if (alive) setCategorySelectionChanged(value === 'true');
    }).catch(() => {});
    return () => { alive = false; };
  }, [categoryStaleKey]);
  const markCategorySelectionChanged = useCallback(async () => {
    setCategorySelectionChanged(true);
    setGenerationError(null); setGenerationErrorCode(null); setGenerationJob(null);
    try { await AsyncStorage.setItem(categoryStaleKey, 'true'); }
    catch { /* In-memory invalidation still prevents stale playback this session. */ }
  }, [categoryStaleKey]);
  const monitor = useCallback(async (id: string) => {
    while (mounted.current) {
      const { request } = await getGenerationRequest(id);
      if (!mounted.current) return;
      setGenerationJob(request);
      if (request.state === 'ready') {
        await AsyncStorage.removeItem(activeKey);
        await refreshSaved(true);
        await AsyncStorage.removeItem(categoryStaleKey);
        if (mounted.current) setCategorySelectionChanged(false);
        return;
      }
      if (request.state === 'failed') {
        await AsyncStorage.removeItem(activeKey);
        throw Object.assign(new Error(request.message || 'Generation failed temporarily.'), { code: request.error_code });
      }
      await new Promise(resolve => setTimeout(resolve, 2000));
    }
  }, [activeKey, categoryStaleKey, refreshSaved]);
  useEffect(() => {
    let alive = true;
    void AsyncStorage.getItem(activeKey).then(id => {
      if (!alive || !id || generationLock.current) return;
      generationLock.current = true; setGenerating(true); setGenerationStartedAt(Date.now());
      void monitor(id).catch(error => {
        if (mounted.current) { setGenerationError(error.message); setGenerationErrorCode(error.code ?? null); }
      }).finally(() => {
        generationLock.current = false;
        if (mounted.current) { setGenerating(false); setGenerationStartedAt(null); }
      });
    });
    return () => { alive = false; };
  }, [activeKey, monitor]);
  async function generate() {
    if (generationLock.current) return;
    generationLock.current = true; setGenerating(true); setGenerationStartedAt(Date.now()); setGenerationError(null); setGenerationErrorCode(null);
    try {
      const { request } = await generateBriefing(profile.data?.briefing_length ?? 'standard');
      setGenerationJob(request);
      await AsyncStorage.setItem(activeKey, request.id);
      await monitor(request.id);
    } catch (error) {
      if (mounted.current) {
        const code = error instanceof ApiError ? error.code ?? null : error && typeof error === 'object' && 'code' in error ? String(error.code) : null;
        setGenerationErrorCode(code);
        setGenerationError(code === 'no_recent_news'
          ? 'ရွေးချယ်ထားသော ကဏ္ဍများတွင် လတ်တလောသတင်း မရှိသေးပါ။ ကဏ္ဍပြောင်းပါ သို့မဟုတ် သတင်းအသစ်ဝင်ပြီးနောက် ပြန်ကြိုးစားပါ။'
          : code === 'generation_limit_reached'
            ? 'ယနေ့အတွက် အသံအသစ် ပြန်ပြင်ဆင်နိုင်သည့် အကြိမ်ပြည့်သွားပါပြီ။ ပြင်ဆင်ပြီးသား နောက်ဆုံးအသံကို ယခု နားဆင်နိုင်ပါသည်။'
            : error instanceof Error ? error.message : 'အနှစ်ချုပ် ပြင်ဆင်မရပါ။ ပြန်ကြိုးစားပါ။');
      }
    }
    finally { generationLock.current = false; if (mounted.current) { setGenerating(false); setGenerationStartedAt(null); } }
  }
  return { saved, profile, generating, generationStartedAt, generationError, generationErrorCode,
    generationJob, categorySelectionChanged, markCategorySelectionChanged, generate, refresh };
}
type ContextValue = ReturnType<typeof usePlaybackOwner> & ReturnType<typeof useBriefingData> & {
  sleepTimerEndsAt: number | null;
  setSleepTimer: (minutes: number | null) => void;
};
const PlaybackContext = createContext<ContextValue | null>(null);
export function PlaybackProvider({ children }: { children: ReactNode }) {
  const owner = useAccountId();
  const audio = usePlaybackOwner();
  const data = useBriefingData();
  const autoPlayGate = useMemo(
    () => createAutoPlayGate(AsyncStorage, process.env.EXPO_PUBLIC_SUPABASE_URL ?? 'unknown'),
    [],
  );
  const todayRecord = data.saved.data ?? null;
  const { playing, intentPlaying, record: selectedRecord } = audio.playback;
  const autoDownloadEnabled = data.profile.data?.auto_download_wifi === true;
  const [sleepTimerEndsAt, setSleepTimerEndsAt] = useState<number | null>(null);
  const setSleepTimer = useCallback((minutes: number | null) => {
    setSleepTimerEndsAt(minutes ? Date.now() + minutes * 60_000 : null);
  }, []);

  useEffect(() => {
    if (!sleepTimerEndsAt) return;
    const remaining = sleepTimerEndsAt - Date.now();
    const timer = setTimeout(() => { audio.controller.pause(); setSleepTimerEndsAt(null); }, Math.max(0, remaining));
    return () => clearTimeout(timer);
  }, [audio.controller, sleepTimerEndsAt]);

  useEffect(() => {
    if (data.profile.data) void configureAutoDownload(autoDownloadEnabled).catch(() => {});
  }, [autoDownloadEnabled, data.profile.data]);
  const progressSavedAt = useRef(0);
  const progressSyncedAt = useRef(0);

  useEffect(() => {
    const record = audio.playback.record;
    if (!record || audio.playback.loading) return;
    const now = Date.now();
    if (now - progressSavedAt.current < 5000 && audio.playback.playing) return;
    progressSavedAt.current = now;
    const key = `playback-position:${owner}:${record.id}`;
    void AsyncStorage.setItem(key, String(Math.floor(audio.playback.position)));
    if (now - progressSyncedAt.current >= 15000 || !audio.playback.playing) {
      progressSyncedAt.current = now;
      void updateListeningProgress({
        briefing_id: record.id,
        position_seconds: Math.floor(audio.playback.position),
        listened_seconds: Math.floor(audio.playback.position),
        completed: audio.playback.duration > 0 && audio.playback.position >= audio.playback.duration - 10,
      }).catch(() => { /* Local progress remains available offline. */ });
    }
  }, [audio.playback.duration, audio.playback.loading, audio.playback.playing, audio.playback.position, audio.playback.record, owner]);

  useEffect(() => {
    if (playing && selectedRecord?.user_id === owner) {
      void autoPlayGate.markHandled(owner, selectedRecord.id);
    }
  }, [autoPlayGate, owner, playing, selectedRecord?.id, selectedRecord?.user_id]);

  useEffect(() => {
    let alive = true;
    async function maybeStart() {
      if (process.env.EXPO_PUBLIC_AUTO_PLAY_ENABLED !== 'true') return;
      if (data.profile.loading || data.profile.error) return;
      if (!isForegroundAutoPlayDue(data.profile.data, todayRecord, owner, AppState.currentState,
        new Date(), process.env.EXPO_PUBLIC_AUTO_PLAY_ENABLED === 'true')) return;
      if (playing || intentPlaying) {
        if (selectedRecord?.id === todayRecord?.id && todayRecord) {
          void autoPlayGate.markHandled(owner, todayRecord.id);
        }
        return;
      }
      if (!todayRecord || !(await autoPlayGate.claim(owner, todayRecord.id)) || !alive) return;
      await audio.controller.select(todayRecord, true, true);
    }
    void maybeStart();
    const subscription = AppState.addEventListener('change', state => {
      if (state === 'active') void maybeStart();
    });
    return () => { alive = false; subscription.remove(); };
  }, [audio.controller, autoPlayGate, data.profile.data, data.profile.error, data.profile.loading,
    intentPlaying, owner, playing, selectedRecord, todayRecord]);
  return <PlaybackContext.Provider value={{ ...audio, ...data, sleepTimerEndsAt, setSleepTimer }}>{children}</PlaybackContext.Provider>;
}
export function useBriefing() {
  const value = useContext(PlaybackContext);
  if (!value) throw Error('Playback must be inside the authenticated main layout');
  return value;
}
