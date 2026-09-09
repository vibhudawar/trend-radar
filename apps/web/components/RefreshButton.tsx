"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import { refreshProjectAction } from "@/app/actions";
import { Button } from "@/components/ui/button";

// Manual refresh (BACKEND.md §3). Triggers the worker, then revalidates while running.
// Supabase Realtime (RealtimeRefresh) pushes live updates; this polling is the fallback.
export function RefreshButton({ projectId, status }: { projectId: string; status: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false); // just-clicked, before status flips to "running"
  const [err, setErr] = useState<string | null>(null);
  const safety = useRef<ReturnType<typeof setTimeout> | null>(null);
  const running = busy || status === "running";

  // Once the worker has actually marked the run "running", let status drive the state.
  useEffect(() => {
    if (status === "running") setBusy(false);
  }, [status]);

  // Poll while a run is in progress so concepts/status stay fresh (Realtime is primary).
  useEffect(() => {
    if (status !== "running") return;
    const t = setInterval(() => router.refresh(), 8000);
    return () => clearInterval(t);
  }, [status, router]);

  useEffect(() => () => { if (safety.current) clearTimeout(safety.current); }, []);

  async function go() {
    setBusy(true);
    setErr(null);
    const r = await refreshProjectAction(projectId);
    if (!r.ok) {
      setErr(r.error ?? "failed");
      setBusy(false);
      return;
    }
    router.refresh(); // pick up status="running"
    // fallback: if status never flips (worker died), don't stay disabled forever
    if (safety.current) clearTimeout(safety.current);
    safety.current = setTimeout(() => setBusy(false), 15000);
  }

  return (
    <div className="flex items-center gap-2.5">
      <Button onClick={go} disabled={running}>
        {running ? <><Loader2 className="size-4 animate-spin" /> Analyzing…</> : "Refresh"}
      </Button>
      {running ? (
        <span className="text-muted-foreground text-xs">
          Finding winning videos — this takes a minute. Results appear automatically.
        </span>
      ) : null}
      {err ? <span className="text-amber-400 text-xs">{err}</span> : null}
    </div>
  );
}
