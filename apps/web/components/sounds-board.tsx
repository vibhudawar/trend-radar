import Link from "next/link";
import { Music, PlayCircle, Volume2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export type SoundRow = {
  audioId: string;
  title: string | null;
  author: string | null;
  playUrl: string | null;
  coverUrl: string | null;
  usage: number; // rank / #trending videos carrying it
  examples: string[] | null;
  isOriginal: boolean | null;
  region: string;
  platform: string;
};

const PLATFORM_LABEL: Record<string, string> = { instagram: "Instagram", tiktok: "TikTok" };

// Trending Songs chart — region-native. Country selector, then a platform sub-filter (IN=IG only).
export function SoundsBoard({
  sounds,
  regions,
  activeRegion,
  platforms,
  activePlatform,
}: {
  sounds: SoundRow[];
  regions: string[];
  activeRegion: string | null;
  platforms: string[];
  activePlatform: string | null;
}) {
  return (
    <div>
      <div className="mb-1 flex items-center gap-2">
        <Music className="text-primary size-5" />
        <h1 className="text-2xl font-bold tracking-tight">Trending Songs</h1>
      </div>
      <p className="text-muted-foreground mb-5 max-w-2xl text-sm leading-relaxed">
        What&apos;s trending right now, by country. Add a trending sound to your next video (muted or
        not, your call) to catch the wave and boost reach.
      </p>

      {regions.length > 0 ? (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span className="text-muted-foreground w-16 text-xs font-medium">Country</span>
          {regions.map((r) => (
            <Chip key={r} label={r} href={`/sounds?region=${encodeURIComponent(r)}`} active={activeRegion === r} />
          ))}
        </div>
      ) : null}

      {platforms.length > 1 ? (
        <div className="mb-5 flex flex-wrap items-center gap-2">
          <span className="text-muted-foreground w-16 text-xs font-medium">Platform</span>
          {platforms.map((p) => (
            <Chip
              key={p}
              label={PLATFORM_LABEL[p] ?? p}
              href={`/sounds?region=${encodeURIComponent(activeRegion ?? "")}&platform=${encodeURIComponent(p)}`}
              active={activePlatform === p}
            />
          ))}
        </div>
      ) : platforms.length === 1 ? (
        <div className="mb-5 flex items-center gap-2">
          <span className="text-muted-foreground w-16 text-xs font-medium">Platform</span>
          <Badge variant="outline" className="text-xs">{PLATFORM_LABEL[platforms[0]] ?? platforms[0]}</Badge>
        </div>
      ) : null}

      {sounds.length === 0 ? (
        <Card className="flex flex-col items-center gap-2 p-12 text-center">
          <Music className="text-muted-foreground size-6" />
          <p className="text-base font-medium">No trending sounds yet</p>
          <p className="text-muted-foreground max-w-md text-sm">
            The chart refreshes every few days. Run{" "}
            <code className="text-xs">worker/refresh_trending_sounds.py</code> to populate it.
          </p>
        </Card>
      ) : (
        <div className="flex flex-col gap-2.5">
          {sounds.map((s, i) => (
            <Card key={s.audioId} className="flex-row items-center gap-4 p-4">
              <span className="text-muted-foreground w-5 shrink-0 text-center text-sm font-semibold tabular-nums">{i + 1}</span>
              {s.coverUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={s.coverUrl} alt="" className="size-10 shrink-0 rounded-lg object-cover" />
              ) : (
                <span className="bg-primary/10 text-primary flex size-10 shrink-0 items-center justify-center rounded-lg">
                  <Music className="size-5" />
                </span>
              )}
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-semibold">{s.title || "Trending sound"}</div>
                <div className="text-muted-foreground mt-0.5 flex flex-wrap items-center gap-1.5 text-xs">
                  {s.author ? <span className="truncate">{s.author}</span> : null}
                  {s.usage > 1 ? (
                    <>
                      <span>·</span>
                      <span><span className="text-foreground font-medium">{s.usage}</span> trending clips</span>
                    </>
                  ) : null}
                  {s.isOriginal ? <Badge variant="outline" className="ml-0.5 px-1.5 py-0 text-[10px]">Original</Badge> : null}
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-2.5">
                {s.playUrl ? (
                  <a href={s.playUrl} target="_blank" rel="noreferrer"
                    className="text-muted-foreground hover:text-foreground transition-colors" title="Preview audio">
                    <Volume2 className="size-4" />
                  </a>
                ) : null}
                {(s.examples ?? []).slice(0, 3).map((url, j) => (
                  <a key={j} href={url} target="_blank" rel="noreferrer"
                    className="text-muted-foreground hover:text-foreground transition-colors" title="Example clip">
                    <PlayCircle className="size-4" />
                  </a>
                ))}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function Chip({ label, href, active }: { label: string; href: string; active: boolean }) {
  return (
    <Link href={href}
      className={cn("rounded-md border px-2.5 py-0.5 text-xs font-medium no-underline transition-colors",
        active ? "border-primary bg-primary/10 text-primary" : "border-input text-muted-foreground hover:text-foreground")}>
      {label}
    </Link>
  );
}
