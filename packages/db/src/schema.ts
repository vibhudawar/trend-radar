import {
  bigint,
  boolean,
  index,
  integer,
  jsonb,
  numeric,
  pgTable,
  primaryKey,
  text,
  timestamp,
  uniqueIndex,
  uuid,
} from "drizzle-orm/pg-core";
import {
  alertType,
  analysisStatus,
  confidence,
  contentType,
  creditCall,
  lane,
  lifecycle,
  platform,
  queryType,
  scoreFlag,
  trendStatus,
  trendType,
} from "./enums";

// Re-export enums so drizzle-kit registers them (emits CREATE TYPE in migrations).
export * from "./enums";

// Conventions (plans/DATABASE_SCHEMA.md §1): uuid pks; timestamptz UTC; counts bigint & nullable
// (never faked to 0); workspace_id present for future RLS; soft-delete only where user-facing.
const id = () => uuid("id").primaryKey().defaultRandom();
const createdAt = () => timestamp("created_at", { withTimezone: true }).notNull().defaultNow();
const updatedAt = () => timestamp("updated_at", { withTimezone: true }).notNull().defaultNow();

// --- projects: an onboarded business/SaaS (Ecombox, Home Design AI). ----------
// The onboarding profile drives the whole pipeline: seeds + intent filter + adaptation.
export const projects = pgTable("projects", {
  id: id(),
  workspaceId: uuid("workspace_id"),
  ownerId: uuid("owner_id"), // Supabase auth.users.id — the creator; reads are scoped to this
  name: text("name").notNull(), // business name
  productUrl: text("product_url"),
  productDescription: text("product_description"), // what they sell (feeds adaptation)
  audience: text("audience"), // who they sell to
  jobToBeDone: text("job_to_be_done"), // e.g. "get online sellers to sign up"
  region: text("region"), // e.g. "IN", "US"
  platforms: platform("platforms").array().notNull(),
  status: text("status").notNull().default("idle"), // idle | running | ready | failed
  lastRefreshedAt: timestamp("last_refreshed_at", { withTimezone: true }),
  lastRunCredits: integer("last_run_credits"),
  createdAt: createdAt(),
  updatedAt: updatedAt(),
  deletedAt: timestamp("deleted_at", { withTimezone: true }),
}, (t) => [index("projects_owner").on(t.ownerId)]);

// --- queries: goal-matched seed inputs per project --------------------------
export const queries = pgTable(
  "queries",
  {
    id: id(),
    projectId: uuid("project_id").notNull().references(() => projects.id),
    platform: platform("platform").notNull(),
    type: queryType("type").notNull(),
    value: text("value").notNull(),
    active: boolean("active").notNull().default(true),
    lastRunAt: timestamp("last_run_at", { withTimezone: true }),
    createdAt: createdAt(),
    deletedAt: timestamp("deleted_at", { withTimezone: true }),
  },
  (t) => [uniqueIndex("queries_unique").on(t.projectId, t.platform, t.type, t.value)],
);

// --- authors: a creator account; baseline_median_views = THE account baseline
export const authors = pgTable(
  "authors",
  {
    id: id(),
    platform: platform("platform").notNull(),
    handle: text("handle").notNull(),
    isVerified: boolean("is_verified"),
    followerCount: bigint("follower_count", { mode: "number" }),
    baselineMedianViews: bigint("baseline_median_views", { mode: "number" }),
    lastProfiledAt: timestamp("last_profiled_at", { withTimezone: true }),
    createdAt: createdAt(),
    updatedAt: updatedAt(),
  },
  (t) => [uniqueIndex("authors_platform_handle").on(t.platform, t.handle)],
);

