import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Proxy API and WebSocket requests to the FastAPI backend during
  // development.  In production the frontend is either served by FastAPI
  // itself or placed behind a reverse proxy — so these rewrites are
  // dev-only.
  async rewrites() {
    return [
      {
        // REST API calls: /api/* → FastAPI
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
      {
        // WebSocket connections: /ws/* → FastAPI
        source: "/ws/:path*",
        destination: "http://localhost:8000/ws/:path*",
      },
    ];
  },
};

export default nextConfig;