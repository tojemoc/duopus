import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

/** Dev server proxy target (Docker Compose sets `http://api:8000`). */
const apiProxy = process.env.DUOPUS_API_PROXY ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  base: "/",
  server: {
    port: 5173,
    proxy: {
      "/api": apiProxy,
    },
  },
});
