import Link from "next/link";
import { AuthForm } from "@/components/auth/auth-form";
import { AuthSplit } from "@/components/auth/auth-split";

export const metadata = { title: "Log in — TrendRadar" };

export default function LoginPage() {
  return (
    <AuthSplit>
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-1.5">
          <h1 className="text-foreground text-2xl font-semibold tracking-tight">Welcome back</h1>
          <p className="text-muted-foreground text-sm text-balance">Log in to your TrendRadar account.</p>
        </div>
        <AuthForm mode="login" />
        <p className="text-muted-foreground text-center text-sm">
          No account?{" "}
          <Link href="/signup" className="text-foreground font-medium underline-offset-4 hover:underline">
            Sign up
          </Link>
        </p>
      </div>
    </AuthSplit>
  );
}
