import fs from "node:fs";
import path from "node:path";
import os from "node:os";

const packages = ["react", "react-dom", "katex", "vite", "@vitejs/plugin-react", "@fontsource-variable/ibm-plex-sans", "@fontsource/ibm-plex-mono", "@fontsource/marcellus"];
const requiredFiles = [
  ...packages.map((name) => `${name}/package.json`),
  "@fontsource-variable/ibm-plex-sans/wght.css", "@fontsource-variable/ibm-plex-sans/wght-italic.css",
  "@fontsource/ibm-plex-mono/400.css", "@fontsource/ibm-plex-mono/500.css", "@fontsource/marcellus/400.css",
  ...packages.filter((name) => name.startsWith("@fontsource")).map((name) => `${name}/LICENSE`),
];
const missingFiles = (directory) => requiredFiles.filter((name) => !fs.existsSync(path.join(directory, name)));
const complete = (directory) => missingFiles(directory).length === 0;
export function findSharedRoot() {
  if (process.env.MF_SHARED_NODE_MODULES) {
    const root = path.resolve(process.env.MF_SHARED_NODE_MODULES);
    const missing = missingFiles(root);
    if (missing.length) throw new Error(`MF_SHARED_NODE_MODULES is missing shared frontend files: ${missing.join(", ")} (${root}). Install the frontend packages declared in web/package.json in a user-wide or machine-wide npm location. Project-local installations are not used.`);
    return fs.realpathSync(root);
  }
  // Windows packaged terminals may expose an AppData alias while child imports
  // resolve its physical package cache. Choose one physical root for every alias.
  if (process.platform === "win32" && process.env.LOCALAPPDATA) {
    const packages = path.join(process.env.LOCALAPPDATA, "Packages");
    if (fs.existsSync(packages)) {
      const candidates = fs.readdirSync(packages, { withFileTypes: true }).filter((entry) => entry.isDirectory()).map((entry) => path.join(packages, entry.name, "LocalCache", "Roaming", "npm", "node_modules")).filter(complete);
      if (candidates.length === 1) return fs.realpathSync(candidates[0]);
      if (candidates.length > 1) throw new Error("More than one shared frontend installation was found. Set MF_SHARED_NODE_MODULES to the intended physical npm global node_modules directory.");
    }
  }
  const candidates = [
    ...(process.env.APPDATA ? [path.join(process.env.APPDATA, "npm", "node_modules")] : []),
    path.join(path.dirname(process.execPath), "node_modules"),
    path.resolve(path.dirname(process.execPath), "../lib/node_modules"),
    path.join(os.homedir(), ".npm-global/lib/node_modules"),
  ];
  const root = candidates.find(complete);
  if (!root) throw new Error("Install the frontend packages declared in web/package.json in a user-wide or machine-wide npm location, then set MF_SHARED_NODE_MODULES to its node_modules directory. Project-local installations are not used.");
  return fs.realpathSync(root);
}
export const sharedRoot = findSharedRoot();
export const sharedPackage = (name, suffix = "") => path.join(sharedRoot, name, suffix).replaceAll("\\", "/");
