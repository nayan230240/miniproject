// Vite config for the React frontend.
// "host: true" lets Docker (and other machines) reach the dev server.

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
  },
});
