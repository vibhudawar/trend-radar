import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

// Loading fallback for Trending Songs — mirrors the filters + ranked list.
export default function Loading() {
  return (
    <div>
      <Skeleton className="mb-2 h-7 w-48" />
      <Skeleton className="mb-5 h-4 w-[32rem] max-w-full" />

      <div className="mb-3 flex items-center gap-2">
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-6 w-12 rounded-md" />
        <Skeleton className="h-6 w-12 rounded-md" />
      </div>
      <div className="mb-5 flex items-center gap-2">
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-6 w-20 rounded-md" />
        <Skeleton className="h-6 w-16 rounded-md" />
      </div>

      <div className="flex flex-col gap-2.5">
        {Array.from({ length: 8 }).map((_, i) => (
          <Card key={i} className="flex-row items-center gap-4 p-4">
            <Skeleton className="size-4" />
            <Skeleton className="size-10 rounded-lg" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-48 max-w-full" />
              <Skeleton className="h-3 w-32" />
            </div>
            <Skeleton className="size-4" />
          </Card>
        ))}
      </div>
    </div>
  );
}
