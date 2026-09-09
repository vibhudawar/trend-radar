import OpenAI from "openai";
import { z } from "zod";
import { fetchProductPage } from "./fetch-url";

// The onboarding profile drives the whole pipeline (seeds + intent filter + adaptation).
// We read the product page and let the LLM propose it; the operator reviews/edits before saving.
export const ProposedProfile = z.object({
  name: z.string(),
  productDescription: z.string(),
  audience: z.string(),
  jobToBeDone: z.string(),
  // region is intentionally NOT proposed — the user sets it (we never infer market).
  platforms: z.array(z.enum(["tiktok", "reels"])),
  seedQueries: z.array(z.string()).max(8),
  competitors: z.array(z.string()).max(8), // suggested competitor/niche social handles to learn from
});
export type ProposedProfile = z.infer<typeof ProposedProfile>;

export async function proposeProfileFromUrl(url: string): Promise<ProposedProfile> {
  const { url: finalUrl, text } = await fetchProductPage(url);

  const key = process.env.OPENAI_API_KEY;
  if (!key) throw new Error("OPENAI_API_KEY is not set");
  const client = new OpenAI({ apiKey: key });

  const prompt = `You onboard a business into a UGC content-intelligence tool. From the product page text,
infer the marketing job-to-be-done and how products/tools LIKE this are pitched via short-form video
(the GOAL, not the product's topic). Return ONLY JSON:
{
  "name": business name,
  "productDescription": one tight paragraph of what it does (used to adapt hooks),
  "audience": who they sell to,
  "jobToBeDone": e.g. "get X to sign up/buy",
  "platforms": subset of ["tiktok","reels"] that fits the audience,
  "seedQueries": 5-7 SHORT search seeds (2-4 words each, keyword/hashtag style like a creator would
     tag or search — e.g. "amazon seller tips", "fix broken listings". NEVER full sentences; long
     phrases wreck search recall, especially on Instagram),
  "competitors": up to 6 competitor or niche creator/brand social handles (no leading @) that post
     pitch-style short-form for this audience — real, well-known ones; omit if unsure rather than invent
}

Do NOT include region/market — the user sets that themselves.

PRODUCT URL: ${finalUrl}
PAGE TEXT:
${text}`;

  const r = await client.chat.completions.create({
    model: process.env.ONBOARDING_MODEL ?? "gpt-5-mini",
    messages: [{ role: "user", content: prompt }],
    response_format: { type: "json_object" },
  });
  const raw = JSON.parse(r.choices[0]?.message?.content ?? "{}");
  return ProposedProfile.parse({ competitors: [], ...raw });
}
