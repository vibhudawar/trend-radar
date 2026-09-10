import { Music, PlayCircle, TrendingUp, Type } from "lucide-react";
import { Card } from "@/components/ui/card";

export type TrendView = {
  id: string;
  type: "hook" | "sound" | "format";
  label: string | null;
  uses: number; // videos
  accounts: number; // distinct creators
  examples: { handle: string | null; url: string }[];
};

// "N uses across M accounts" — the corpus-wide counting layer (recurring hooks / sounds among peers).
export function TrendingBoard({ trends }: { trends: TrendView[] }) {
  return (
    <div className="mt-8">
      <div className="mb-1 flex items-center gap-2">
        <TrendingUp className="text-primary size-4" />
        <h2 className="text-base font-semibold">Trending in your niche</h2>
      </div>
      <p className="text-muted-foreground mb-4 text-sm">
        Hooks and sounds your peers reuse — ranked by how many <span className="text-foreground">accounts</span> run them.
      </p>

      {trends.length === 0 ? (
        <Card className="p-8 text-center">
          <p className="text-sm font-medium">No repeated patterns yet</p>
          <p className="text-muted-foreground mx-auto mt-1 max-w-md text-sm">
            This surfaces once the same hook or sound recurs across your peers — it needs a larger peer set to light up.
            Add more competitor accounts to grow the corpus.
          </p>
        </Card>
      ) : (
        <div className="flex flex-col gap-2">
          {trends.map((t) => (
            <Card key={t.id} className="flex-row items-center justify-between gap-4 p-3.5">
              <div className="flex min-w-0 items-center gap-2.5">
                <span className="bg-muted text-muted-foreground flex size-7 shrink-0 items-center justify-center rounded-md">
                  {t.type === "sound" ? <Music className="size-3.5" /> : <Type className="size-3.5" />}
                </span>
                <span className="truncate text-sm font-medium">{t.label ?? (t.type === "sound" ? "Trending sound" : "Hook")}</span>
              </div>
              <div className="flex shrink-0 items-center gap-4">
                <div className="text-right">
                  <span className="text-foreground text-sm font-semibold">{t.uses}</span>
                  <span className="text-muted-foreground text-xs"> uses · </span>
                  <span className="text-foreground text-sm font-semibold">{t.accounts}</span>
                  <span className="text-muted-foreground text-xs"> accounts</span>
                </div>
                {t.examples[0] ? (
                  <a href={t.examples[0].url} target="_blank" rel="noreferrer"
                    className="text-muted-foreground hover:text-foreground shrink-0 transition-colors">
                    <PlayCircle className="size-4" />
                  </a>
                ) : null}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
