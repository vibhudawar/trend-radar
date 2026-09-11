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

  // Once the DB reflects a started/terminal state, drop the local bridge and let status drive.
  useEffect(() => {
    if (status === "running" || status === "ready" || status === "failed") setBusy(false);
  }, [status]);

  // Poll while a run is expected — during the just-clicked bridge (busy) AND while status is
  // "running" — so we catch the status flip (the worker sets it a beat after the 202) and keep
  // results fresh, even when Realtime isn't delivering. `running` covers both.
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => router.refresh(), 5000);
    return () => clearInterval(t);
  }, [running, router]);

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
    // fallback: if the run never even registers as running (worker unreachable), stop the spinner.
    // The worker sets "running" within ~1-2s, so 45s only trips on a genuinely dead run.
    if (safety.current) clearTimeout(safety.current);
    safety.current = setTimeout(() => setBusy(false), 45000);
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
