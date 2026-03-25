import type { NextConfig } from "next";

const adminPanelUrl = process.env.ADMIN_PANEL_URL || "http://localhost:8100";

const nextConfig: NextConfig = {
  output: "standalone",

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
