ALTER TABLE "projects" ADD COLUMN "status" text DEFAULT 'idle' NOT NULL;--> statement-breakpoint
ALTER TABLE "projects" ADD COLUMN "last_refreshed_at" timestamp with time zone;--> statement-breakpoint
ALTER TABLE "projects" ADD COLUMN "last_run_credits" integer;