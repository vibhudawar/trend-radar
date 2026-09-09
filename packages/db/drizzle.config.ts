import { readFileSync } from "node:fs";
import { defineConfig } from "drizzle-kit";

// Load DATABASE_URL from the backend env (worker/.env).
try {
  for (const line of readFileSync(new URL("../../worker/.env", import.meta.url), "utf8").split("\n")) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (m && !process.env[m[1]!]) process.env[m[1]!] = m[2]!.replace(/^["']|["']$/g, "");
  }
} catch {
  /* no .env.local yet — DATABASE_URL may come from the shell env */
}

export default defineConfig({
  schema: "./src/schema.ts",
  out: "./drizzle",
  dialect: "postgresql",
  dbCredentials: {
    // Supabase Postgres connection string. Set in packages/db/.env
    url: process.env.DATABASE_URL ?? "",
  },
  casing: "snake_case",
});
