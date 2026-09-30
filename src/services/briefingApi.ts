import { apiRequest } from "../lib/api";

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

export type BriefingCategory = {
  category: {
    id: string;
    slug: string;
    name_en: string;
    name_my: string;
  };
  stories: BriefingStory[];
};

export type TodayBriefing = {
  date: string;
  categories: BriefingCategory[];
};

export type SavedBriefing = {
  id: string;
  user_id: string;
  briefing_date: string;
  title: string;
  script: string;
  audio_url: string | null;
  duration_seconds: number | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type GeneratedBriefing = SavedBriefing & {
  generated_at: string;
  categories: BriefingCategory[];
};

export async function getTodayBriefing(): Promise<TodayBriefing> {
  return apiRequest("/api/v1/briefings/today") as Promise<TodayBriefing>;
}

export async function getSavedTodayBriefing(): Promise<{
  briefing: SavedBriefing | null;
}> {
  return apiRequest("/api/v1/briefings/today/saved") as Promise<{
    briefing: SavedBriefing | null;
  }>;
}

export async function generateBriefing(): Promise<{
  message: string;
  briefing: GeneratedBriefing;
}> {
  return apiRequest("/api/v1/briefings/generate", {
    method: "POST",
  }) as Promise<{
    message: string;
    briefing: GeneratedBriefing;
  }>;
}
