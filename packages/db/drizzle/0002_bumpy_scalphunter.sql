CREATE TABLE IF NOT EXISTS "peer_cache" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"project_id" uuid NOT NULL,
	"platform" "platform" NOT NULL,
	"handle" text NOT NULL,
	"is_peer" boolean NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "trending_sounds" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"region" text NOT NULL,
	"audio_id" text NOT NULL,
	"title" text,
	"author" text,
	"play_url" text,
	"cover_url" text,
	"is_original_sound" boolean,
	"is_commerce_music" boolean,
	"usage_signal" integer DEFAULT 0 NOT NULL,
	"example_urls" text[],
	"fetched_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "video_embeddings" (
	"video_id" uuid PRIMARY KEY NOT NULL,
	"model" text NOT NULL,
	"source_hash" text NOT NULL,
	"embedding" vector(1536) NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
ALTER TABLE "trends" ALTER COLUMN "status" DROP NOT NULL;--> statement-breakpoint
ALTER TABLE "projects" ADD COLUMN "owner_id" uuid;--> statement-breakpoint
ALTER TABLE "projects" ADD COLUMN "competitor_urls" text[];--> statement-breakpoint
ALTER TABLE "queries" ADD COLUMN "is_own" boolean DEFAULT false NOT NULL;--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "peer_cache" ADD CONSTRAINT "peer_cache_project_id_projects_id_fk" FOREIGN KEY ("project_id") REFERENCES "public"."projects"("id") ON DELETE no action ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "video_embeddings" ADD CONSTRAINT "video_embeddings_video_id_videos_id_fk" FOREIGN KEY ("video_id") REFERENCES "public"."videos"("id") ON DELETE cascade ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
CREATE UNIQUE INDEX IF NOT EXISTS "peer_cache_unique" ON "peer_cache" USING btree ("project_id","platform","handle");--> statement-breakpoint
CREATE UNIQUE INDEX IF NOT EXISTS "trending_sounds_region_audio" ON "trending_sounds" USING btree ("region","audio_id");--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "trending_sounds_region_rank" ON "trending_sounds" USING btree ("region","usage_signal");--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "projects_owner" ON "projects" USING btree ("owner_id");