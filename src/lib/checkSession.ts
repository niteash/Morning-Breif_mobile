// src/lib/checkSession.ts

import { supabase } from "./supabase";
import { apiRequest } from "./api";

interface SavedBriefing {
  id?: string;
  briefing_date?: string;
  status?: string;
  audio_url?: string | null;
}

interface SavedBriefingResponse {
  briefing: SavedBriefing | null;
}

export async function checkSupabaseSession(): Promise<boolean> {
  try {
    const {
      data: { session },
      error,
    } = await supabase.auth.getSession();

    if (error) {
      console.error("Session error:", error.message);
      return false;
    }

    if (!session?.access_token) {
      console.log("No active session. Please sign in first.");
      return false;
    }

    console.log("Authenticated user ID:", session.user.id);
    console.log("Access token available:", true);

    console.log(
      "Token expires at:",
      session.expires_at
        ? new Date(session.expires_at * 1000).toISOString()
        : "Unknown",
    );

    return true;
  } catch (error) {
    console.error("Failed to check Supabase session:", error);
    return false;
  }
}

export async function testBriefingAPI(): Promise<void> {
  console.log("=================================");
  console.log("MORNING BRIEF API TEST");
  console.log("=================================");

  try {
    const authenticated = await checkSupabaseSession();

    if (!authenticated) {
      console.error("API test stopped: user is not authenticated.");
      return;
    }

    console.log("Testing saved briefing endpoint...");

    const result = (await apiRequest(
      "/api/v1/briefings/today/saved",
    )) as SavedBriefingResponse;

    if (!result || typeof result !== "object") {
      console.error("Unexpected API response format.");
      return;
    }

    const briefing = result.briefing;

    if (!briefing) {
      console.log("API connection successful.");
      console.log("No saved briefing exists for today.");
      return;
    }

    console.log("API connection successful.");
    console.log("Saved briefing exists:", true);
    console.log("Briefing ID:", briefing.id ?? "Not provided");
    console.log("Briefing date:", briefing.briefing_date ?? "Unknown");
    console.log("Briefing status:", briefing.status ?? "Unknown");
    console.log("Audio URL available:", Boolean(briefing.audio_url));

    if (briefing.status === "ready" && briefing.audio_url) {
      console.log("SUCCESS: Saved briefing and audio URL are available.");
    } else {
      console.warn("Briefing exists, but its status or audio needs checking.");
    }
  } catch (error) {
    console.error("=================================");
    console.error("MORNING BRIEF API TEST FAILED");
    console.error(error instanceof Error ? error.message : error);
    console.error("=================================");
  }
}
