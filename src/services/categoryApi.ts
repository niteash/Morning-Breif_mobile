import { apiRequest } from "../lib/api";

export async function getCategories() {
  return apiRequest("/api/v1/categories");
}
