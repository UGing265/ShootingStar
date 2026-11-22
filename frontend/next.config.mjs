/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  distDir: process.env.NEXT_DIST_DIR || ".next",
  // E2E only: Next's agent upgrade nudge kills `next dev` on first compile under an agent shell.
  ...(process.env.NEXT_DIST_DIR ? { experimental: { agentUpgrade: false } } : {}),
};

export default nextConfig;
