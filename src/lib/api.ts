import { supabase } from "./supabase";

const API_URL = process.env.EXPO_PUBLIC_API_URL!;

export async function apiRequest(path: string, options: RequestInit = {}) {
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.access_token) {
    throw new Error("User is not authenticated");
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session.access_token}`,
      ...(options.headers || {}),
    },
  });

  const contentType = response.headers.get("content-type");

  const data = contentType?.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    console.error("API ERROR STATUS:", response.status);
    console.error("API ERROR RESPONSE:", data);

    let message = `API request failed: ${response.status}`;

    if (typeof data === "object" && data !== null) {
      if ("detail" in data) {
        message =
          typeof data.detail === "string"
            ? data.detail
            : JSON.stringify(data.detail);
      } else {
        message = JSON.stringify(data);
      }
    } else if (typeof data === "string" && data) {
      message = data;
    }

    throw new Error(message);
  }

  return data;
}
