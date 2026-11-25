import type { SourceMetadata } from '../components/BriefingSources';
import type { BriefingChapter } from '../services/briefingApi';
/** Client playback coordination. No networking or native module imports: exercised offline. */
export type Recording = {
  source_metadata?: SourceMetadata | null;
  id: string; user_id: string; briefing_date: string; status: string;
  script: string | null; audio_url: string | null; generated_at: string | null;
  duration_seconds: number | null; offline?: boolean;
  chapters?: BriefingChapter[] | null;
};
export type Availability = 'loading' | 'absent' | 'pending' | 'generating' | 'ready' | 'failed' | 'audio-unavailable';
export function availability(record: Recording | null, loading: boolean): Availability {
  if (loading && !record) return 'loading';
  if (!record) return 'absent';
  if (record.status === 'ready') return record.audio_url ? 'ready' : 'audio-unavailable';
  if (record.status === 'pending' || record.status === 'generating' || record.status === 'failed') return record.status;
  return 'audio-unavailable';
}
export function assetIdentity(record: Recording): string {
  let path = record.audio_url || '';
  try { const url = new URL(path); path = url.origin + url.pathname; } catch { path = path.split('?')[0]; }
  return `${record.user_id}|${record.id}|${record.briefing_date}|${record.generated_at || ''}|${path}`;
}
export function clockTime(seconds: number) {
  const value = Number.isFinite(seconds) ? Math.max(0, Math.floor(seconds)) : 0;
  return `${Math.floor(value / 60)}:${String(value % 60).padStart(2, '0')}`;
}
export function storyChapters(record: Recording | null) {
  return (record?.chapters ?? []).filter(chapter => chapter.type === 'story');
}
export function activeStory(record: Recording | null, position: number) {
  const chapters = storyChapters(record);
  return chapters.find(chapter => position >= chapter.start_seconds && position < chapter.end_seconds)
    ?? chapters.at(-1) ?? null;
}
export function localDay(timezone: string, now = new Date()) {
  try { return new Intl.DateTimeFormat('en-CA', { timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit' }).format(now); }
  catch { return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Yangon', year: 'numeric', month: '2-digit', day: '2-digit' }).format(now); }
}
export type PlaybackSnapshot = {
  record: Recording | null; position: number; duration: number; playing: boolean; intentPlaying: boolean;
  loading: boolean; refreshing: boolean; buffering: boolean; error: string | null; rate: number;
};
export type AudioPort = {
  prepare(): Promise<void>; load(url: string): Promise<void>; cancelLoad(): void;
  play(): void; pause(): void; seek(seconds: number): Promise<void>; rate(value: number): void;
  stop(): void;
  metadata?(value: { title: string; artist: string; artworkUrl?: string }): void;
};
export function createPlayback(owner: string, audio: AudioPort, fetchCurrent: (selected: Recording) => Promise<Recording | null>, now = Date.now) {
  let snapshot: PlaybackSnapshot = { record: null, position: 0, duration: 0, playing: false, intentPlaying: false, loading: false, refreshing: false, buffering: false, error: null, rate: 1 };
  let epoch = 0, disposed = false, fetchedAt = 0, loaded = false, activeChapterId: string | null = null;
  let refreshPromise: Promise<void> | undefined;
  const listeners = new Set<() => void>();
  const publish = (patch: Partial<PlaybackSnapshot>) => { snapshot = { ...snapshot, ...patch }; listeners.forEach(fn => fn()); };
  const valid = (version: number) => !disposed && epoch === version;
  const fail = (message: string) => {
    audio.pause();
    publish({ error: message, loading: false, intentPlaying: false, playing: false });
  };
  async function replace(record: Recording, preserve: boolean, version: number) {
    if (!record.audio_url || record.status !== 'ready' || record.user_id !== owner) throw Error('Audio is unavailable.');
    loaded = false;
    publish({ loading: true, playing: false, record, position: preserve ? snapshot.position : 0, duration: record.duration_seconds || 0, error: null });
    activeChapterId = null;
    audio.cancelLoad();
    audio.pause();
    await audio.prepare();
    if (!valid(version)) return;
    await audio.load(record.audio_url);
    if (!valid(version)) return;
    // Read the latest desired position and intent, not the values captured before a refresh.
    await audio.seek(snapshot.position);
    if (!valid(version)) return;
    audio.rate(snapshot.rate);
    fetchedAt = now();
    loaded = true;
    const shouldPlay = snapshot.intentPlaying;
    publish({ loading: false });
    if (shouldPlay) audio.play();
  }
  const api = {
    getSnapshot: () => snapshot,
    activate() { disposed = false; },
    subscribe(fn: () => void) { listeners.add(fn); return () => { listeners.delete(fn); }; },
    async select(record: Recording, autoplay = true, restart = false) {
      if (disposed || record.user_id !== owner) return;
      if (record.status !== 'ready' || !record.audio_url) { publish({ error: 'အသံဖိုင် မရရှိသေးပါ။ ပြန်လည်စစ်ဆေးပါ။' }); return; }
      const sameAsset = Boolean(snapshot.record && assetIdentity(record) === assetIdentity(snapshot.record));
      if (sameAsset && (loaded || snapshot.loading) && !snapshot.error) {
        if (restart) await api.seek(0);
        if (autoplay) await api.play();
        return;
      }
      const version = ++epoch;
      refreshPromise = undefined;
      publish({ intentPlaying: autoplay, refreshing: false });
      try { await replace(record, sameAsset, version); }
      catch { if (valid(version)) fail('အသံဖိုင် ဖွင့်မရသေးပါ။ ပြန်ကြိုးစားပါ။'); }
    },
    pause() {
      if (disposed) return;
      publish({ intentPlaying: false, playing: false });
      audio.pause();
    },
    async play() {
      if (disposed || !snapshot.record) return;
      const version = epoch;
      publish({ intentPlaying: true, error: null });
      if (snapshot.loading || snapshot.refreshing) return;
      if (!loaded || (!snapshot.record.offline && now() - fetchedAt > 50 * 60_000)) { await api.refresh(); return; }
      try {
        if (snapshot.duration > 0 && snapshot.position >= snapshot.duration) await api.seek(0);
        if (valid(version) && snapshot.intentPlaying) audio.play();
      } catch { if (valid(version)) fail('အသံဖွင့်မရပါ။ အသံလင့်ခ်ကို ပြန်ရယူပါ။'); }
    },
    async seek(seconds: number) {
      if (disposed || !snapshot.record) return;
      const version = epoch;
      const position = Math.max(0, Math.min(snapshot.duration || 0, seconds));
      publish({ position });
      if (snapshot.loading) return;
      try { await audio.seek(position); } catch { if (valid(version)) publish({ error: 'ရွေးထားသည့်နေရာသို့ ရွှေ့မရပါ။' }); }
    },
    setRate(rate: number) {
      if (disposed || ![0.75, 1, 1.25, 1.5, 2].includes(rate)) return;
      try { audio.rate(rate); publish({ rate }); } catch { publish({ error: 'နားဆင်နှုန်း ပြောင်းမရသေးပါ။' }); }
    },
    clear() {
      if (disposed) return;
      epoch++; loaded = false; refreshPromise = undefined; activeChapterId = null;
      audio.cancelLoad(); audio.stop();
      publish({ record: null, position: 0, duration: 0, playing: false, intentPlaying: false,
        loading: false, refreshing: false, buffering: false, error: null });
    },
    refresh(): Promise<void> {
      if (disposed || !snapshot.record) return Promise.resolve();
      if (refreshPromise) return refreshPromise;
      if (snapshot.loading) return Promise.resolve();
      const version = epoch, identity = assetIdentity(snapshot.record);
      publish({ refreshing: true, error: null });
      const request = (async () => {
        try {
          const record = snapshot.record!.offline ? snapshot.record : await fetchCurrent(snapshot.record!);
          if (!valid(version)) return;
          if (!record || record.user_id !== owner || !record.audio_url || record.status !== 'ready') throw Error('Unavailable');
          // Never silently swap the selected day or a regenerated asset.
          if (assetIdentity(record) !== identity) {
            publish({ intentPlaying: snapshot.playing, error: 'အသံဖိုင်အသစ် ရှိနိုင်ပါသည်။ ပင်မစာမျက်နှာမှ ရွေးချယ်နားဆင်ပါ။' });
            return;
          }
          await replace(record, true, version);
        } catch { if (valid(version)) fail('အသံလင့်ခ် ပြန်ရယူမရပါ။ အင်တာနက်ကို စစ်ပြီး ပြန်ကြိုးစားပါ။'); }
        finally { if (valid(version)) publish({ refreshing: false }); }
      })();
      refreshPromise = request;
      void request.finally(() => { if (refreshPromise === request) refreshPromise = undefined; });
      return request;
    },
    status(status: { currentTime: number; duration: number; playing: boolean; isBuffering: boolean; isLoaded: boolean; didJustFinish?: boolean; error?: unknown }) {
      if (disposed || snapshot.loading || !snapshot.record) return;
      const nativePaused = snapshot.playing && !status.playing;
      publish({ position: status.currentTime, duration: status.duration || snapshot.duration, playing: status.playing, buffering: status.isBuffering,
        intentPlaying: status.didJustFinish || nativePaused ? false : status.playing || snapshot.intentPlaying,
        ...(status.error ? { error: 'အသံဖိုင် မရရှိပါ။ အသံလင့်ခ်ကို ပြန်ရယူပါ။', intentPlaying: false } : {}),
      });
      const chapter = activeStory(snapshot.record, status.currentTime);
      if (chapter && chapter.id !== activeChapterId) {
        activeChapterId = chapter.id;
        audio.metadata?.({ title: chapter.title, artist: `${chapter.category_name || 'နေ့သစ်'} · ${chapter.publisher || 'သတင်းအနှစ်ချုပ်'}`, artworkUrl: chapter.image_url || undefined });
      }
    },
    dispose() {
      if (disposed) return;
      disposed = true; epoch++; loaded = false; refreshPromise = undefined; audio.cancelLoad(); audio.stop();
      publish({ record: null, playing: false, intentPlaying: false, loading: false, refreshing: false }); listeners.clear();
    },
  };
  return api;
}
