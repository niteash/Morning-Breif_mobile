import { getSavedTodayBriefing } from '../services/briefingApi';
import { getMyPreferences } from '../services/userApi';
import { getOfflineAudio } from '../services/offlineAudioStorage';
import { supabase } from './supabase';

export const AUTO_DOWNLOAD_TASK = 'nay-thit-wifi-auto-download';

type NativeModules = {
  BackgroundTask: typeof import('expo-background-task');
  Network: typeof import('expo-network');
  TaskManager: typeof import('expo-task-manager');
};
let nativeModules: Promise<NativeModules | null> | null = null;

async function loadNativeModules(): Promise<NativeModules | null> {
  if (!nativeModules) nativeModules = Promise.all([
    import('expo-background-task'), import('expo-network'), import('expo-task-manager'),
  ]).then(([BackgroundTask, Network, TaskManager]) => ({ BackgroundTask, Network, TaskManager }))
    .catch(() => null);
  return nativeModules;
}

export async function initializeAutoDownloadTask() {
  const modules = await loadNativeModules();
  if (!modules || modules.TaskManager.isTaskDefined(AUTO_DOWNLOAD_TASK)) return Boolean(modules);
  const { BackgroundTask, Network, TaskManager } = modules;
  TaskManager.defineTask(AUTO_DOWNLOAD_TASK, async () => {
    try {
      const network = await Network.getNetworkStateAsync();
      if (network.type !== Network.NetworkStateType.WIFI || !network.isConnected) {
        return BackgroundTask.BackgroundTaskResult.Success;
      }
      const { data: { session } } = await supabase.auth.getSession();
      if (!session || session.user.is_anonymous) return BackgroundTask.BackgroundTaskResult.Success;
      const [{ profile }, { briefing }] = await Promise.all([getMyPreferences(), getSavedTodayBriefing()]);
      if (!profile.auto_download_wifi || !briefing?.audio_url || briefing.status !== 'ready') {
        return BackgroundTask.BackgroundTaskResult.Success;
      }
      const cache = getOfflineAudio(session.user.id);
      if (!(await cache.list()).some(item => item.id === briefing.id)) await cache.save(briefing);
      return BackgroundTask.BackgroundTaskResult.Success;
    } catch {
      return BackgroundTask.BackgroundTaskResult.Failed;
    }
  });
  return true;
}

export async function configureAutoDownload(enabled: boolean) {
  const available = await initializeAutoDownloadTask();
  const modules = await loadNativeModules();
  if (!available || !modules) return false;
  const registered = await modules.TaskManager.isTaskRegisteredAsync(AUTO_DOWNLOAD_TASK);
  if (enabled && !registered) await modules.BackgroundTask.registerTaskAsync(AUTO_DOWNLOAD_TASK, { minimumInterval: 60 });
  if (!enabled && registered) await modules.BackgroundTask.unregisterTaskAsync(AUTO_DOWNLOAD_TASK);
  return true;
}
