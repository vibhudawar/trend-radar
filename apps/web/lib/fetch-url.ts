import dns from "node:dns/promises";
import net from "node:net";

// SSRF mitigation for the paste-URL onboarding: the operator supplies arbitrary client
// product URLs, so a fixed domain allowlist can't be used. We instead: allow only http/https,
// resolve the host and reject any private/reserved IP, forbid redirects, cap time + size.
// Caveat: DNS rebinding is not fully closed here (resolve→fetch TOCTOU); acceptable for an
// internal single-operator tool. For public/multi-tenant use, route through an egress proxy
// that pins the validated IP.

function isBlockedIp(ip: string): boolean {
  if (net.isIPv4(ip)) {
    const [a, b] = ip.split(".").map(Number) as [number, number, number, number];
    if (a === 10 || a === 127 || a === 0) return true;
    if (a === 169 && b === 254) return true; // link-local + cloud metadata
    if (a === 172 && b >= 16 && b <= 31) return true;
    if (a === 192 && b === 168) return true;
    if (a === 100 && b >= 64 && b <= 127) return true; // CGNAT
    return false;
  }
  const v = ip.toLowerCase();
  if (v === "::1" || v === "::") return true;
  if (v.startsWith("fe80") || v.startsWith("fc") || v.startsWith("fd")) return true; // link-local + ULA
  if (v.startsWith("::ffff:")) return isBlockedIp(v.slice(7)); // IPv4-mapped
  return false;
}

const MAX_BYTES = 1_500_000;

export async function fetchProductPage(rawUrl: string): Promise<{ url: string; text: string }> {
  let u: URL;
  try {
    u = new URL(rawUrl.startsWith("http") ? rawUrl : `https://${rawUrl}`);
  } catch {
    throw new Error("Invalid URL");
  }
  if (u.protocol !== "http:" && u.protocol !== "https:") throw new Error("Only http/https allowed");

  const resolved = await dns.lookup(u.hostname, { all: true }).catch(() => {
    throw new Error("Could not resolve host");
  });
  if (resolved.length === 0 || resolved.some((r) => isBlockedIp(r.address))) {
    throw new Error("Host not allowed");
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 12_000);
  try {
    const res = await fetch(u.toString(), {
      redirect: "manual",
      signal: controller.signal,
      headers: { "User-Agent": "TrendRadar-Onboarding/1.0" },
    });
    if (res.status >= 300 && res.status < 400) throw new Error("Redirects are not followed");
    if (!res.ok) throw new Error(`Fetch failed (${res.status})`);
    const buf = await res.arrayBuffer();
    const html = Buffer.from(buf.slice(0, MAX_BYTES)).toString("utf8");
    return { url: u.toString(), text: htmlToText(html) };
  } finally {
    clearTimeout(timer);
  }
}

function htmlToText(html: string): string {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&[a-z]+;/gi, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 6000);
}
