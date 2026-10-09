import type { NextConfig } from 'next';
// The README's two-terminal local setup must reach FastAPI even if the user
// has not created .env.local from the example file yet.
const configuredApiOrigin = process.env.API_ORIGIN;
const apiOrigin = (configuredApiOrigin || (process.env.NODE_ENV === 'development' ? 'http://127.0.0.1:8000' : '')).replace(/\/$/, '');
const nextConfig: NextConfig = {
  outputFileTracingRoot: process.cwd(),
  poweredByHeader: false,
  async rewrites() { return apiOrigin ? [{ source: '/api/:path*', destination: `${apiOrigin}/api/:path*` }] : []; },
};
export default nextConfig;
