import path from "node:path";
import { fileURLToPath } from "node:url";

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Builds a self-contained server in .next/standalone, used by the Docker image.
  output: "standalone",
  experimental: {
    // Trace files from this folder only, so standalone/server.js sits at the top level
    // even though the repo root (one level up) also has files.
    outputFileTracingRoot: path.dirname(fileURLToPath(import.meta.url)),
  },
};

export default nextConfig;
