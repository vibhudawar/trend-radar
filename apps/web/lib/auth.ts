import { redirect } from "next/navigation";
import { supabaseServer } from "@/lib/supabase/server";

/** Current authenticated user's id, or null if not signed in / Supabase not configured. */
export async function currentUserId(): Promise<string | null> {
  try {
    const supabase = await supabaseServer();
    const { data } = await supabase.auth.getUser();
    return data.user?.id ?? null;
  } catch {
    return null;
  }
}

/** Require a signed-in user; redirect to /login otherwise. Returns the user id. */
export async function requireUserId(): Promise<string> {
  const id = await currentUserId();
  if (!id) redirect("/login");
  return id;
}
