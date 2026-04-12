import type { NextConfig } from "next";
import path from "path";

import { getConfiguredServerApiBaseUrl } from "./src/lib/config/apiBase";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  reactCompiler: true,
  output: "standalone",
  // Disable built-in gzip compression so SSE streams are flushed per-event
  // instead of being buffered by the compressor.  In production, the reverse
  // proxy (nginx / CDN) handles compression for non-streaming responses.
  compress: false,
  transpilePackages: ["@pathfinder/shared"],
  turbopack: {
    root: path.resolve(process.cwd(), "../.."),
  },
  experimental: {
    serverActions: {
      bodySizeLimit: "2mb",
    },
  },
  async rewrites() {
    const apiBase = getConfiguredServerApiBaseUrl();
    return [
      {
        source: "/health/:path*",
        destination: `${apiBase}/health/:path*`,
      },
      {
        source: "/api/:path*",
        destination: `${apiBase}/api/:path*`,
      },
      {
        source: "/docs",
        destination: `${apiBase}/docs`,
      },
      {
        source: "/docs/:path*",
        destination: `${apiBase}/docs/:path*`,
      },
      {
        source: "/redoc",
        destination: `${apiBase}/redoc`,
      },
      {
        source: "/redoc/:path*",
        destination: `${apiBase}/redoc/:path*`,
      },
      {
        source: "/openapi.json",
        destination: `${apiBase}/openapi.json`,
      },
    ];
  },
};

export default nextConfig;
