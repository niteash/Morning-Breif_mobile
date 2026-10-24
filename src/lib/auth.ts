import { supabase } from "./supabase";

export async function ensureAuthenticated() {
  console.log("=================================");
  console.log("CHECKING SUPABASE SESSION");
  console.log("=================================");

  const {
    data: { session },
    error: sessionError,
  } = await supabase.auth.getSession();

  if (sessionError) {
    console.error("SESSION CHECK ERROR:", sessionError);

    throw sessionError;
  }

  // -----------------------------------------
  // Existing session
  // -----------------------------------------

  if (session) {
    console.log("ACTIVE SESSION FOUND:", session.user.id);

    return session;
  }

  // -----------------------------------------
  // No session
  // Create anonymous session for development
  // -----------------------------------------

  console.log("NO ACTIVE SESSION");

  console.log("CREATING ANONYMOUS SESSION...");

  const { data, error } = await supabase.auth.signInAnonymously();

  if (error) {
    console.error("ANONYMOUS AUTH ERROR:", error);

    throw error;
  }

  if (!data.session) {
    throw new Error(
      "Anonymous authentication succeeded but no session was returned",
    );
  }

  console.log("ANONYMOUS SESSION CREATED:", data.user?.id);

  console.log("=================================");

  return data.session;
}
