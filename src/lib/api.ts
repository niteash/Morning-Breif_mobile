import { supabase } from "./supabase";

const API_URL = process.env.EXPO_PUBLIC_API_URL;

if (!API_URL) {
  console.error("EXPO_PUBLIC_API_URL is not configured");
}

export async function apiRequest(path: string, options: RequestInit = {}) {
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.access_token) {
    throw new Error("User is not authenticated");
  }

  const url = `${API_URL}${path}`;

  console.log("=================================");

  console.log("API REQUEST:");

  console.log("URL:", url);

  console.log("METHOD:", options.method || "GET");

  console.log("USER:", session.user.id);

  console.log("=================================");

  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${session.access_token}`,
        ...(options.headers || {}),
      },
    });

    console.log("API RESPONSE STATUS:", response.status);

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

    console.log("API REQUEST SUCCESS");

    return data;
  } catch (error) {
    console.error("=================================");

    console.error("API FETCH ERROR:");

    console.error(error);

    console.error("URL:", url);

    console.error("=================================");

    throw error;
  }
}
