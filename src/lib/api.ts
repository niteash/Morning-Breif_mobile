import { supabase } from "./supabase";
import { requestJson } from "./http";
import { authenticatedRequest, type SessionResult } from "./authenticatedRequest";

const API_URL = process.env.EXPO_PUBLIC_API_URL?.trim().replace(/\/+$/, "");

export async function apiRequest(path: string, options: RequestInit = {}, expectedUserId?: string) {
  if (!API_URL || !/^https?:\/\//.test(API_URL)) throw new Error("The service address is not configured.");
  const readSession = async (): Promise<SessionResult> => {
    const { data: { session }, error } = await supabase.auth.getSession();
    return { session, error };
  };
  try {
    const result = await authenticatedRequest({
      path,
      method: options.method || "GET",
      expectedUserId,
      getSession: readSession,
      refreshSession: async () => {
        const { data: { session }, error } = await supabase.auth.refreshSession();
        return { session, error };
      },
      send: async (session, requestId) => {
        const headers = new Headers(options.headers);
        headers.set("Content-Type", "application/json");
        headers.set("Authorization", `Bearer ${session.access_token}`);
        headers.set("X-Request-ID", requestId);
        try {
          return { status: 200, value: await requestJson(`${API_URL}${path}`, { ...options, headers }, path.endsWith("/generate") ? 240_000 : 30_000) };
        } catch (error) {
          if (error && typeof error === "object" && "status" in error && typeof error.status === "number") {
            return { status: error.status, error };
          }
          throw error;
        }
      },
      onDiagnostic: (event) => console.warn("API authentication diagnostic", event),
    });
    if ("error" in result) throw result.error;
    return result.value;
  } catch (error) {
    if (error instanceof Error && /cancelled or timed out/i.test(error.message)) {
      // Route/method only; do not emit the API host, account or bearer token.
      throw new Error(`Staging API request timed out (${options.method || "GET"} ${path}). Check that the staging API is running and reachable from this device.`);
    }
    throw error;
  }
}
