import { and, desc, eq, sql } from "drizzle-orm";
import { trendingSounds } from "@trendradar/db";
import { safe } from "@/lib/db";
import { requireUserId } from "@/lib/auth";
import { SoundsBoard, type SoundRow } from "@/components/sounds-board";

export const dynamic = "force-dynamic";
export const metadata = { title: "Trending Songs — TrendRadar" };

// Region-native Trending Songs chart (SPEC §4.5). Two axes: country, then platform.
// IN → Instagram only (TikTok banned); US → Instagram + TikTok. Not niche-scoped.
export default async function SoundsPage({
  searchParams,
}: {
  searchParams: Promise<{ region?: string; platform?: string }>;
}) {
  const qs = await searchParams;
  await requireUserId();

  // Distinct (region, platform) pairs we actually have data for.
  const pairs = await safe(
    (d) =>
      d
        .selectDistinct({ region: trendingSounds.region, platform: trendingSounds.platform })
        .from(trendingSounds)
        .orderBy(trendingSounds.region, trendingSounds.platform),
    [] as { region: string; platform: string }[],
  );

  const regions = [...new Set(pairs.map((p) => p.region))];
  const region = qs.region && regions.includes(qs.region) ? qs.region : (regions[0] ?? null);
  const platforms = pairs.filter((p) => p.region === region).map((p) => p.platform);
  const platform =
    qs.platform && platforms.includes(qs.platform) ? qs.platform : (platforms[0] ?? null);

  const rows =
    region && platform
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
              .where(and(eq(trendingSounds.region, region), eq(trendingSounds.platform, platform)))
              .orderBy(desc(trendingSounds.usageSignal), sql`${trendingSounds.title} asc nulls last`),
          [] as Omit<SoundRow, "region" | "platform">[],
        )
      : [];

  const sounds: SoundRow[] = rows.map((r) => ({ ...r, region: region ?? "", platform: platform ?? "" }));

  return (
    <SoundsBoard
      sounds={sounds}
      regions={regions}
      activeRegion={region}
      platforms={platforms}
      activePlatform={platform}
    />
  );
}
