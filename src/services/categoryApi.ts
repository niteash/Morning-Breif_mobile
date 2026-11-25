import { apiRequest } from "../lib/api";

export async function getCategories() {
  return apiRequest("/api/v1/categories") as Promise<{ categories: { id: string; slug: string; name_my: string; name_en: string; active: boolean }[] }>;
}
