import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { defineConfig } from "vite";
// @ts-expect-error Local build-only module has no declaration file.
import { renderDemo } from "./scripts/demo.mjs";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    {
      name: "localized-demo",
      configureServer(server) {
        server.middlewares.use(async (req, res, next) => {
          const pathname = req.url?.split("?")[0];
          if (pathname !== "/demo.html" && pathname !== "/zh/demo.html")
            return next();
          res.setHeader("Content-Type", "text/html; charset=utf-8");
          res.end(
            await renderDemo(pathname.startsWith("/zh/") ? "zh-CN" : "en")
          );
        });
      },
    },
  ],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "client", "src"),
      "@shared": path.resolve(import.meta.dirname, "shared"),
      "@assets": path.resolve(import.meta.dirname, "attached_assets"),
    },
  },
  envDir: path.resolve(import.meta.dirname),
  root: path.resolve(import.meta.dirname, "client"),
  build: {
    outDir: path.resolve(import.meta.dirname, "dist/public"),
    emptyOutDir: true,
  },
  server: {
    port: 3000,
    strictPort: false,
    host: true,
    fs: {
      strict: true,
      deny: ["**/.*"],
    },
  },
});
