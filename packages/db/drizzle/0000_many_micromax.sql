CREATE TYPE "public"."alert_type" AS ENUM('breakout', 'trend_rising', 'competitor', 'saturation');--> statement-breakpoint
CREATE TYPE "public"."analysis_status" AS ENUM('pending', 'done', 'failed');--> statement-breakpoint
CREATE TYPE "public"."confidence" AS ENUM('high', 'medium', 'emerging');--> statement-breakpoint
CREATE TYPE "public"."content_type" AS ENUM('pitch', 'education', 'other');--> statement-breakpoint
CREATE TYPE "public"."credit_call" AS ENUM('search', 'video_detail', 'author_videos', 'transcript');--> statement-breakpoint
CREATE TYPE "public"."lane" AS ENUM('rising', 'proven');--> statement-breakpoint
CREATE TYPE "public"."lifecycle" AS ENUM('emerging', 'growing', 'mature', 'declining');--> statement-breakpoint
CREATE TYPE "public"."platform" AS ENUM('tiktok', 'reels');--> statement-breakpoint
CREATE TYPE "public"."query_type" AS ENUM('hashtag', 'keyword', 'sound', 'account');--> statement-breakpoint
CREATE TYPE "public"."score_flag" AS ENUM('ok', 'approximated', 'no_baseline', 'noise');--> statement-breakpoint
CREATE TYPE "public"."trend_status" AS ENUM('rising', 'peak', 'declining');--> statement-breakpoint
CREATE TYPE "public"."trend_type" AS ENUM('sound', 'format', 'hook');--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "alerts" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"project_id" uuid NOT NULL,
	"type" "alert_type" NOT NULL,
	"payload" jsonb NOT NULL,
	"read" boolean DEFAULT false NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "analyses" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"video_id" uuid NOT NULL,
	"status" "analysis_status" DEFAULT 'pending' NOT NULL,
	"hook_text" text,
	"hook_type" text,
	"hook_source" text,
	"emotional_driver" text,
	"format" text,
	"structure" text,
	"replication_score" integer,
	"transcript" text,
	"onscreen_text" text,
	"provider" text,
	"model" text,
	"prompt_version" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "authors" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"platform" "platform" NOT NULL,
	"handle" text NOT NULL,
	"is_verified" boolean,
	"follower_count" bigint,
	"baseline_median_views" bigint,
	"last_profiled_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "concept_members" (
	"concept_id" uuid NOT NULL,
	"video_id" uuid NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "concept_members_concept_id_video_id_pk" PRIMARY KEY("concept_id","video_id")
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "concepts" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"project_id" uuid NOT NULL,
	"lane" "lane" NOT NULL,
	"name" text NOT NULL,
	"pattern" text,
	"n_videos" integer DEFAULT 0 NOT NULL,
	"n_creators" integer DEFAULT 0 NOT NULL,
	"median_outperformance" numeric,
	"niche_spike" numeric,
	"confidence" "confidence" NOT NULL,
	"lifecycle" "lifecycle" NOT NULL,
	"adapted_hook" text,
	"format" text,
	"length_s" integer,
	"test_target" text,
	"script" jsonb,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "credit_log" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"source" text NOT NULL,
	"call" "credit_call" NOT NULL,
	"credits" integer NOT NULL,
	"result_count" integer,
	"project_id" uuid,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "llm_log" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"provider" text NOT NULL,
	"model" text NOT NULL,
	"task" text NOT NULL,
	"tokens_in" integer,
	"tokens_out" integer,
	"batch" boolean DEFAULT false NOT NULL,
	"project_id" uuid,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "projects" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"workspace_id" uuid,
	"name" text NOT NULL,
	"product_url" text,
	"product_description" text,
	"audience" text,
	"job_to_be_done" text,
	"region" text,
	"platforms" "platform"[] NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"deleted_at" timestamp with time zone
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "queries" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"project_id" uuid NOT NULL,
	"platform" "platform" NOT NULL,
	"type" "query_type" NOT NULL,
	"value" text NOT NULL,
	"active" boolean DEFAULT true NOT NULL,
	"last_run_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"deleted_at" timestamp with time zone
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "scores" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"video_id" uuid NOT NULL,
	"strategy" text NOT NULL,
	"lane" "lane" NOT NULL,
	"account_outperformance" numeric,
	"save_rate" numeric,
	"share_rate" numeric,
	"like_rate" numeric,
	"comment_rate" numeric,
	"velocity" numeric,
	"niche_spike" numeric,
	"duration_s" integer,
	"age_days" integer,
	"composite" numeric NOT NULL,
	"flag" "score_flag" DEFAULT 'ok' NOT NULL,
	"computed_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "trend_members" (
	"trend_id" uuid NOT NULL,
	"video_id" uuid NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "trend_members_trend_id_video_id_pk" PRIMARY KEY("trend_id","video_id")
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "trends" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"project_id" uuid NOT NULL,
	"type" "trend_type" NOT NULL,
	"key" text NOT NULL,
	"label" text,
	"status" "trend_status" NOT NULL,
	"growth_rate" numeric,
	"member_count" integer DEFAULT 0 NOT NULL,
	"first_detected_at" timestamp with time zone,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "video_snapshots" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"video_id" uuid NOT NULL,
	"captured_at" timestamp with time zone DEFAULT now() NOT NULL,
	"view_count" bigint,
	"like_count" bigint,
	"comment_count" bigint,
	"share_count" bigint,
	"save_count" bigint
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "videos" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"platform" "platform" NOT NULL,
	"video_id" text NOT NULL,
	"author_id" uuid,
	"project_id" uuid,
	"caption" text,
	"content_type" "content_type",
	"audio_id" text,
	"audio_title" text,
	"url" text NOT NULL,
	"duration_s" integer,
	"taken_at" timestamp with time zone,
	"first_seen_at" timestamp with time zone DEFAULT now() NOT NULL,
	"raw_payload" jsonb NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "watchlist" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"project_id" uuid NOT NULL,
	"author_id" uuid NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"deleted_at" timestamp with time zone
);
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "alerts" ADD CONSTRAINT "alerts_project_id_projects_id_fk" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE no action ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "analyses" ADD CONSTRAINT "analyses_video_id_videos_id_fk" FOREIGN KEY ("video_id") REFERENCES "public"."videos"("id") ON DELETE no action ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "concept_members" ADD CONSTRAINT "concept_members_concept_id_concepts_id_fk" FOREIGN KEY ("concept_id") REFERENCES "public"."concepts"("id") ON DELETE no action ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "concept_members" ADD CONSTRAINT "concept_members_video_id_videos_id_fk" FOREIGN KEY ("video_id") REFERENCES "public"."videos"("id") ON DELETE no action ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "concepts" ADD CONSTRAINT "concepts_project_id_projects_id_fk" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE no action ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "credit_log" ADD CONSTRAINT "credit_log_project_id_projects_id_fk" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE no action ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "llm_log" ADD CONSTRAINT "llm_log_project_id_projects_id_fk" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE no action ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "queries" ADD CONSTRAINT "queries_project_id_projects_id_fk" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE no action ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "scores" ADD CONSTRAINT "scores_video_id_videos_id_fk" FOREIGN KEY ("video_id") REFERENCES "public"."videos"("id") ON DELETE no action ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "trend_members" ADD CONSTRAINT "trend_members_trend_id_trends_id_fk" FOREIGN KEY ("trend_id") REFERENCES "public"."trends"("id") ON DELETE no action ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "trend_members" ADD CONSTRAINT "trend_members_video_id_videos_id_fk" FOREIGN KEY ("video_id") REFERENCES "public"."videos"("id") ON DELETE no action ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "trends" ADD CONSTRAINT "trends_project_id_projects_id_fk" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE no action ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "video_snapshots" ADD CONSTRAINT "video_snapshots_video_id_videos_id_fk" FOREIGN KEY ("video_id") REFERENCES "public"."videos"("id") ON DELETE no action ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "videos" ADD CONSTRAINT "videos_author_id_authors_id_fk" FOREIGN KEY ("author_id") REFERENCES "public"."authors"("id") ON DELETE no action ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "videos" ADD CONSTRAINT "videos_project_id_projects_id_fk" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE no action ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "watchlist" ADD CONSTRAINT "watchlist_project_id_projects_id_fk" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE no action ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "watchlist" ADD CONSTRAINT "watchlist_author_id_authors_id_fk" FOREIGN KEY ("author_id") REFERENCES "public"."authors"("id") ON DELETE no action ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "alerts_project_created" ON "alerts" USING btree ("project_id","created_at" DESC NULLS LAST);--> statement-breakpoint
CREATE UNIQUE INDEX IF NOT EXISTS "analyses_video" ON "analyses" USING btree ("video_id");--> statement-breakpoint
CREATE UNIQUE INDEX IF NOT EXISTS "authors_platform_handle" ON "authors" USING btree ("platform","handle");--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "concepts_project_lane" ON "concepts" USING btree ("project_id","lane");--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "credit_log_created" ON "credit_log" USING btree ("created_at");--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "credit_log_source" ON "credit_log" USING btree ("source","created_at");--> statement-breakpoint
CREATE UNIQUE INDEX IF NOT EXISTS "queries_unique" ON "queries" USING btree ("project_id","platform","type","value");--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "scores_video_computed" ON "scores" USING btree ("video_id","computed_at" DESC NULLS LAST);--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "scores_composite" ON "scores" USING btree ("composite" DESC NULLS LAST);--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "trends_project_status" ON "trends" USING btree ("project_id","status");--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "snapshots_video_captured" ON "video_snapshots" USING btree ("video_id","captured_at" DESC NULLS LAST);--> statement-breakpoint
CREATE UNIQUE INDEX IF NOT EXISTS "videos_platform_video_id" ON "videos" USING btree ("platform","video_id");--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "videos_project" ON "videos" USING btree ("project_id");--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "videos_author" ON "videos" USING btree ("author_id");--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "videos_audio" ON "videos" USING btree ("audio_id");--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "videos_platform_taken" ON "videos" USING btree ("platform","taken_at");--> statement-breakpoint
CREATE UNIQUE INDEX IF NOT EXISTS "watchlist_project_author" ON "watchlist" USING btree ("project_id","author_id");