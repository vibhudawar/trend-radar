DROP INDEX IF EXISTS "trending_sounds_region_audio";--> statement-breakpoint
DROP INDEX IF EXISTS "trending_sounds_region_rank";--> statement-breakpoint
ALTER TABLE "trending_sounds" ADD COLUMN "platform" text NOT NULL;--> statement-breakpoint
CREATE UNIQUE INDEX IF NOT EXISTS "trending_sounds_region_platform_audio" ON "trending_sounds" USING btree ("region","platform","audio_id");--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "trending_sounds_region_platform_rank" ON "trending_sounds" USING btree ("region","platform","usage_signal");