import type { SourceMetadata } from '../components/BriefingSources';
import { apiRequest } from "../lib/api";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { supabase } from "../lib/supabase";
import { createGenerationRequests } from "../lib/generationRequest";

/* ========================================================= */
/* STORY */
/* ========================================================= */

export type BriefingStory = {
  id: string;
  category_id: string;
  source: string;
  title: string;
  description: string | null;
  url: string;
  image_url: string | null;
  author: string | null;
  published_at: string | null;
  created_at: string;
};

/* ========================================================= */
/* CATEGORY */
/* ========================================================= */

export type BriefingCategory = {
  category: {
    id: string;
    slug: string;
    name_en: string;
    name_my: string;
  };

  stories: BriefingStory[];
};

/* ========================================================= */
/* TODAY'S STORY BRIEFING */
/* ========================================================= */

export type TodayBriefing = {
  date: string;
  categories: BriefingCategory[];
};

/* ========================================================= */
/* SAVED AI BRIEFING */
/* ========================================================= */

export type SavedBriefing = {
  source_metadata?: SourceMetadata | null;
  id: string;
  user_id: string;
  briefing_date: string;

  title: string;
  script: string | null;

  audio_url: string | null;
  duration_seconds: number | null;

  status: string;

  /*
   * Actual time when AI generated the briefing.
   */
  generated_at: string | null;

  created_at: string;
  updated_at: string;
  target_minutes?: number | null;
  chapters?: BriefingChapter[] | null;
};

export type BriefingChapter = {
  id: string; type: 'category' | 'story'; title: string;
  story_id?: string; category_name?: string | null; publisher?: string | null;
  url?: string | null; image_url?: string | null; published_at?: string | null;
  start_seconds: number; end_seconds: number;
};

/* ========================================================= */
/* GENERATED BRIEFING */
/* ========================================================= */

export type GeneratedBriefing = SavedBriefing;

/* ========================================================= */
/* GET TODAY'S STORY BRIEFING */
/* ========================================================= */

export async function getTodayBriefing(): Promise<TodayBriefing> {
  return apiRequest("/api/v1/briefings/today") as Promise<TodayBriefing>;
}

/* ========================================================= */
/* GET SAVED AI BRIEFING */
/* ========================================================= */

export async function getSavedTodayBriefing(): Promise<{
  briefing: SavedBriefing | null;
}> {
  return apiRequest("/api/v1/briefings/today/saved") as Promise<{
    briefing: SavedBriefing | null;
  }>;
}

/* ========================================================= */
/* GENERATE / REGENERATE AI BRIEFING */
/* ========================================================= */

export type GenerationJob = {
  id: string; user_id: string; briefing_date: string;
  length: 'quick' | 'standard' | 'detailed';
  state: 'queued' | 'selecting' | 'checking_sources' | 'writing' | 'synthesizing' | 'finalizing' | 'ready' | 'failed';
  progress: number; message: string | null; error_code: string | null;
  briefing_id: string | null; created_at: string; started_at: string | null;
  finished_at: string | null; updated_at: string;
};
export type GenerationResponse = { request: GenerationJob };

const generationLengths = new Map<string, 'quick' | 'standard' | 'detailed'>();
const generateRequest = createGenerationRequests<GenerationResponse>(
  AsyncStorage,
  () => `${Date.now()}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`,
  (regenerationId, userId) => apiRequest("/api/v1/briefings/requests", {
    method: "POST",
    body: JSON.stringify({ request_key: regenerationId, length: generationLengths.get(userId) ?? 'standard' }),
  }, userId),
);

export async function generateBriefing(length: 'quick' | 'standard' | 'detailed' = 'standard'): Promise<GenerationResponse> {
  const { data: { session }, error } = await supabase.auth.getSession();
  if (error || !session || session.user.is_anonymous) throw new Error("Please sign in to continue.");
  // The Supabase project identifies the data, even when a development tunnel changes.
  const environment = process.env.EXPO_PUBLIC_SUPABASE_URL!;
  generationLengths.set(session.user.id, length);
  try { return await generateRequest(environment, session.user.id); }
  finally { generationLengths.delete(session.user.id); }
}

export function getGenerationRequest(id: string): Promise<GenerationResponse> {
  return apiRequest(`/api/v1/briefings/requests/${encodeURIComponent(id)}`);
}

export type BriefingHistoryItem = Omit<SavedBriefing, 'script' | 'audio_url'>;
export function getBriefingHistory(offset = 0): Promise<{ briefings: BriefingHistoryItem[]; next_offset: number | null }> {
  return apiRequest(`/api/v1/briefings/history?offset=${offset}&limit=20`);
}
export function getHistoricalBriefing(id: string): Promise<{ briefing: SavedBriefing }> {
  return apiRequest(`/api/v1/briefings/history/${encodeURIComponent(id)}`);
}

export function reportPronunciation(id: string, phrase: string, notes?: string): Promise<{ accepted: boolean; report_id: string | null }> {
  return apiRequest(`/api/v1/briefings/${encodeURIComponent(id)}/pronunciation-reports`, {
    method: 'POST', body: JSON.stringify({ phrase, notes: notes?.trim() || null }),
  });
}
