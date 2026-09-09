import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

// Supabase server client (uses the public URL + publishable/anon key + the user's session cookies).
// RLS enforces access; this key is safe to be public.
export async function supabaseServer() {
  const cookieStore = await cookies();
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
    {
      cookies: {
        getAll: () => cookieStore.getAll(),
        setAll: (list) => {
          try {
            list.forEach(({ name, value, options }) => cookieStore.set(name, value, options));
          } catch {
            /* called from a Server Component — middleware refreshes the session instead */
          }
        },
      },
    },
  );
}
