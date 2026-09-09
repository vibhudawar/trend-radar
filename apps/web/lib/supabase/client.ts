"use client";

import { createBrowserClient } from "@supabase/ssr";

// Browser client — used ONLY for Realtime subscriptions (live concept updates).
// Public URL + publishable key; RLS restricts what it can read.
export function supabaseBrowser() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
  );
}
