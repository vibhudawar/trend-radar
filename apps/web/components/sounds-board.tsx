import Link from "next/link";
import { Music, PlayCircle } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export type SoundRow = {
  key: string;
  label: string | null;
  uses: number; // videos using it
  accounts: number; // distinct creators
  regions: string[];
  examples: { handle: string | null; url: string }[];
};

// The global Trending Songs tab — sounds your peers are riding, across your projects.
export function SoundsBoard({ sounds, regions, activeRegion }: {
  sounds: SoundRow[]; regions: string[]; activeRegion: string | null;
}) {
  return (
    <div>
      <div className="mb-1 flex items-center gap-2">
        <Music className="text-primary size-5" />
        <h1 className="text-2xl font-bold tracking-tight">Trending Songs</h1>
      </div>
      <p className="text-muted-foreground mb-5 max-w-2xl text-sm leading-relaxed">
        Sounds your peers are riding — ranked by how many <span className="text-foreground">accounts</span> use them.
        Add a trending sound to your next video (muted or not, your call) to catch the wave and boost reach.
      </p>

      {regions.length > 1 ? (
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <span className="text-muted-foreground text-xs font-medium">Region:</span>
          <RegionChip label="All" href="/sounds" active={!activeRegion} />
          {regions.map((r) => (
            <RegionChip key={r} label={r} href={`/sounds?region=${encodeURIComponent(r)}`} active={activeRegion === r} />
          ))}
        </div>
      ) : null}

      {sounds.length === 0 ? (
        <Card className="flex flex-col items-center gap-2 p-12 text-center">
          <Music className="text-muted-foreground size-6" />
          <p className="text-base font-medium">No trending sounds yet</p>
          <p className="text-muted-foreground max-w-md text-sm">
            A sound shows up here once the same audio is used across your peers' videos. Run more projects (and larger
            peer sets) to surface the sounds worth riding.
          </p>
        </Card>
      ) : (
        <div className="flex flex-col gap-2.5">
          {sounds.map((s, i) => (
            <Card key={s.key} className="flex-row items-center gap-4 p-4">
              <span className="text-muted-foreground w-5 shrink-0 text-center text-sm font-semibold tabular-nums">{i + 1}</span>
              <span className="bg-primary/10 text-primary flex size-10 shrink-0 items-center justify-center rounded-lg">
                <Music className="size-5" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-semibold">{s.label || "Trending sound"}</div>
                <div className="text-muted-foreground mt-0.5 flex flex-wrap items-center gap-1.5 text-xs">
                  <span><span className="text-foreground font-medium">{s.accounts}</span> accounts</span>
                  <span>·</span>
                  <span><span className="text-foreground font-medium">{s.uses}</span> videos</span>
                  {s.regions.map((r) => <Badge key={r} variant="outline" className="ml-0.5 px-1.5 py-0 text-[10px]">{r}</Badge>)}
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                {s.examples.slice(0, 3).map((e, j) => (
                  <a key={j} href={e.url} target="_blank" rel="noreferrer"
                    className="text-muted-foreground hover:text-foreground transition-colors" title={`@${e.handle ?? "creator"}`}>
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

function RegionChip({ label, href, active }: { label: string; href: string; active: boolean }) {
  return (
    <Link href={href}
      className={cn("rounded-md border px-2.5 py-0.5 text-xs font-medium no-underline transition-colors",
        active ? "border-primary bg-primary/10 text-primary" : "border-input text-muted-foreground hover:text-foreground")}>
      {label}
    </Link>
  );
}
