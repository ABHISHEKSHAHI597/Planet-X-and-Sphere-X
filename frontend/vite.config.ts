/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The API lives at /api/v1 (implementation.md §5.1). In dev, proxy it to P's backend
// (uvicorn on :8000). With VITE_MOCK=1 the in-browser mock transport answers instead (workflow.md §8.5).
export default defineConfig({
  // "/" on our own host; "/<repository>/" for GitHub Pages (ParallaX Lite; src/lib/base.ts).
  base: process.env.VITE_BASE ?? "/",
  plugins: [react()],
  server: {
    proxy: { "/api": { target: process.env.PARALLAX_API ?? "http://localhost:8000", changeOrigin: true } },
  },
  build: {
    target: "es2022",
    sourcemap: true,
    // Aladin Lite is lazy-loaded into its own chunk (implementation.md §6.7: ≤ 400 KB gz without Aladin).
    chunkSizeWarningLimit: 2000,
  },
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.ts", "tests/**/*.test.tsx"],
  },
});
