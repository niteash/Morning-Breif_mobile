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

export type NewsPage = { news: NewsItem[]; next_offset: number | null };
export function discoverNews(params: { q?: string; category_id?: string; offset?: number; selected_only?: boolean } = {}) {
  const query = new URLSearchParams({ limit: '20', offset: String(params.offset || 0) });
  if (params.q?.trim()) query.set('q', params.q.trim());
  if (params.category_id) query.set('category_id', params.category_id);
  if (params.selected_only) query.set('selected_only', 'true');
  return apiRequest(`/api/v1/news/discover?${query}`) as Promise<NewsPage>;
}
export const getArticle = (id: string) => apiRequest(`/api/v1/news/${encodeURIComponent(id)}`) as Promise<{ article: NewsItem }>;
export const getBookmark = (id: string) => apiRequest(`/api/v1/bookmarks/${encodeURIComponent(id)}`) as Promise<{ saved: boolean }>;
export const setBookmark = (id: string, saved: boolean) => apiRequest(`/api/v1/bookmarks/${encodeURIComponent(id)}`, { method: saved ? 'PUT' : 'DELETE' }) as Promise<{ saved: boolean }>;
export const getBookmarks = (offset = 0) => apiRequest(`/api/v1/bookmarks?offset=${offset}&limit=20`) as Promise<{ bookmarks: { article_id: string; article: NewsItem | null }[]; next_offset: number | null }>;
export type StoryFeedbackAction = 'more_like_this' | 'less_like_this' | 'hide_topic' | 'hide_publisher' | 'report_incorrect';
export const setStoryFeedback = (id: string, action: StoryFeedbackAction, reason?: string) => apiRequest(`/api/v1/news/${encodeURIComponent(id)}/feedback`, {
  method: 'PUT', body: JSON.stringify({ action, reason }),
}) as Promise<{ saved: boolean }>;
