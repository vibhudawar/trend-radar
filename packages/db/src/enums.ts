import { pgEnum } from "drizzle-orm/pg-core";

// See plans/DATABASE_SCHEMA.md §2. Enums declared once, mirrored in the worker (Pydantic).
export const platform = pgEnum("platform", ["tiktok", "reels"]);
export const queryType = pgEnum("query_type", ["hashtag", "keyword", "sound", "account"]);
export const contentType = pgEnum("content_type", ["pitch", "education", "other"]);
export const lane = pgEnum("lane", ["rising", "proven"]);
export const confidence = pgEnum("confidence", ["high", "medium", "emerging"]);
export const lifecycle = pgEnum("lifecycle", ["emerging", "growing", "mature", "declining"]);
export const scoreFlag = pgEnum("score_flag", ["ok", "approximated", "no_baseline", "noise"]);
export const trendType = pgEnum("trend_type", ["sound", "format", "hook"]);
export const trendStatus = pgEnum("trend_status", ["rising", "peak", "declining"]);
export const alertType = pgEnum("alert_type", ["breakout", "trend_rising", "competitor", "saturation"]);
export const analysisStatus = pgEnum("analysis_status", ["pending", "done", "failed"]);
export const creditCall = pgEnum("credit_call", ["search", "video_detail", "author_videos", "transcript"]);
