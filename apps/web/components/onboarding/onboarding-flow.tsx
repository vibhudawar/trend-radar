"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useFormStatus } from "react-dom";
import { ArrowRight, Loader2, Sparkles, Wand2 } from "lucide-react";
import { analyzeUrlAction, createProjectAction } from "@/app/actions";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { ChipsInput } from "./chips-input";

type Phase = "invite" | "analyzing" | "review";
const REGIONS = ["US", "IN", "UK", "CA", "AU", "Global"];
const PLATFORMS = [
  { id: "tiktok", label: "TikTok" },
  { id: "reels", label: "Instagram Reels" },
] as const;

const empty = {
  name: "", productDescription: "", audience: "", jobToBeDone: "", region: "",
  platforms: ["tiktok", "reels"] as string[],
  seedQueries: [] as string[], competitors: [] as string[], ownAccounts: [] as string[], competitorUrls: [] as string[],
};

export function OnboardingFlow() {
  const [phase, setPhase] = useState<Phase>("invite");
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [f, setF] = useState({ ...empty });
  const [suggestedCompetitors, setSuggestedCompetitors] = useState<string[]>([]);
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((p) => ({ ...p, [k]: v }));

  async function analyze(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim()) return;
    setError(null);
    setPhase("analyzing");
    const fd = new FormData();
    fd.set("url", url.trim());
    const res = await analyzeUrlAction(null, fd);
    if (res.ok) {
      const p = res.profile;
      setF((prev) => ({
        ...prev,
        name: p.name ?? "", productDescription: p.productDescription ?? "",
        audience: p.audience ?? "", jobToBeDone: p.jobToBeDone ?? "",
        platforms: p.platforms?.length ? p.platforms : prev.platforms,
        seedQueries: p.seedQueries ?? [],
      }));
      setSuggestedCompetitors(p.competitors ?? []);
      setPhase("review");
    } else {
      setError(res.error);
      setPhase("invite");
    }
  }

  if (phase === "invite" || phase === "analyzing") {
    return (
      <div className="mx-auto max-w-xl pt-6">
        <Link href="/" className="text-muted-foreground text-sm no-underline hover:underline">← Projects</Link>
        <div className="mt-8 text-center">
          <div className="bg-primary/10 text-primary mx-auto mb-4 flex size-12 items-center justify-center rounded-xl">
            <Wand2 className="size-6" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight">Onboard a business</h1>
          <p className="text-muted-foreground mx-auto mt-2 max-w-md text-sm leading-relaxed">
            Paste the product URL. We read the site and set up the whole profile — you just review.
          </p>
        </div>

        {phase === "invite" ? (
          <form onSubmit={analyze} className="mt-7">
            <div className="flex gap-2">
              <Input
                autoFocus
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://yourproduct.com"
                className="h-11 text-base"
                type="url"
              />
              <Button type="submit" size="lg" disabled={!url.trim()} className="shrink-0">
                <Sparkles className="size-4" /> Analyze
              </Button>
            </div>
            {error ? <p className="text-amber-400 mt-2 text-sm">{error}</p> : null}
            <p className="text-muted-foreground mt-3 text-center text-xs">Takes a few seconds · nothing is charged</p>
          </form>
        ) : (
          <AnalyzingCard url={url} />
        )}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl pb-16">
      <Link href="/" className="text-muted-foreground text-sm no-underline hover:underline">← Projects</Link>
      <div className="mt-3 mb-5 flex items-center gap-2">
        <div className="bg-emerald-500/15 text-emerald-500 flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium">
          <Sparkles className="size-3.5" /> Profile ready
        </div>
        <p className="text-muted-foreground text-sm">Review and edit — everything is yours to change.</p>
      </div>

      <form action={createProjectAction}>
        <input type="hidden" name="productUrl" value={url} />
        {f.platforms.map((p) => <input key={p} type="hidden" name="platforms" value={p} />)}
        {f.seedQueries.map((v) => <input key={`k${v}`} type="hidden" name="seedQueries" value={v} />)}
        {f.competitors.map((v) => <input key={`c${v}`} type="hidden" name="competitors" value={v} />)}
        {f.ownAccounts.map((v) => <input key={`o${v}`} type="hidden" name="ownAccounts" value={v} />)}
        {f.competitorUrls.map((v) => <input key={`u${v}`} type="hidden" name="competitorUrls" value={v} />)}

        <Card className="gap-0 divide-y p-0">
          <Section title="Business">
            <Field label="Business name" required>
              <Input name="name" value={f.name} onChange={(e) => set("name", e.target.value)} placeholder="e.g. Ecombox" />
            </Field>
            <Field label="What they sell" hint="Used to adapt hooks to this business">
              <Textarea name="productDescription" rows={2} value={f.productDescription}
                onChange={(e) => set("productDescription", e.target.value)} />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Audience"><Input name="audience" value={f.audience} onChange={(e) => set("audience", e.target.value)} /></Field>
              <Field label="Goal (job to be done)"><Input name="jobToBeDone" value={f.jobToBeDone} onChange={(e) => set("jobToBeDone", e.target.value)} /></Field>
            </div>
          </Section>

          <Section title="Targeting">
            <Field label="Region" required hint="Which market are your customers in? We only search where they are.">
              <input type="hidden" name="region" value={f.region} />
              <div className="flex flex-wrap gap-2">
                {REGIONS.map((r) => (
                  <Chip key={r} active={f.region === r} onClick={() => set("region", r)}>{r}</Chip>
                ))}
                <input
                  value={REGIONS.includes(f.region) ? "" : f.region}
                  onChange={(e) => set("region", e.target.value)}
                  placeholder="Custom…"
                  className="border-input focus:border-ring w-24 rounded-md border bg-transparent px-2 text-sm outline-none"
                />
              </div>
              {!f.region ? <p className="text-amber-400 mt-1.5 text-xs">Pick a region to continue.</p> : null}
            </Field>
            <Field label="Platforms">
              <div className="flex gap-2">
                {PLATFORMS.map((pl) => (
                  <Chip key={pl.id} active={f.platforms.includes(pl.id)}
                    onClick={() => set("platforms", f.platforms.includes(pl.id) ? f.platforms.filter((x) => x !== pl.id) : [...f.platforms, pl.id])}>
                    {f.platforms.includes(pl.id) ? "✓ " : ""}{pl.label}
                  </Chip>
                ))}
              </div>
            </Field>
            <Field label="Search keywords" hint="Short seeds we search for winning videos — keep them 2–4 words">
              <ChipsInput value={f.seedQueries} onChange={(v) => set("seedQueries", v)} placeholder="Add a keyword and press Enter" mono />
            </Field>
          </Section>

          <Section title="Competitors & accounts" subtitle="Optional — we learn from these and still surface creators you don't know yet.">
            <Field label="Competitor accounts" hint="Handles of rivals / niche creators to mine for winners">
              <ChipsInput value={f.competitors} onChange={(v) => set("competitors", v)} suggestions={suggestedCompetitors}
                prefix="@" placeholder="Add a handle" mono />
            </Field>
            <Advanced>
              <Field label="Your own accounts" hint="We learn your style and won't re-recommend what you already posted">
                <ChipsInput value={f.ownAccounts} onChange={(v) => set("ownAccounts", v)} prefix="@" placeholder="Your handles" mono />
              </Field>
              <Field label="Competitor websites" hint="Extra context for the profile">
                <ChipsInput value={f.competitorUrls} onChange={(v) => set("competitorUrls", v)} placeholder="https://competitor.com" mono />
              </Field>
            </Advanced>
          </Section>
        </Card>

        <div className="mt-5 flex items-center justify-between gap-4">
          <p className="text-muted-foreground text-xs">Next: run analysis on the project — <span className="text-foreground">nothing is charged until you click Run.</span></p>
          <CreateButton disabled={!f.name.trim() || !f.region.trim() || f.platforms.length === 0} />
        </div>
      </form>
    </div>
  );
}

