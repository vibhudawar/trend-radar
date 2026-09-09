"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { supabaseBrowser } from "@/lib/supabase/client";

// Live updates (#2): subscribe to this project's concepts + status changes and revalidate the
// server components when the worker writes. Requires Realtime enabled on the tables + RLS.
export function RealtimeRefresh({ projectId }: { projectId: string }) {
  const router = useRouter();
  useEffect(() => {
    if (!process.env.NEXT_PUBLIC_SUPABASE_URL) return;
    const supabase = supabaseBrowser();
    const channel = supabase
      .channel(`project-${projectId}`)
      .on("postgres_changes",
        { event: "*", schema: "public", table: "concepts", filter: `project_id=eq.${projectId}` },
        () => router.refresh())
      .on("postgres_changes",
        { event: "UPDATE", schema: "public", table: "projects", filter: `id=eq.${projectId}` },
        () => router.refresh())
      .subscribe();
    return () => { supabase.removeChannel(channel); };
  }, [projectId, router]);
  return null;
}
