import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          "react-vendor": ["react", "react-dom"],
          charts: ["recharts"],
          icons: ["lucide-react"],
        },
      },
    },
  },
  server: {
    host: "0.0.0.0",
    port: 8501,
    allowedHosts: true,
    proxy: {
      "/api": {
        target: "http://fastapi:8001",
        changeOrigin: true,
      },
    },
  },
});
