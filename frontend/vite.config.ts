/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const proxyTarget = process.env.VITE_PROXY_TARGET || "http://localhost:8000";
// Public demo through a tunnel (docs/DEPLOYMENT.md): Vite only answers Host headers it
// knows, so allow quick-tunnel domains plus any extra ones listed in ALLOWED_HOSTS.
const allowedHosts = [".trycloudflare.com", ...(process.env.ALLOWED_HOSTS?.split(",") ?? [])];
const apiProxy = { "/api": { target: proxyTarget, changeOrigin: true } };

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: apiProxy,
    allowedHosts,
  },
  // `vite preview` serves the production build (what the Docker image runs).
  preview: {
    port: 5173,
    proxy: apiProxy,
    allowedHosts,
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["src/test/setup.ts"],
    // Playwright specs live under e2e/ and must never be collected by vitest.
    exclude: ["e2e/**", "node_modules/**", "dist/**"],
  },
});
