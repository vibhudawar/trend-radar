import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";
import * as schema from "./schema";

export * from "./schema";
export * as enums from "./enums";

export type Platform = "tiktok" | "reels";

/**
 * Singleton Drizzle client over Supabase Postgres.
 * DATABASE_URL is the Supabase connection string (session pooler for the worker,
 * transaction pooler for serverless). Never hardcode it.
 */
let _db: ReturnType<typeof drizzle<typeof schema>> | undefined;

export function getDb(connectionString = process.env.DATABASE_URL) {
  if (!connectionString) throw new Error("DATABASE_URL is not set");
  if (!_db) {
    const client = postgres(connectionString, { prepare: false });
    _db = drizzle(client, { schema, casing: "snake_case" });
  }
  return _db;
}

export type Db = ReturnType<typeof getDb>;
