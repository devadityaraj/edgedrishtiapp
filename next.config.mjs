/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  // Enable static export for Python backend serving
  output: 'export',
  // Disable image optimization for static export
  reactCompiler: false,
  trailingSlash: true,
}

export default nextConfig
