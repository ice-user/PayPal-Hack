import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

// Fixtures live in /contracts (shared with Person B), so the dev server may read one level up.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      "@contracts": path.resolve(__dirname, "../contracts"),
      "@cases": path.resolve(__dirname, "../cases"),
    },
  },
  server: {
    port: 5173,
    fs: { allow: [".."] },
  },
});
