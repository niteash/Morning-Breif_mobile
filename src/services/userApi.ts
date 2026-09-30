import { apiRequest } from "../lib/api";

export async function getMyPreferences() {
  return apiRequest("/api/v1/users/me/preferences");
}

export async function updateMyPreferences(data: {
  timezone: string;
  delivery_hour: number;
  delivery_minute: number;
}) {
  return apiRequest("/api/v1/users/me/preferences", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function getMyCategories() {
  return apiRequest("/api/v1/users/me/categories");
}

export async function updateMyCategories(categoryIds: string[]) {
  return apiRequest("/api/v1/users/me/categories", {
    method: "PUT",
    body: JSON.stringify({
      category_ids: categoryIds,
    }),
  });
}
