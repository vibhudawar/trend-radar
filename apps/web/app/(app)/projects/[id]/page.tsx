import Link from "next/link";
import { and, eq, inArray, isNull } from "drizzle-orm";
import { analyses, authors, conceptMembers, concepts, projects, queries, trends, trendMembers, videos } from "@trendradar/db";
import { safe } from "@/lib/db";
import { requireUserId } from "@/lib/auth";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { RefreshButton } from "@/components/RefreshButton";
import { RealtimeRefresh } from "@/components/RealtimeRefresh";
import { ConceptBoard, type ConceptView, type Beat } from "@/components/concept-board";
import { TrendingBoard, type TrendView } from "@/components/trending-board";
import { EditProjectSheet } from "@/components/edit-project-sheet";

export const dynamic = "force-dynamic";

type Member = { conceptId: string; url: string; handle: string | null; hook: string | null };

function agoText(d: Date | null): string {
  if (!d) return "never refreshed";
  const h = Math.floor((Date.now() - new Date(d).getTime()) / 3.6e6);
  return h < 1 ? "refreshed just now" : `refreshed ${h}h ago`;
}

// One labeled row in the project details card (label column + value).
function ProjectField({ label, value }: { label: string; value: React.ReactNode | null }) {
  if (!value) return null;
  return (
    <div className="grid gap-1 border-t px-4 py-3 first:border-t-0 sm:grid-cols-[104px_1fr] sm:gap-4 sm:py-3.5">
      <div className="text-muted-foreground pt-0.5 text-[11px] font-semibold uppercase tracking-wide">{label}</div>
      <div className="text-foreground/90 text-sm leading-relaxed">{value}</div>
    </div>
  );
}

export default async function ProjectDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const uid = await requireUserId();
  const project = await safe(
    async (d) =>
      (await d.select().from(projects)
        .where(and(eq(projects.id, id), eq(projects.ownerId, uid), isNull(projects.deletedAt)))
        .limit(1))[0] ?? null,
    null as typeof projects.$inferSelect | null,
  );
  const seeds = await safe((d) => d.select().from(queries).where(eq(queries.projectId, id)), [] as (typeof queries.$inferSelect)[]);
  const rows = await safe((d) => d.select().from(concepts).where(eq(concepts.projectId, id)), [] as (typeof concepts.$inferSelect)[]);

  // Counting layer: "N uses across M accounts" trends (hooks + sounds).
  const trendRows = await safe((d) => d.select().from(trends).where(eq(trends.projectId, id)), [] as (typeof trends.$inferSelect)[]);
  const trendIds = trendRows.map((t) => t.id);
  const trendMems = trendIds.length
    ? await safe(
        (d) =>
          d.select({ trendId: trendMembers.trendId, handle: authors.handle, url: videos.url })
            .from(trendMembers)
            .innerJoin(videos, eq(trendMembers.videoId, videos.id))
            .leftJoin(authors, eq(videos.authorId, authors.id))
            .where(inArray(trendMembers.trendId, trendIds)),
        [] as { trendId: string; handle: string | null; url: string }[],
      )
    : ([] as { trendId: string; handle: string | null; url: string }[]);
  const trendViews: TrendView[] = trendRows
    .map((t): TrendView => {
      const mems = trendMems.filter((m) => m.trendId === t.id);
      return {
        id: t.id, type: t.type as TrendView["type"], label: t.label,
        uses: t.memberCount, accounts: new Set(mems.map((m) => m.handle)).size,
        examples: mems.slice(0, 5),
      };
    })
    .sort((a, b) => b.accounts - a.accounts || b.uses - a.uses);

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
      <div className="flex items-center gap-2">
        <h1 className="text-2xl font-bold tracking-tight">{project.name}</h1>
        <EditProjectSheet
          project={{
            id: project.id,
            name: project.name,
            jobToBeDone: project.jobToBeDone,
            productDescription: project.productDescription,
            audience: project.audience,
            productUrl: project.productUrl,
            region: project.region,
          }}
        />
      </div>

      <Card className="mt-4 max-w-2xl gap-0 py-0">
        <ProjectField label="Goal" value={project.jobToBeDone} />
        <ProjectField label="About" value={project.productDescription} />
        <ProjectField label="Audience" value={project.audience} />
        <ProjectField
          label="Website"
          value={
            project.productUrl ? (
              <a href={project.productUrl} target="_blank" rel="noreferrer"
                className="text-primary break-all hover:underline">
                {project.productUrl.replace(/^https?:\/\//, "").replace(/\/$/, "")}
              </a>
            ) : null
          }
        />
      </Card>

      <div className="mt-4 mb-7 flex flex-wrap items-center gap-3">
        <RefreshButton projectId={project.id} status={project.status} />
        <span className="text-muted-foreground text-sm">
          {project.status === "running" ? "running…" : agoText(project.lastRefreshedAt)}
          {project.lastRunCredits != null ? ` · ${project.lastRunCredits} credits last run` : ""}
        </span>
      </div>

      <ConceptBoard rising={rising} proven={proven} />

      <TrendingBoard trends={trendViews} />

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
