import { apiRequest } from "../lib/api";

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
  id: string;
  user_id: string;
  briefing_date: string;

  title: string;
  script: string;

  audio_url: string | null;
  duration_seconds: number | null;

  status: string;

  /*
   * Actual time when AI generated the briefing.
   */
  generated_at: string | null;

  created_at: string;
  updated_at: string;
};

/* ========================================================= */
/* GENERATED BRIEFING */
/* ========================================================= */

export type GeneratedBriefing = SavedBriefing & {
  categories: BriefingCategory[];
};

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

export async function generateBriefing(): Promise<{
  message: string;
  briefing: GeneratedBriefing;
}> {
  /*
   * Every generation gets a unique ID.
   *
   * This allows the backend/Gemini to know that
   * the user requested a fresh regeneration.
   */

  const regenerationId = `${Date.now()}-${Math.random()
    .toString(36)
    .substring(2, 10)}`;

  console.log("REGENERATION ID:", regenerationId);

  return apiRequest("/api/v1/briefings/generate", {
    method: "POST",

    body: JSON.stringify({
      regeneration_id: regenerationId,
    }),
  }) as Promise<{
    message: string;
    briefing: GeneratedBriefing;
  }>;
}
