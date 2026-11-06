import { fileURLToPath, URL } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The UI is always compiled to static files (dist/) and served by FastAPI.
// `npm run watch` rebuilds on save during development; there is no Node
// server at runtime.
export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: mode === "development",
    // Keep everything as external files so the strict CSP (no inline
    // scripts/styles) holds.
    assetsInlineLimit: 0,
  },
}));
