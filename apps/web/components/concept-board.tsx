"use client";

import { useState } from "react";
import {
  ChevronRight, Clapperboard, Lightbulb, PlayCircle, ShieldCheck, Sparkles, TrendingUp, Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

export type Beat = { t?: string; action?: string };
export type ConceptView = {
  id: string;
  lane: "rising" | "proven";
  name: string;
  confidence: "high" | "medium" | "emerging";
  lifecycle: string;
  nVideos: number;
  nCreators: number;
  medianOutperformance: string | null;
  adaptedHook: string | null;
  format: string | null;
  lengthS: number | null;
  testTarget: string | null;
  script: Beat[];
  videos: { handle: string | null; url: string; hook: string | null }[];
};

const CONF: Record<string, string> = {
  high: "bg-emerald-500/15 text-emerald-500 border-emerald-500/25",
  medium: "bg-blue-500/15 text-blue-500 border-blue-500/25",
  emerging: "bg-amber-500/15 text-amber-500 border-amber-500/25",
};
const CONF_RANK: Record<string, number> = { high: 3, medium: 2, emerging: 1 };

const LANE_COPY = {
  rising: {
    icon: <TrendingUp className="size-4" />,
    hint: "Fresh trends gaining steam. Post these fast to ride the wave before everyone copies it.",
    pick: { label: "Act this week", icon: <Zap className="size-3.5" /> },
  },
  proven: {
    icon: <Sparkles className="size-4" />,
    hint: "Formats that have worked again and again. Safe to copy anytime — reliable results.",
    pick: { label: "Safest bet", icon: <ShieldCheck className="size-3.5" /> },
  },
} as const;

export function ConceptBoard({ rising, proven }: { rising: ConceptView[]; proven: ConceptView[] }) {
  return (
    <div>
      {/* how-to banner */}
      <div className="bg-muted/40 mb-4 flex items-start gap-2.5 rounded-lg border p-3">
        <Lightbulb className="text-primary mt-0.5 size-4 shrink-0" />
        <p className="text-muted-foreground text-sm leading-relaxed">
          <span className="text-foreground font-medium">Which video should you make?</span>{" "}
          <span className="text-foreground font-medium">Proven playbook</span> = reliable formats, safe to copy.{" "}
          <span className="text-foreground font-medium">Rising now</span> = fresh trends — post fast to catch the wave.
          New here? Start with the <span className="text-foreground font-medium">Safest bet</span>, then test a Rising one.
        </p>
      </div>

      <Tabs defaultValue={rising.length || !proven.length ? "rising" : "proven"} className="w-full">
        <TabsList>
          <TabsTrigger value="rising">
            <TrendingUp className="size-4" /> Rising now
            <span className="text-muted-foreground ml-1 text-xs">{rising.length}</span>
          </TabsTrigger>
          <TabsTrigger value="proven">
            <Sparkles className="size-4" /> Proven playbook
            <span className="text-muted-foreground ml-1 text-xs">{proven.length}</span>
          </TabsTrigger>
        </TabsList>
        <TabsContent value="rising" className="mt-4"><Lane lane="rising" items={rising} /></TabsContent>
        <TabsContent value="proven" className="mt-4"><Lane lane="proven" items={proven} /></TabsContent>
      </Tabs>
    </div>
  );
}

function Lane({ lane, items }: { lane: "rising" | "proven"; items: ConceptView[] }) {
  const copy = LANE_COPY[lane];
  if (items.length === 0) {
    return (
      <Card className="p-10 text-center">
        <p className="text-sm font-medium">No proven pattern here yet</p>
        <p className="text-muted-foreground mx-auto mt-1 max-w-md text-sm">
          We only surface hooks backed by multiple winning videos across at least two creators — no anecdotes.
          Add more competitor accounts, broaden the keywords, or run with a higher cap to widen the net.
        </p>
      </Card>
    );
  }
  // strongest concept = the recommended pick for this lane
  const sorted = [...items].sort(
    (a, b) => (CONF_RANK[b.confidence] - CONF_RANK[a.confidence]) || (b.nVideos - a.nVideos),
  );
  const recommendedId = sorted[0]?.id;

  return (
    <div className="flex flex-col gap-4">
      <p className="text-muted-foreground text-sm">{copy.hint}</p>
      {sorted.map((c) => (
        <ConceptCard key={c.id} c={c} recommend={c.id === recommendedId ? copy.pick : null} />
      ))}
    </div>
  );
}

function ConceptCard({ c, recommend }: {
  c: ConceptView;
  recommend: { label: string; icon: React.ReactNode } | null;
}) {
  const [showScript, setShowScript] = useState(false);
  const [showVideos, setShowVideos] = useState(false);

  return (
    <Card className={cn("gap-4 p-5", recommend && "ring-primary/40 ring-2")}>
      {recommend ? (
        <div className="text-primary -mt-1 flex items-center gap-1.5 text-xs font-semibold">
          {recommend.icon} {recommend.label}
          <span className="text-muted-foreground font-normal">· start with this one</span>
        </div>
      ) : null}

      <div className="flex items-start justify-between gap-3">
        <h3 className="text-base font-semibold leading-snug">{c.name}</h3>
        <div className="flex shrink-0 gap-1.5">
          <Badge variant="outline" className={cn("capitalize", CONF[c.confidence])}>{c.confidence} confidence</Badge>
          <Badge variant="outline" className="capitalize">{c.lifecycle}</Badge>
        </div>
      </div>

      <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm">
        <Stat label="creators used it" value={String(c.nCreators)} />
        <Stat label="winning videos" value={String(c.nVideos)} />
        {c.medianOutperformance ? <Stat label="above the creator's norm" value={c.medianOutperformance} highlight /> : null}
      </div>

      {c.adaptedHook ? (
        <div className="border-primary/20 bg-primary/5 rounded-lg border p-4">
          <div className="text-primary flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide">
            <Sparkles className="size-3.5" /> Your hook — say this in the first 2 seconds
          </div>
          <p className="mt-1.5 text-[15px] font-medium leading-snug">“{c.adaptedHook}”</p>
          <div className="text-muted-foreground mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs">
            {c.format ? <span className="capitalize">{c.format}</span> : null}
            {c.lengthS ? <span>· {c.lengthS}s long</span> : null}
            {c.testTarget ? <span>· 🎯 aim for: {c.testTarget}</span> : null}
          </div>
        </div>
      ) : null}

      <div className="flex flex-col divide-y">
        {c.script.length > 0 ? (
          <Disclosure open={showScript} onToggle={() => setShowScript((v) => !v)}
            icon={<Clapperboard className="size-4" />} label={`Shoot-ready script (${c.script.length} steps)`}>
            <ol className="mt-2 space-y-2">
              {c.script.map((b, i) => (
                <li key={i} className="flex gap-3 text-sm">
                  <span className="bg-muted text-muted-foreground mt-0.5 h-fit rounded px-1.5 py-0.5 font-mono text-[11px]">{b.t}</span>
                  <span className="leading-snug">{b.action}</span>
                </li>
              ))}
            </ol>
          </Disclosure>
        ) : null}

        {c.videos.length > 0 ? (
          <Disclosure open={showVideos} onToggle={() => setShowVideos((v) => !v)}
            icon={<PlayCircle className="size-4" />} label={`Proof — the winning videos (${c.videos.length})`}>
            <p className="text-muted-foreground mt-2 text-xs">
              Real videos that beat their creator's own average with this hook structure. Your hook above reworks it for your product.
            </p>
            <ul className="mt-2 flex flex-col gap-2">
              {c.videos.map((v, i) => (
                <li key={i} className="bg-muted/40 rounded-lg border p-2.5">
                  {v.hook ? <p className="text-[13px] leading-snug">“{v.hook}”</p> : null}
                  <a href={v.url} target="_blank" rel="noreferrer"
                    className="text-muted-foreground hover:text-foreground mt-1 inline-flex items-center gap-1 text-xs font-medium transition-colors">
                    @{v.handle ?? "creator"} — watch <PlayCircle className="size-3.5 opacity-70" />
                  </a>
                </li>
              ))}
            </ul>
          </Disclosure>
        ) : null}
      </div>
    </Card>
  );
}

function Stat({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <span className="flex items-baseline gap-1">
      <span className={cn("font-semibold", highlight && "text-primary")}>{value}</span>
      <span className="text-muted-foreground text-xs">{label}</span>
    </span>
  );
}

function Disclosure({ open, onToggle, icon, label, children }: {
  open: boolean; onToggle: () => void; icon: React.ReactNode; label: string; children: React.ReactNode;
}) {
  return (
    <div className="py-2 first:pt-0 last:pb-0">
      <button onClick={onToggle} className="hover:text-foreground text-muted-foreground flex w-full items-center gap-2 text-sm font-medium transition-colors">
        <ChevronRight className={cn("size-4 transition-transform", open && "rotate-90")} />
        {icon}
        {label}
      </button>
      {open ? children : null}
    </div>
  );
}
