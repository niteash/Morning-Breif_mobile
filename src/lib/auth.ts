import { supabase } from "./supabase";

export async function ensureAuthenticated() {
  const { data: { session }, error } = await supabase.auth.getSession();
  if (error) throw error;
  if (!session || session.user.is_anonymous) throw new Error("Please sign in with your phone number.");
  return session;
}
