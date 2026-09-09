import { AppSidebar } from "@/components/shared/app-sidebar";
import { TopBar } from "@/components/shared/top-bar";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { supabaseServer } from "@/lib/supabase/server";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const { data } = await supabaseServer().then((s) => s.auth.getUser());

  return (
    <SidebarProvider>
      <AppSidebar email={data.user?.email ?? null} />
      <SidebarInset>
        <TopBar />
        <div className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <div className="mx-auto w-full max-w-6xl">{children}</div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
