/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // 允许访问后端 API
  async rewrites() {
    return []
  },
}

module.exports = nextConfig
