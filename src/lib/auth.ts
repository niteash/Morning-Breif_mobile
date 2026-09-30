import { supabase } from "./supabase";

export async function ensureAuthenticated() {
  const {
    data: { session },
    error,
  } = await supabase.auth.getSession();

  if (error) {
    console.error("SESSION ERROR:", error);
    throw error;
  }

  if (!session) {
    throw new Error("No active session");
  }

  console.log("=================================");
  console.log("USER ID:", session.user.id);
  console.log("ACCESS TOKEN:", session.access_token);
  console.log("=================================");

  return session;
}