function AnalyzingCard({ url }: { url: string }) {
  const steps = ["Reading your site…", "Finding your audience & goal…", "Drafting search seeds…", "Suggesting competitors…"];
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setI((x) => Math.min(x + 1, steps.length - 1)), 1400);
    return () => clearInterval(t);
  }, [steps.length]);
  return (
    <Card className="mt-7 gap-4 p-5">
      <div className="text-muted-foreground flex items-center gap-2 text-sm">
        <Loader2 className="text-primary size-4 animate-spin" />
        <span className="text-foreground font-medium">{steps[i]}</span>
        <span className="truncate">{new URL(url.startsWith("http") ? url : `https://${url}`).hostname}</span>
      </div>
      <div className="space-y-3">
        <Skeleton className="h-4 w-1/3" />
        <Skeleton className="h-8 w-full" />
        <div className="grid grid-cols-2 gap-3"><Skeleton className="h-8" /><Skeleton className="h-8" /></div>
        <Skeleton className="h-4 w-1/4" />
        <div className="flex gap-2"><Skeleton className="h-6 w-20" /><Skeleton className="h-6 w-24" /><Skeleton className="h-6 w-16" /></div>
      </div>
    </Card>
  );
}

function Section({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-4 p-5">
      <div>
        <h2 className="text-sm font-semibold">{title}</h2>
        {subtitle ? <p className="text-muted-foreground mt-0.5 text-xs">{subtitle}</p> : null}
      </div>
      {children}
    </div>
  );
}

function Field({ label, hint, required, children }: {
  label: string; hint?: string; required?: boolean; children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label className="flex items-center gap-1">
        {label}{required ? <span className="text-amber-400">*</span> : null}
      </Label>
      {hint ? <p className="text-muted-foreground -mt-0.5 text-xs">{hint}</p> : null}
      {children}
    </div>
  );
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-md border px-3 py-1 text-sm font-medium transition-colors",
        active ? "border-primary bg-primary/10 text-primary" : "border-input text-muted-foreground hover:text-foreground hover:border-ring",
      )}
    >
      {children}
    </button>
  );
}

function Advanced({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger className="text-muted-foreground hover:text-foreground flex items-center gap-1.5 text-xs font-medium transition-colors">
        <ChevronDown className={cn("size-3.5 transition-transform", open && "rotate-180")} />
        {open ? "Hide" : "Add your own accounts & competitor websites"}
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-4 flex flex-col gap-4">{children}</CollapsibleContent>
    </Collapsible>
  );
}

function CreateButton({ disabled }: { disabled: boolean }) {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" size="lg" disabled={disabled || pending} className="shrink-0">
      {pending ? <><Loader2 className="size-4 animate-spin" /> Creating…</> : <>Create project <ArrowRight className="size-4" /></>}
    </Button>
  );
}
