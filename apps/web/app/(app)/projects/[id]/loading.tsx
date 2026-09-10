import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

// Loading fallback for a project — mirrors the header, details card, and concept boards.
export default function Loading() {
  return (
    <div>
      <Skeleton className="h-4 w-20" /> {/* ← Projects */}

      <div className="mt-3 mb-1.5 flex gap-2">
        <Skeleton className="h-5 w-14 rounded-full" />
        <Skeleton className="h-5 w-10 rounded-full" />
      </div>
      <Skeleton className="h-8 w-56" /> {/* title */}

      <Card className="mt-4 max-w-2xl gap-0 py-0">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="grid gap-1 border-t px-4 py-3.5 first:border-t-0 sm:grid-cols-[104px_1fr] sm:gap-4">
            <Skeleton className="h-3.5 w-16" />
            <div className="space-y-1.5">
              <Skeleton className="h-3.5 w-full" />
              <Skeleton className="h-3.5 w-4/5" />
            </div>
          </div>
        ))}
      </Card>

      <div className="mt-4 mb-7 flex items-center gap-3">
        <Skeleton className="h-9 w-24 rounded-md" />
        <Skeleton className="h-4 w-48" />
      </div>

      {/* concept boards */}
      <div className="space-y-6">
        {Array.from({ length: 2 }).map((_, lane) => (
          <div key={lane}>
            <Skeleton className="mb-3 h-5 w-40" />
            <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-3.5">
              {Array.from({ length: 2 }).map((_, i) => (
                <Card key={i} className="gap-3 p-4">
                  <Skeleton className="h-5 w-24 rounded-full" />
                  <Skeleton className="h-5 w-11/12" />
                  <div className="space-y-1.5">
                    <Skeleton className="h-3.5 w-full" />
                    <Skeleton className="h-3.5 w-2/3" />
                  </div>
                </Card>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
