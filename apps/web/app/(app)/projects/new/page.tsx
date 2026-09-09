"use client";

import Link from "next/link";
import { useActionState, useEffect, useState } from "react";
import { analyzeUrlAction, createProjectAction } from "@/app/actions";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

const PLATFORMS = ["tiktok", "reels"] as const;

export default function NewProjectPage() {
  const [state, analyze, analyzing] = useActionState(analyzeUrlAction, null as
    | { ok: true; profile: any }
    | { ok: false; error: string }
    | null);

  const [f, setF] = useState({
    name: "", productUrl: "", productDescription: "", audience: "",
    jobToBeDone: "", region: "", platforms: ["tiktok"] as string[], seedQueries: "",
  });

  useEffect(() => {
    if (state && state.ok) {
      const p = state.profile;
      setF((prev) => ({
        ...prev,
        name: p.name ?? prev.name,
        productDescription: p.productDescription ?? "",
        audience: p.audience ?? "",
        jobToBeDone: p.jobToBeDone ?? "",
        region: p.region ?? "",
        platforms: p.platforms?.length ? p.platforms : prev.platforms,
        seedQueries: (p.seedQueries ?? []).join("\n"),
      }));
    }
  }, [state]);

  const toggle = (pl: string) =>
    setF((prev) => ({
      ...prev,
      platforms: prev.platforms.includes(pl) ? prev.platforms.filter((x) => x !== pl) : [...prev.platforms, pl],
    }));

  return (
    <div className="max-w-2xl">
      <Link href="/" className="text-sm text-muted-foreground no-underline">← Projects</Link>
      <h1 className="mb-1 mt-2.5 text-2xl font-bold">Onboard a business</h1>
      <p className="mb-5 text-sm text-muted-foreground">
        Paste the product URL — we read the site and propose the profile + seed queries. Review, then create.
      </p>

      <Card className="mb-4 p-4">
        <form action={analyze}>
          <Label className="mb-1.5 block">Product URL</Label>
          <div className="flex gap-2.5">
            <Input name="url" value={f.productUrl} placeholder="https://ecombox.in"
              onChange={(e) => setF((p) => ({ ...p, productUrl: e.target.value }))} />
            <Button type="submit" variant="secondary" disabled={analyzing} className="whitespace-nowrap">
              {analyzing ? "Reading…" : "Analyze URL"}
            </Button>
          </div>
          {state && !state.ok ? <p className="mt-2 text-sm text-amber-400">{state.error}</p> : null}
          {state && state.ok ? <p className="mt-2 text-sm text-emerald-400">Profile proposed below — review and edit.</p> : null}
        </form>
      </Card>

      <Card className="p-4">
        <form action={createProjectAction} className="flex flex-col gap-3.5">
          <input type="hidden" name="productUrl" value={f.productUrl} />
          <Field name="name" label="Business name" value={f.name} onChange={(v) => setF((p) => ({ ...p, name: v }))} />
          <Field name="jobToBeDone" label="Job to be done" value={f.jobToBeDone} onChange={(v) => setF((p) => ({ ...p, jobToBeDone: v }))} />
          <Field name="audience" label="Audience" value={f.audience} onChange={(v) => setF((p) => ({ ...p, audience: v }))} />
          <div>
            <Label className="mb-1.5 block">Product description (used to adapt hooks)</Label>
            <Textarea name="productDescription" rows={3} value={f.productDescription}
              onChange={(e) => setF((p) => ({ ...p, productDescription: e.target.value }))} />
          </div>
          <div className="flex gap-3.5">
            <div className="flex-1">
              <Field name="region" label="Region" value={f.region} onChange={(v) => setF((p) => ({ ...p, region: v }))} />
            </div>
            <div className="flex-1">
              <Label className="mb-1.5 block">Platforms</Label>
              <div className="flex gap-2 pt-0.5">
                {PLATFORMS.map((pl) => (
                  <Button type="button" key={pl} variant={f.platforms.includes(pl) ? "default" : "outline"}
                    size="sm" onClick={() => toggle(pl)}>
                    {f.platforms.includes(pl) ? "✓ " : ""}{pl}
                  </Button>
                ))}
              </div>
              {f.platforms.map((pl) => <input key={pl} type="hidden" name="platforms" value={pl} />)}
            </div>
          </div>
          <div>
            <Label className="mb-1.5 block">Seed queries (one per line — goal-matched)</Label>
            <Textarea name="seedQueries" rows={5} value={f.seedQueries} className="font-mono text-[13px]"
              onChange={(e) => setF((p) => ({ ...p, seedQueries: e.target.value }))} />
          </div>
          <div className="flex justify-end">
            <Button type="submit">Create project</Button>
          </div>
        </form>
      </Card>
    </div>
  );
}

function Field({ name, label, value, onChange }: {
  name: string; label: string; value: string; onChange: (v: string) => void;
}) {
  return (
    <div>
      <Label className="mb-1.5 block">{label}</Label>
      <Input name={name} value={value} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}
