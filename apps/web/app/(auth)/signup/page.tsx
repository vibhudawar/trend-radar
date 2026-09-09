import Link from "next/link";
import { AuthForm } from "@/components/auth/auth-form";
import { AuthSplit } from "@/components/auth/auth-split";

export const metadata = { title: "Sign up — TrendRadar" };

export default function SignupPage() {
  return (
    <AuthSplit>
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-1.5">
          <h1 className="text-foreground text-2xl font-semibold tracking-tight">Create your account</h1>
          <p className="text-muted-foreground text-sm text-balance">Start finding what's working.</p>
        </div>
        <AuthForm mode="signup" />
        <p className="text-muted-foreground text-center text-sm">
          Already have an account?{" "}
          <Link href="/login" className="text-foreground font-medium underline-offset-4 hover:underline">
            Log in
          </Link>
        </p>
      </div>
    </AuthSplit>
  );
}
