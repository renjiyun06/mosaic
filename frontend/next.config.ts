import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Disable Turbopack due to Google Fonts compatibility issue
  // Turbopack is disabled via TURBOPACK=0 environment variable in package.json
};

export default nextConfig;
