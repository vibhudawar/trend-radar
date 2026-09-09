import { SidebarTrigger } from "@/components/ui/sidebar";

export function TopBar({ title }: { title?: string }) {
  return (
    <header className="bg-background/80 sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 rounded-t-xl border-b px-4 backdrop-blur">
      <SidebarTrigger className="-ml-1" />
      {title ? <span className="text-sm font-medium">{title}</span> : null}
    </header>
  );
}
