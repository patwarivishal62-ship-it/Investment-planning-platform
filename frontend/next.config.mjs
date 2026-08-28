/** @type {import('next').NextConfig} */
const backendUrl = process.env.BACKEND_URL || "http://127.0.0.1:8000";

const nextConfig = {
  reactStrictMode: true,
  // The browser only ever talks to this Next.js server on a relative /api path.
  // The backend is proxied server-side, so no CORS and no exposed backend port.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
  // Allow the sandboxed preview host to load dev assets.
  allowedDevOrigins: ["*"],
};

export default nextConfig;
