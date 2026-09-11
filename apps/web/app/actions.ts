"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
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

const clean = (arr: unknown) =>
  z.array(z.string()).catch([]).parse(arr).map((s) => s.trim().replace(/^@/, "")).filter(Boolean);

const CreateInput = z.object({
  name: z.string().min(1, "Business name is required"),
  productUrl: z.string().optional(),
  productDescription: z.string().optional(),
  audience: z.string().optional(),
  jobToBeDone: z.string().optional(),
  region: z.string().min(1, "Region is required"), // user-set, never inferred
  platforms: z.array(z.enum(["tiktok", "reels"])).min(1),
  seedQueries: z.array(z.string()).default([]),
  competitors: z.array(z.string()).default([]), // niche/competitor account handles
  ownAccounts: z.array(z.string()).default([]), // the client's own handles
  competitorUrls: z.array(z.string()).default([]),
});

export async function createProjectAction(formData: FormData): Promise<void> {
  const platformsRaw = formData.getAll("platforms").map(String) as Platform[];
  const parsed = CreateInput.safeParse({
    name: formData.get("name"),
    productUrl: formData.get("productUrl") || undefined,
    productDescription: formData.get("productDescription") || undefined,
    audience: formData.get("audience") || undefined,
    jobToBeDone: formData.get("jobToBeDone") || undefined,
    region: (formData.get("region") as string)?.trim(),
    platforms: platformsRaw.length ? platformsRaw : ["tiktok"],
    seedQueries: clean(formData.getAll("seedQueries")),
    competitors: clean(formData.getAll("competitors")),
    ownAccounts: clean(formData.getAll("ownAccounts")),
    competitorUrls: clean(formData.getAll("competitorUrls")),
  });
  if (!parsed.success) throw new Error(parsed.error.issues[0]?.message ?? "Invalid project input");
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
      competitorUrls: p.competitorUrls.length ? p.competitorUrls : null,
      platforms: p.platforms,
    })
    .returning({ id: projects.id });

  if (row) {
    // Seeds drive the worker's 3-source discovery: keyword search + account mining (SPEC §4.0).
    const own = new Set(p.ownAccounts.map((h) => h.toLowerCase()));
    const competitors = p.competitors.filter((h) => !own.has(h.toLowerCase())); // own wins on overlap
    // One row per (platform, seed) so per-platform ingest finds each; dedupe handles overlap.
    const rows = p.platforms.flatMap((pl) => [
      ...p.seedQueries.map((value) => ({ projectId: row.id, platform: pl, type: "keyword" as const, value, isOwn: false })),
      ...competitors.map((value) => ({ projectId: row.id, platform: pl, type: "account" as const, value, isOwn: false })),
      ...p.ownAccounts.map((value) => ({ projectId: row.id, platform: pl, type: "account" as const, value, isOwn: true })),
    ]);
    if (rows.length) await d.insert(queries).values(rows);
  }
  redirect(row ? `/projects/${row.id}` : "/");
}

const UpdateInput = z.object({
  name: z.string().min(1, "Business name is required"),
  productUrl: z.string().optional(),
  productDescription: z.string().optional(),
  audience: z.string().optional(),
  jobToBeDone: z.string().optional(),
  region: z.string().min(1, "Region is required"),
});

// Edit the business details captured at onboarding (name/goal/about/audience/website/region).
export async function updateProjectAction(
  projectId: string,
  formData: FormData,
): Promise<{ ok: boolean; error?: string }> {
  const uid = await requireUserId();
  const parsed = UpdateInput.safeParse({
    name: formData.get("name"),
    productUrl: formData.get("productUrl") || undefined,
    productDescription: formData.get("productDescription") || undefined,
    audience: formData.get("audience") || undefined,
    jobToBeDone: formData.get("jobToBeDone") || undefined,
    region: (formData.get("region") as string)?.trim(),
  });
  if (!parsed.success) return { ok: false, error: parsed.error.issues[0]?.message ?? "Invalid input" };
  const p = parsed.data;

  const res = await db()
    .update(projects)
    .set({
      name: p.name,
      productUrl: p.productUrl ?? null,
      productDescription: p.productDescription ?? null,
      audience: p.audience ?? null,
      jobToBeDone: p.jobToBeDone ?? null,
      region: p.region,
      updatedAt: new Date(),
    })
    .where(and(eq(projects.id, projectId), eq(projects.ownerId, uid))) // ownership enforced
    .returning({ id: projects.id });

  if (!res.length) return { ok: false, error: "Project not found" };
  revalidatePath(`/projects/${projectId}`);
  return { ok: true };
}

// Soft-delete a project (sets deleted_at; rows stay for recovery). Ownership-enforced.
export async function deleteProjectAction(projectId: string): Promise<void> {
  const uid = await requireUserId();
  await db()
    .update(projects)
    .set({ deletedAt: new Date(), updatedAt: new Date() })
    .where(and(eq(projects.id, projectId), eq(projects.ownerId, uid)));
  revalidatePath("/");
  redirect("/");
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
  const headers: Record<string, string> = {};
  if (process.env.WORKER_SECRET) headers["X-Worker-Secret"] = process.env.WORKER_SECRET;
  try {
    const res = await fetch(`${base}/projects/${encodeURIComponent(projectId)}/refresh`, { method: "POST", headers });
    if (!res.ok && res.status !== 202) return { ok: false, error: `worker returned ${res.status}` };
    return { ok: true };
  } catch {
    return { ok: false, error: "worker unreachable" };
  }
}
