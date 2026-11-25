export type Preferences = {
  id?: string;
  name?: string | null;
  phone_number?: string | null;
  avatar_path?: string | null;
  timezone: string;
  delivery_hour: number;
  delivery_minute: number;
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
  automatic_delivery_preferences_available?: boolean;
};

export type SelectedCategory = { category_id: string; categories: { id: string; name_my?: string; name_en?: string; slug?: string } | null };

// Only a missing profile means first-time setup. Preserve network/auth failures.
export async function loadOptionalPreferences(
  load: () => Promise<{ profile: Preferences }>,
): Promise<Preferences | null> {
  try {
    return (await load()).profile;
  } catch (error) {
    if (error instanceof Error && "status" in error && error.status === 404) return null;
    throw error;
  }
}

export async function needsOnboarding(
  loadProfile: () => Promise<Preferences | null>,
  loadCategories: () => Promise<{ categories: SelectedCategory[] }>,
): Promise<boolean> {
  const profile = await loadProfile();
  if (!profile) return true;
  const { categories } = await loadCategories();
  return !categories.some((item) => item.categories?.id === item.category_id);
}
