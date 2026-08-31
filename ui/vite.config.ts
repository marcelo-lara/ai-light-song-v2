/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Target: Chrome 151 only (the operator's browser). No cross-browser fallbacks,
// polyfills or autoprefixer — build to esnext and use modern web APIs freely.
//
// The dev-server `/data` static mount + `PUT /api/human-hints/<song>` /
// `PUT /api/song-facts/<song>` handlers are ported from ui.old/vite.config.js in
// plan item 2. This shell config only serves the app.
export default defineConfig({
  plugins: [react()],
  build: {
    target: "esnext",
  },
  server: {
    host: "0.0.0.0",
    port: 8080,
    strictPort: true,
    watch: {
      usePolling: true,
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["src/test/setup.ts"],
    css: true,
  },
});
