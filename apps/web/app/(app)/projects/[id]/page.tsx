import Link from "next/link";
import { and, eq, inArray } from "drizzle-orm";
import { analyses, authors, conceptMembers, concepts, projects, queries, videos } from "@trendradar/db";
import { safe } from "@/lib/db";
import { requireUserId } from "@/lib/auth";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { RefreshButton } from "@/components/RefreshButton";
import { RealtimeRefresh } from "@/components/RealtimeRefresh";
import { ConceptBoard, type ConceptView, type Beat } from "@/components/concept-board";

export const dynamic = "force-dynamic";

type Member = { conceptId: string; url: string; handle: string | null; hook: string | null };

function agoText(d: Date | null): string {
  if (!d) return "never refreshed";
  const h = Math.floor((Date.now() - new Date(d).getTime()) / 3.6e6);
  return h < 1 ? "refreshed just now" : `refreshed ${h}h ago`;
}

export default async function ProjectDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const uid = await requireUserId();
  const project = await safe(
    async (d) =>
      (await d.select().from(projects)
        .where(and(eq(projects.id, id), eq(projects.ownerId, uid)))
        .limit(1))[0] ?? null,
    null as typeof projects.$inferSelect | null,
  );
  const seeds = await safe((d) => d.select().from(queries).where(eq(queries.projectId, id)), [] as (typeof queries.$inferSelect)[]);
  const rows = await safe((d) => d.select().from(concepts).where(eq(concepts.projectId, id)), [] as (typeof concepts.$inferSelect)[]);

  const conceptIds = rows.map((r) => r.id);
  const members = conceptIds.length
    ? await safe(
        (d) =>
          d.select({ conceptId: conceptMembers.conceptId, url: videos.url, handle: authors.handle, hook: analyses.hookText })
            .from(conceptMembers)
            .innerJoin(videos, eq(conceptMembers.videoId, videos.id))
            .leftJoin(authors, eq(videos.authorId, authors.id))
            .leftJoin(analyses, eq(analyses.videoId, videos.id))
            .where(inArray(conceptMembers.conceptId, conceptIds)),
        [] as Member[],
      )
    : ([] as Member[]);

  const vidsByConcept = new Map<string, { handle: string | null; url: string; hook: string | null }[]>();
  for (const m of members) {
    const list = vidsByConcept.get(m.conceptId) ?? [];
    list.push({ handle: m.handle, url: m.url, hook: m.hook });
    vidsByConcept.set(m.conceptId, list);
  }

  if (!project) {
    return (
      <div>
        <Link href="/" className="text-muted-foreground text-sm no-underline">← Projects</Link>
        <Card className="mt-4 p-4">Project not found (or database not configured).</Card>
      </div>
    );
  }

  const toView = (r: typeof concepts.$inferSelect): ConceptView => ({
    id: r.id,
    lane: r.lane as "rising" | "proven",
    name: r.name,
    confidence: r.confidence as ConceptView["confidence"],
    lifecycle: r.lifecycle,
    nVideos: r.nVideos,
    nCreators: r.nCreators,
    medianOutperformance: r.medianOutperformance ? `${r.medianOutperformance}×` : null,
    adaptedHook: r.adaptedHook,
    format: r.format,
    lengthS: r.lengthS,
    testTarget: r.testTarget,
    script: Array.isArray(r.script) ? (r.script as Beat[]) : [],
    videos: vidsByConcept.get(r.id) ?? [],
  });

  const rising = rows.filter((r) => r.lane === "rising").map(toView);
  const proven = rows.filter((r) => r.lane === "proven").map(toView);

  return (
    <div>
      <RealtimeRefresh projectId={project.id} />
      <Link href="/" className="text-muted-foreground text-sm no-underline hover:underline">← Projects</Link>

      <div className="mt-3 mb-1.5 flex flex-wrap items-center gap-2">
        {project.platforms.map((pl) => <Badge key={pl} variant="secondary">{pl}</Badge>)}
        {project.region ? <Badge variant="outline">{project.region}</Badge> : null}
      </div>
      <h1 className="text-2xl font-bold tracking-tight">{project.name}</h1>
      <p className="text-muted-foreground mt-1 max-w-2xl text-sm leading-relaxed">
        {project.jobToBeDone}{project.jobToBeDone && project.productDescription ? " — " : ""}{project.productDescription}
      </p>

      <div className="mt-4 mb-7 flex flex-wrap items-center gap-3">
        <RefreshButton projectId={project.id} status={project.status} />
        <span className="text-muted-foreground text-sm">
          {project.status === "running" ? "running…" : agoText(project.lastRefreshedAt)}
          {project.lastRunCredits != null ? ` · ${project.lastRunCredits} credits last run` : ""}
        </span>
      </div>

      <ConceptBoard rising={rising} proven={proven} />

      <Card className="mt-6 gap-2 p-4">
        <div className="text-muted-foreground text-xs font-semibold uppercase tracking-wide">Seed queries ({seeds.length})</div>
        {seeds.length === 0 ? (
          <p className="text-muted-foreground text-sm">No seed queries yet.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {seeds.map((s) => (
              <span key={s.id} className="bg-muted/40 rounded-md border px-2.5 py-1 text-[13px]">{s.value}</span>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
