import { getDb } from "@trendradar/db";

export function db() {
  return getDb();
}

/** Run a query, returning `fallback` if the DB isn't configured/reachable (dev without Supabase). */
export async function safe<T>(fn: (d: ReturnType<typeof getDb>) => Promise<T>, fallback: T): Promise<T> {
  try {
    return await fn(getDb());
  } catch (e) {
    if (process.env.NODE_ENV !== "production") console.warn("[db] unavailable:", (e as Error).message);
    return fallback;
  }
}
