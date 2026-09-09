import { cn } from "@/lib/utils";

export function Wordmark({ iconOnly, className }: { iconOnly?: boolean; className?: string }) {
  return (
    <span className={cn("flex items-center gap-2 font-bold tracking-tight", className)}>
      <span className="inline-block size-6 shrink-0 rounded-md bg-gradient-to-br from-primary to-chart-2" />
      {!iconOnly && <span>TrendRadar</span>}
    </span>
  );
}
