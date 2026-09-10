import { desc, eq, sql } from "drizzle-orm";
import { trendingSounds } from "@trendradar/db";
import { safe } from "@/lib/db";
import { requireUserId } from "@/lib/auth";
import { SoundsBoard, type SoundRow } from "@/components/sounds-board";

export const dynamic = "force-dynamic";
export const metadata = { title: "Trending Songs — TrendRadar" };

// Global, region-keyed Trending Songs chart (SPEC §4.5) — NOT niche-scoped. Everyone sees the same
// chart; the only axis is country. Fed by worker/refresh_trending_sounds into `trending_sounds`.
export default async function SoundsPage({ searchParams }: { searchParams: Promise<{ region?: string }> }) {
  const { region: qsRegion } = await searchParams;
  await requireUserId();

  const regionRows = await safe(
    (d) =>
      d
        .selectDistinct({ region: trendingSounds.region })
        .from(trendingSounds)
        .orderBy(trendingSounds.region),
    [] as { region: string }[],
  );
  const regions = regionRows.map((r) => r.region);
  const region = qsRegion && regions.includes(qsRegion) ? qsRegion : (regions[0] ?? null);

  const rows = region
    ? await safe(
        (d) =>
          d
            .select({
              audioId: trendingSounds.audioId,
              title: trendingSounds.title,
              author: trendingSounds.author,
              playUrl: trendingSounds.playUrl,
              coverUrl: trendingSounds.coverUrl,
              usage: trendingSounds.usageSignal,
              examples: trendingSounds.exampleUrls,
              isOriginal: trendingSounds.isOriginalSound,
            })
            .from(trendingSounds)
            .where(eq(trendingSounds.region, region))
            .orderBy(desc(trendingSounds.usageSignal), sql`${trendingSounds.title} asc nulls last`),
        [] as Omit<SoundRow, "region">[],
      )
    : [];

  const sounds: SoundRow[] = rows.map((r) => ({ ...r, region: region ?? "" }));

  return <SoundsBoard sounds={sounds} regions={regions} activeRegion={region} />;
}
