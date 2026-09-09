/** @type {import('next').NextConfig} */
const nextConfig = {
  transpilePackages: ["@trendradar/db"],
  images: { remotePatterns: [{ protocol: "https", hostname: "**" }] },
};
export default nextConfig;
