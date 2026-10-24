import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev mode, /api/* is forwarded to FastAPI on :8000 (prefix removed) - this mimics Nginx.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://localhost:8000", changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, "") } },
  },
});
