import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // base: "./" emits relative asset paths so the same bundle works under
  // any reverse-proxy prefix (e.g. /yinhu/super-xiaochen/) without rebuild.
  // The runtime <base href> injection in public/base-href.js translates
  // them into absolute tenant-prefixed URLs at load time.
  base: "./",
  build: {
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: true,
    target: "es2022",
  },
  server: {
    port: 5174,
    strictPort: false,
    host: true,
  },
});