// --- videos: identity row (one per unique video). Metrics live in snapshots. -
export const videos = pgTable(
  "videos",
  {
    id: id(),
    platform: platform("platform").notNull(),
    videoId: text("video_id").notNull(),
    authorId: uuid("author_id").references(() => authors.id),
    projectId: uuid("project_id").references(() => projects.id),
    caption: text("caption"),
    contentType: contentType("content_type"), // from the intent filter
    audioId: text("audio_id"),
    audioTitle: text("audio_title"),
    url: text("url").notNull(),
    durationS: integer("duration_s"),
    takenAt: timestamp("taken_at", { withTimezone: true }),
    firstSeenAt: timestamp("first_seen_at", { withTimezone: true }).notNull().defaultNow(),
    rawPayload: jsonb("raw_payload").notNull(),
    createdAt: createdAt(),
  },
  (t) => [
    uniqueIndex("videos_platform_video_id").on(t.platform, t.videoId), // dedupe key
    index("videos_project").on(t.projectId),
    index("videos_author").on(t.authorId),
    index("videos_audio").on(t.audioId),
    index("videos_platform_taken").on(t.platform, t.takenAt),
  ],
);

// --- video_snapshots: append-only time-series. share/save null on IG. -------
export const videoSnapshots = pgTable(
  "video_snapshots",
  {
    id: id(),
    videoId: uuid("video_id").notNull().references(() => videos.id),
    capturedAt: timestamp("captured_at", { withTimezone: true }).notNull().defaultNow(),
    viewCount: bigint("view_count", { mode: "number" }),
    likeCount: bigint("like_count", { mode: "number" }),
    commentCount: bigint("comment_count", { mode: "number" }),
    shareCount: bigint("share_count", { mode: "number" }), // TikTok fills; IG null unless Apify
    saveCount: bigint("save_count", { mode: "number" }),
  },
  (t) => [index("snapshots_video_captured").on(t.videoId, t.capturedAt.desc())],
);

