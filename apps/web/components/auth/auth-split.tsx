import Link from "next/link";
import { Wordmark } from "@/components/shared/wordmark";

// Two-column auth shell: brand panel left, form right, centered on a muted background.
export function AuthSplit({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-muted flex min-h-svh flex-col items-center justify-center p-6 md:p-10">
      <div className="w-full max-w-sm md:max-w-3xl">
        <div className="bg-card text-card-foreground ring-foreground/10 overflow-hidden rounded-2xl shadow-sm ring-1">
          <div className="grid md:min-h-[480px] md:grid-cols-2">
            <div className="from-primary via-primary to-primary/80 relative hidden bg-gradient-to-br md:block">
              <div
                aria-hidden
                className="pointer-events-none absolute inset-0 opacity-[0.12]"
                style={{
                  backgroundImage:
                    "radial-gradient(circle at 20% 20%, white 1px, transparent 1px), radial-gradient(circle at 80% 65%, white 1px, transparent 1px)",
                  backgroundSize: "38px 38px",
                }}
              />
              <div className="relative flex h-full flex-col p-8 text-white">
                <Link href="/" className="w-fit">
                  <Wordmark className="text-2xl [&_span]:text-white" />
                </Link>
                <div className="mt-auto space-y-3">
                  <p className="text-2xl leading-[1.2] font-semibold tracking-tight text-balance">
                    Find what's winning. Make content that rides the wave.
                  </p>
                  <p className="text-sm leading-relaxed text-white/80">
                    Data-backed hooks, scripts, and trends — adapted to each client.
                  </p>
                </div>
              </div>
            </div>

            <div className="flex items-center p-6 md:p-8">
              <div className="w-full">
                <Link href="/" className="mb-6 inline-block md:hidden">
                  <Wordmark className="text-2xl" />
                </Link>
                {children}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
