import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { sharedPackage } from "./shared-deps.mjs";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const vite = await import(pathToFileURL(sharedPackage("vite", "dist/node/index.js")).href);
const command = process.argv[2] || "dev";
const configFile = path.join(webRoot, "vite.config.js");
if (command === "build") {
  await vite.build({ root: webRoot, configFile });
  const { buildMathRuntime } = await import("./build-math-runtime.mjs");
  await buildMathRuntime();
} else if (command === "preview") {
  const server = await vite.preview({ root: webRoot, configFile }); server.printUrls();
} else if (command === "dev") {
  const server = await vite.createServer({ root: webRoot, configFile }); await server.listen(); server.printUrls();
} else throw new Error(`Unknown command: ${command}`);
