import Link from "next/link";
import { desc, eq } from "drizzle-orm";
import { projects } from "@trendradar/db";
import { safe } from "@/lib/db";
import { requireUserId } from "@/lib/auth";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function Dashboard() {
  const uid = await requireUserId();
  const rows = await safe(
    (d) =>
      d.select().from(projects)
        .where(eq(projects.ownerId, uid)) // owner-scoped
        .orderBy(desc(projects.createdAt))
        .limit(60),
    [] as (typeof projects.$inferSelect)[],
  );

  return (
    <div>
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Projects</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Each project is an onboarded business — its profile drives the whole content engine.
          </p>
        </div>
        <Link href="/projects/new" className={cn(buttonVariants())}>＋ New Project</Link>
      </div>

      {rows.length === 0 ? (
        <Card className="flex flex-col items-center gap-3 p-12 text-center">
          <p className="text-base">No projects yet.</p>
          <p className="text-sm text-muted-foreground">
            Onboard a business by pasting its product URL — we propose the profile and seed queries.
          </p>
          <Link href="/projects/new" className={cn(buttonVariants())}>Onboard your first business</Link>
        </Card>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-3.5">
          {rows.map((p) => (
            <Link key={p.id} href={`/projects/${p.id}`} className="no-underline">
              <Card className="h-full gap-2 p-4 transition-colors hover:border-ring">
                <div className="flex flex-wrap items-center gap-2">
                  {p.platforms.map((pl) => (
                    <Badge key={pl} variant="secondary">{pl}</Badge>
                  ))}
                  {p.region ? <Badge variant="outline">{p.region}</Badge> : null}
                  {p.status === "ready" ? <Badge className="bg-emerald-500/15 text-emerald-400">ready</Badge> : null}
                  {p.status === "running" ? <Badge className="bg-amber-500/15 text-amber-400">running…</Badge> : null}
                </div>
                <div className="text-base font-semibold">{p.name}</div>
                <div className="text-sm text-muted-foreground line-clamp-3">
                  {p.jobToBeDone || p.productDescription || "No profile yet"}
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
