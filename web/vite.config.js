import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { sharedPackage } from "./scripts/shared-deps.mjs";

export default async () => {
  const { default: react } = await import(pathToFileURL(sharedPackage("@vitejs/plugin-react", "dist/index.mjs")).href);
  return {
  plugins: [react()],
  cacheDir: path.join(os.tmpdir(), "model-forge-codex-vite-cache"),
  resolve: {
    dedupe: ["react", "react-dom"], preserveSymlinks: true,
    alias: [
      { find: /^react-dom(?=\/|$)/, replacement: sharedPackage("react-dom") },
      { find: /^react(?=\/|$)/, replacement: sharedPackage("react") },
      { find: /^katex(?=\/|$)/, replacement: sharedPackage("katex") },
      { find: /^@fontsource-variable\/ibm-plex-sans(?=\/|$)/, replacement: sharedPackage("@fontsource-variable/ibm-plex-sans") },
      { find: /^@fontsource\/ibm-plex-mono(?=\/|$)/, replacement: sharedPackage("@fontsource/ibm-plex-mono") },
      { find: /^@fontsource\/marcellus(?=\/|$)/, replacement: sharedPackage("@fontsource/marcellus") },
    ],
  },
  server: {
    host: "127.0.0.1", port: Number(process.env.MF_WEB_PORT || 5173),
    // Font stylesheets reference files in the shared installation outside web/.
    fs: { allow: [path.dirname(fileURLToPath(import.meta.url)), sharedPackage("katex", "dist"),
      sharedPackage("@fontsource-variable/ibm-plex-sans"), sharedPackage("@fontsource/ibm-plex-mono"), sharedPackage("@fontsource/marcellus")] },
    proxy: {
      "/api": { target: process.env.MF_API_URL || "http://127.0.0.1:8766", changeOrigin: false },
    },
  },
  build: { outDir: "dist" },
};
};
