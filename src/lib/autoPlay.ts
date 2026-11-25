import type { Recording } from './playback';

type Profile = {
  timezone?: string;
  delivery_hour?: number;
  delivery_minute?: number;
  delivery_schedule?: 'daily' | 'weekdays';
  auto_play_when_open?: boolean;
};

export function isForegroundAutoPlayDue(
  profile: Profile | null | undefined,
  record: Recording | null | undefined,
  accountId: string,
  appState: string,
  now = new Date(),
  autoPlayEnabled = false,
): boolean {
  if (!autoPlayEnabled) return false;
  if (appState !== 'active' || profile?.auto_play_when_open !== true || !record || record.user_id !== accountId) return false;
  if (record.status !== 'ready' || !record.audio_url || !profile.timezone) return false;
  try {
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone: profile.timezone, year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', hourCycle: 'h23', weekday: 'short',
    }).formatToParts(now);
    const values = Object.fromEntries(parts.map(part => [part.type, part.value]));
    const localDate = `${values.year}-${values.month}-${values.day}`;
    if (record.briefing_date !== localDate) return false;
    if (profile.delivery_schedule === 'weekdays' && ['Sat', 'Sun'].includes(values.weekday)) return false;
    const hour = profile.delivery_hour, minute = profile.delivery_minute;
    if (!Number.isInteger(hour) || !Number.isInteger(minute) || hour! < 0 || hour! > 23 || minute! < 0 || minute! > 59) return false;
    return Number(values.hour) * 60 + Number(values.minute) >= hour! * 60 + minute!;
  } catch {
    return false;
  }
}

export function createAutoPlayGate(storage: {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
}, environment: string) {
  const claiming = new Set<string>();
  const keyFor = (userId: string, briefingId: string) => `nay-thit:auto-play:v1:${environment}:${userId}:${briefingId}`;
  async function claim(userId: string, briefingId: string): Promise<boolean> {
    const key = keyFor(userId, briefingId);
    if (claiming.has(key)) return false;
    claiming.add(key);
    try {
      if (await storage.getItem(key)) return false;
      await storage.setItem(key, 'handled');
      return true;
    } catch {
      return false; // fail closed: storage errors must never cause repeated starts
    } finally {
      claiming.delete(key);
    }
  }
  async function markHandled(userId: string, briefingId: string): Promise<void> {
    const key = keyFor(userId, briefingId);
    try { await storage.setItem(key, 'handled'); } catch { /* Autoplay remains disabled by a later claim failure. */ }
  }
  return { claim, markHandled };
}
