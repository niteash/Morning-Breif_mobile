import { apiRequest } from "../lib/api";
import { loadOptionalPreferences, type Preferences, type SelectedCategory } from "../lib/onboarding";

export async function getMyPreferences() {
  return apiRequest("/api/v1/users/me/preferences") as Promise<{ profile: Preferences }>;
}

export const getOptionalPreferences = () => loadOptionalPreferences(getMyPreferences);

export async function updateMyPreferences(data: {
  timezone?: string;
  delivery_hour?: number;
  delivery_minute?: number;
  automatic_briefing_enabled?: boolean;
  daily_reminder_enabled?: boolean;
  auto_play_when_open?: boolean;
  delivery_schedule?: 'daily' | 'weekdays';
  briefing_length?: 'quick' | 'standard' | 'detailed';
  weekend_delivery_hour?: number;
  weekend_delivery_minute?: number;
  separate_weekend_schedule?: boolean;
  breaking_news_enabled?: boolean;
  data_saver_enabled?: boolean;
  auto_download_wifi?: boolean;
  listening_streak_enabled?: boolean;
  horoscope_sign?: 'aries' | 'taurus' | 'gemini' | 'cancer' | 'leo' | 'virgo' | 'libra' | 'scorpio' | 'sagittarius' | 'capricorn' | 'aquarius' | 'pisces' | null;
  crypto_watchlist?: ('BTC' | 'ETH' | 'SOL' | 'XRP' | 'BNB' | 'DOGE' | 'ADA' | 'AVAX' | 'DOT' | 'LINK')[];
}) {
  return apiRequest("/api/v1/users/me/preferences", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function updateMyProfile(data: {
  name?: string | null;
  phone_number?: string | null;
  avatar_path?: string | null;
}) {
  return apiRequest("/api/v1/users/me/profile", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function getMyCategories() {
  return apiRequest("/api/v1/users/me/categories") as Promise<{ categories: SelectedCategory[] }>;
}

export async function updateMyCategories(categoryIds: string[]) {
  return apiRequest("/api/v1/users/me/categories", {
    method: "PUT",
    body: JSON.stringify({
      category_ids: categoryIds,
    }),
  });
}

export function updateListeningProgress(data: { briefing_id: string; position_seconds: number; listened_seconds: number; completed: boolean }) {
  return apiRequest('/api/v1/users/me/listening-progress', { method: 'PUT', body: JSON.stringify(data) });
}

export function getListeningSummary() {
  return apiRequest('/api/v1/users/me/listening-summary') as Promise<{ minutes: number; completed_briefings: number; streak_days: number }>;
}
