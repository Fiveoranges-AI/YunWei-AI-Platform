import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const apiProxyTarget = process.env.JINTAI_API_PROXY_TARGET ?? "http://127.0.0.1:8000";
// --public (Tailscale/LAN demo, 方案 A): the browser only talks to vite; vite
// proxies to the two backends which stay on 127.0.0.1 (NOT exposed). Distinct
// prefixes because BOTH demos share the /api/win path on different ports.
// Strip the prefix so /<prefix>/api/win/... → <backend>/api/win/... AND
// /<prefix>/health → <backend>/health (health lives at the backend root).
const guangtianTarget = process.env.GUANGTIAN_API_PROXY_TARGET ?? "http://127.0.0.1:8001";

export default defineConfig({
  plugins: [react()],
  base: "/win/",
  build: {
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: true,
    target: "es2022",
  },
  server: {
    port: 5175,
    strictPort: false,
    host: true,
    proxy: {
      "/jintai-api": {
        target: apiProxyTarget,
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/jintai-api/, ""),
      },
      "/guangtian-api": {
        target: guangtianTarget,
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/guangtian-api/, ""),
      },
      "/api": {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
});
