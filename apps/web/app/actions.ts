"use server";

import { redirect } from "next/navigation";
import { and, eq } from "drizzle-orm";
import { z } from "zod";
import { projects, queries, type Platform } from "@trendradar/db";
import { db } from "@/lib/db";
import { requireUserId } from "@/lib/auth";
import { proposeProfileFromUrl, ProposedProfile } from "@/lib/onboarding";

// Server action: analyze a pasted product URL -> proposed onboarding profile (for the form to prefill).
export async function analyzeUrlAction(
  _prev: unknown,
  formData: FormData,
): Promise<{ ok: true; profile: ProposedProfile } | { ok: false; error: string }> {
  const url = String(formData.get("url") ?? "").trim();
  if (!url) return { ok: false, error: "Paste a product URL first." };
  try {
    const profile = await proposeProfileFromUrl(url);
    return { ok: true, profile };
  } catch (e) {
    // Never leak internals to the client (SSRF/host errors etc.) — generic message.
    return { ok: false, error: (e as Error).message || "Could not analyze that URL." };
  }
}

const CreateInput = z.object({
  name: z.string().min(1),
  productUrl: z.string().optional(),
  productDescription: z.string().optional(),
  audience: z.string().optional(),
  jobToBeDone: z.string().optional(),
  region: z.string().optional(),
  platforms: z.array(z.enum(["tiktok", "reels"])).min(1),
  seedQueries: z.array(z.string()).default([]),
});

export async function createProjectAction(formData: FormData): Promise<void> {
  const platformsRaw = formData.getAll("platforms").map(String) as Platform[];
  const parsed = CreateInput.safeParse({
    name: formData.get("name"),
    productUrl: formData.get("productUrl") || undefined,
    productDescription: formData.get("productDescription") || undefined,
    audience: formData.get("audience") || undefined,
    jobToBeDone: formData.get("jobToBeDone") || undefined,
    region: formData.get("region") || undefined,
    platforms: platformsRaw.length ? platformsRaw : ["tiktok"],
    seedQueries: String(formData.get("seedQueries") ?? "")
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean),
  });
  if (!parsed.success) throw new Error("Invalid project input");
  const p = parsed.data;
  const uid = await requireUserId();

  const d = db();
  const [row] = await d
    .insert(projects)
    .values({
      ownerId: uid,
      name: p.name,
      productUrl: p.productUrl,
      productDescription: p.productDescription,
      audience: p.audience,
      jobToBeDone: p.jobToBeDone,
      region: p.region,
      platforms: p.platforms,
    })
    .returning({ id: projects.id });

  if (row && p.seedQueries.length) {
    // one row per (platform, query) so the worker's per-platform ingest finds seeds for each
    await d.insert(queries).values(
      p.platforms.flatMap((pl) =>
        p.seedQueries.map((value) => ({
          projectId: row.id,
          platform: pl,
          type: "keyword" as const,
          value,
        })),
      ),
    );
  }
  redirect(row ? `/projects/${row.id}` : "/");
}

// Trigger a pipeline run on the Python worker (fire-and-forget; worker updates project.status).
export async function refreshProjectAction(projectId: string): Promise<{ ok: boolean; error?: string }> {
  const uid = await requireUserId();
  const owned = await db()
    .select({ id: projects.id })
    .from(projects)
    .where(and(eq(projects.id, projectId), eq(projects.ownerId, uid)))
    .limit(1);
  if (!owned.length) return { ok: false, error: "not found" };

  const base = process.env.WORKER_URL ?? "http://localhost:8000";
  try {
    const res = await fetch(`${base}/projects/${encodeURIComponent(projectId)}/refresh`, { method: "POST" });
    if (!res.ok && res.status !== 202) return { ok: false, error: `worker returned ${res.status}` };
    return { ok: true };
  } catch {
    return { ok: false, error: "worker unreachable" };
  }
}
