import { and, eq, inArray } from "drizzle-orm";
import { authors, projects, trends, trendMembers, videos } from "@trendradar/db";
import { safe } from "@/lib/db";
import { requireUserId } from "@/lib/auth";
import { SoundsBoard, type SoundRow } from "@/components/sounds-board";

export const dynamic = "force-dynamic";
export const metadata = { title: "Trending Songs — TrendRadar" };

export default async function SoundsPage({ searchParams }: { searchParams: Promise<{ region?: string }> }) {
  const { region } = await searchParams;
  const uid = await requireUserId();

  const myProjects = await safe(
    (d) => d.select({ id: projects.id, region: projects.region }).from(projects).where(eq(projects.ownerId, uid)),
    [] as { id: string; region: string | null }[],
  );
  const projectRegion = new Map(myProjects.map((p) => [p.id, p.region]));
  const projectIds = myProjects.map((p) => p.id);

  const soundTrends = projectIds.length
    ? await safe(
        (d) => d.select({ id: trends.id, key: trends.key, label: trends.label, uses: trends.memberCount, projectId: trends.projectId })
          .from(trends)
          .where(and(inArray(trends.projectId, projectIds), eq(trends.type, "sound"))),
        [] as { id: string; key: string; label: string | null; uses: number; projectId: string }[],
      )
    : [];

  const trendIds = soundTrends.map((t) => t.id);
  const mems = trendIds.length
    ? await safe(
        (d) => d.select({ trendId: trendMembers.trendId, handle: authors.handle, url: videos.url })
          .from(trendMembers)
          .innerJoin(videos, eq(trendMembers.videoId, videos.id))
          .leftJoin(authors, eq(videos.authorId, authors.id))
          .where(inArray(trendMembers.trendId, trendIds)),
        [] as { trendId: string; handle: string | null; url: string }[],
      )
    : [];

  // Aggregate by the sound (key) across all of the user's projects.
  const byKey = new Map<string, { label: string | null; uses: number; handles: Set<string>; regions: Set<string>; examples: { handle: string | null; url: string }[] }>();
  for (const t of soundTrends) {
    const g = byKey.get(t.key) ?? { label: t.label, uses: 0, handles: new Set<string>(), regions: new Set<string>(), examples: [] };
    g.label = g.label ?? t.label;
    g.uses += t.uses;
    const r = projectRegion.get(t.projectId);
    if (r) g.regions.add(r);
    for (const m of mems.filter((x) => x.trendId === t.id)) {
      if (m.handle) g.handles.add(m.handle);
      if (g.examples.length < 5) g.examples.push({ handle: m.handle, url: m.url });
    }
    byKey.set(t.key, g);
  }

  let sounds: SoundRow[] = [...byKey.entries()]
    .map(([key, g]): SoundRow => ({
      key, label: g.label, uses: g.uses, accounts: g.handles.size, regions: [...g.regions], examples: g.examples,
    }))
    .sort((a, b) => b.accounts - a.accounts || b.uses - a.uses);

  const allRegions = [...new Set(sounds.flatMap((s) => s.regions))].sort();
  if (region) sounds = sounds.filter((s) => s.regions.includes(region));

  return <SoundsBoard sounds={sounds} regions={allRegions} activeRegion={region ?? null} />;
}