// --- scores: selection output. Never rank by raw views. ---------------------
export const scores = pgTable(
  "scores",
  {
    id: id(),
    videoId: uuid("video_id").notNull().references(() => videos.id),
    strategy: text("strategy").notNull(),
    lane: lane("lane").notNull(),
    accountOutperformance: numeric("account_outperformance"), // PRIMARY: views ÷ creator median
    saveRate: numeric("save_rate"),
    shareRate: numeric("share_rate"),
    likeRate: numeric("like_rate"),
    commentRate: numeric("comment_rate"),
    velocity: numeric("velocity"),
    nicheSpike: numeric("niche_spike"),
    durationS: integer("duration_s"),
    ageDays: integer("age_days"),
    composite: numeric("composite").notNull(),
    flag: scoreFlag("flag").notNull().default("ok"),
    computedAt: timestamp("computed_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (t) => [
    index("scores_video_computed").on(t.videoId, t.computedAt.desc()),
    index("scores_composite").on(t.composite.desc()),
  ],
);

// --- analyses: real-hook output, outliers only, cached by video -------------
export const analyses = pgTable(
  "analyses",
  {
    id: id(),
    videoId: uuid("video_id").notNull().references(() => videos.id),
    status: analysisStatus("status").notNull().default("pending"),
    hookText: text("hook_text"),
    hookType: text("hook_type"),
    hookSource: text("hook_source"), // onscreen | spoken | caption (fidelity flag)
    emotionalDriver: text("emotional_driver"),
    format: text("format"),
    structure: text("structure"),
    replicationScore: integer("replication_score"),
    transcript: text("transcript"),
    onscreenText: text("onscreen_text"),
    provider: text("provider"),
    model: text("model"),
    promptVersion: text("prompt_version"),
    createdAt: createdAt(),
    updatedAt: updatedAt(),
  },
  (t) => [uniqueIndex("analyses_video").on(t.videoId)],
);

// --- concepts: THE deliverable — recurring concepts with evidence -----------
export const concepts = pgTable(
  "concepts",
  {
    id: id(),
    projectId: uuid("project_id").notNull().references(() => projects.id),
    lane: lane("lane").notNull(),
    name: text("name").notNull(),
    pattern: text("pattern"),
    nVideos: integer("n_videos").notNull().default(0),
    nCreators: integer("n_creators").notNull().default(0),
    medianOutperformance: numeric("median_outperformance"),
    nicheSpike: numeric("niche_spike"),
    confidence: confidence("confidence").notNull(),
    lifecycle: lifecycle("lifecycle").notNull(),
    adaptedHook: text("adapted_hook"),
    format: text("format"),
    lengthS: integer("length_s"),
    testTarget: text("test_target"),
    script: jsonb("script"), // timecoded beats
    createdAt: createdAt(),
    updatedAt: updatedAt(),
  },
  (t) => [index("concepts_project_lane").on(t.projectId, t.lane)],
);

export const conceptMembers = pgTable(
  "concept_members",
  {
    conceptId: uuid("concept_id").notNull().references(() => concepts.id),
    videoId: uuid("video_id").notNull().references(() => videos.id),
    addedAt: createdAt(),
  },
  (t) => [primaryKey({ columns: [t.conceptId, t.videoId] })],
);

// --- trends (Phase 3) -------------------------------------------------------
export const trends = pgTable(
  "trends",
  {
    id: id(),
    projectId: uuid("project_id").notNull().references(() => projects.id),
    type: trendType("type").notNull(),
    key: text("key").notNull(),
    label: text("label"),
    status: trendStatus("status").notNull(),
    growthRate: numeric("growth_rate"),
    memberCount: integer("member_count").notNull().default(0),
    firstDetectedAt: timestamp("first_detected_at", { withTimezone: true }),
    updatedAt: updatedAt(),
  },
  (t) => [index("trends_project_status").on(t.projectId, t.status)],
);

export const trendMembers = pgTable(
  "trend_members",
  {
    trendId: uuid("trend_id").notNull().references(() => trends.id),
    videoId: uuid("video_id").notNull().references(() => videos.id),
    addedAt: createdAt(),
  },
  (t) => [primaryKey({ columns: [t.trendId, t.videoId] })],
);

// --- alerts (Phase 3) -------------------------------------------------------
export const alerts = pgTable(
  "alerts",
  {
    id: id(),
    projectId: uuid("project_id").notNull().references(() => projects.id),
    type: alertType("type").notNull(),
    payload: jsonb("payload").notNull(),
    read: boolean("read").notNull().default(false),
    createdAt: createdAt(),
  },
  (t) => [index("alerts_project_created").on(t.projectId, t.createdAt.desc())],
);

// --- watchlist --------------------------------------------------------------
export const watchlist = pgTable(
  "watchlist",
  {
    id: id(),
    projectId: uuid("project_id").notNull().references(() => projects.id),
    authorId: uuid("author_id").notNull().references(() => authors.id),
    createdAt: createdAt(),
    deletedAt: timestamp("deleted_at", { withTimezone: true }),
  },
  (t) => [uniqueIndex("watchlist_project_author").on(t.projectId, t.authorId)],
);

// --- credit_log: every DataSource call --------------------------------------
export const creditLog = pgTable(
  "credit_log",
  {
    id: id(),
    source: text("source").notNull(),
    call: creditCall("call").notNull(),
    credits: integer("credits").notNull(),
    resultCount: integer("result_count"),
    projectId: uuid("project_id").references(() => projects.id),
    createdAt: createdAt(),
  },
  (t) => [index("credit_log_created").on(t.createdAt), index("credit_log_source").on(t.source, t.createdAt)],
);

// --- llm_log: LLM spend (Phase 2) -------------------------------------------
export const llmLog = pgTable("llm_log", {
  id: id(),
  provider: text("provider").notNull(),
  model: text("model").notNull(),
  task: text("task").notNull(),
  tokensIn: integer("tokens_in"),
  tokensOut: integer("tokens_out"),
  batch: boolean("batch").notNull().default(false),
  projectId: uuid("project_id").references(() => projects.id),
  createdAt: createdAt(),
});
