const path = require("path");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  transpilePackages: ["@pathfinder/shared"],
  turbopack: {
    root: path.resolve(__dirname, "../.."),
  },
  experimental: {
    serverActions: {
      bodySizeLimit: "2mb",
    },
  },
  async rewrites() {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [
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

module.exports = nextConfig;
