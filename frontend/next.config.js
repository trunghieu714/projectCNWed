/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    domains: ["localhost"],
  },
  async rewrites() {
    return [
      {
        source: "/storage/:path*",
        destination: "http://backend:8000/storage/:path*",
      },
    ];
  },
};

module.exports = nextConfig;
