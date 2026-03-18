import type { NextConfig } from "next";

// Destination for server-side proxy — resolves inside the Docker network.
// Set ADMIN_PANEL_URL as a build arg; falls back to localhost for local dev.
const adminPanelUrl = process.env.ADMIN_PANEL_URL || "http://localhost:8100";

const nextConfig: NextConfig = {
  output: "standalone",

  // Proxy /api/* to the admin panel so the browser never needs to know the
  // backend URL.  This eliminates CORS issues and makes the build portable.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${adminPanelUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
