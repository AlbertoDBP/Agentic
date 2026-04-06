import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // API proxy is handled by src/middleware.ts
};

export default nextConfig;
