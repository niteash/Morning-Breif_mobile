import { apiRequest } from "../lib/api";

export type NewsItem = {
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

export async function getNews(params?: {
  category_id?: string;
  limit?: number;
}) {
  const query = new URLSearchParams();

  if (params?.category_id) {
    query.set("category_id", params.category_id);
  }

  if (params?.limit) {
    query.set("limit", String(params.limit));
  }

  const queryString = query.toString();

  return apiRequest(
    `/api/v1/news${queryString ? `?${queryString}` : ""}`,
  ) as Promise<{
    news: NewsItem[];
  }>;
}
