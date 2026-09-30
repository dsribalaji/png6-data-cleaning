import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Note: Backend FastAPI currently has no global "/api" prefix; routes are mounted at root
// (e.g. /datasets, /profile, /plans). This proxy for "/api" is kept as PROVISIONAL
// if the backend is later mounted behind an /api prefix or gateway.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
