import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

export const appRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const digest = (bytes) => createHash("sha256").update(bytes).digest("hex");

function filesWithin(root) {
  const files = [];
  function visit(directory) {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      if (entry.name === "__pycache__") continue;
      const absolute = path.join(directory, entry.name);
      if (entry.isSymbolicLink()) throw new Error(`Release files must not be symlinks: ${absolute}`);
      if (entry.isDirectory()) visit(absolute);
      else if (entry.isFile()) files.push(path.relative(root, absolute).replaceAll("\\", "/"));
    }
  }
  visit(root);
  return files.sort();
}

export function verifyCatalog(root) {
  const catalogRoot = path.join(root, "contracts");
  const manifest = fs.readFileSync(path.join(catalogRoot, "MANIFEST.sha256"));
  const pin = JSON.parse(fs.readFileSync(path.join(catalogRoot, "catalog-pin.json"), "utf8"));
  if (digest(manifest) !== pin.catalog_manifest_sha256) {
    throw new Error("The catalog manifest differs from its pin. Review and seal the catalog before packaging.");
  }
  const entries = new Set();
  for (const line of manifest.toString("utf8").split(/\r?\n/u).filter(Boolean)) {
    const match = /^([a-f0-9]{64})  (.+)$/u.exec(line);
    if (!match) throw new Error("The catalog manifest contains an invalid entry.");
    const [, expected, relative] = match;
    const absolute = path.resolve(catalogRoot, relative);
    const normalized = path.relative(catalogRoot, absolute).replaceAll("\\", "/");
    if (normalized !== relative || normalized.startsWith("../") || path.isAbsolute(normalized) || entries.has(relative)) {
      throw new Error(`Invalid catalog path: ${relative}`);
    }
    if (digest(fs.readFileSync(absolute)) !== expected) throw new Error(`Catalog content differs from its manifest: ${relative}`);
    entries.add(relative);
  }
  const actual = filesWithin(catalogRoot).filter((name) => !["MANIFEST.sha256", "catalog-pin.json"].includes(name));
  if (actual.length !== entries.size || actual.some((name) => !entries.has(name))) {
    throw new Error("The catalog file inventory differs from its manifest. Review and seal the catalog before packaging.");
  }
  return [...entries].map((name) => `contracts/${name}`).concat("contracts/MANIFEST.sha256", "contracts/catalog-pin.json");
}

export function verifyPackageContents(paths, catalogPaths, { requireReleaseManifest = true } = {}) {
  const names = new Set(paths);
  const exact = new Set([
    "package.json", "README.md", "LICENSE", "pyproject.toml", "bin/model-forge-codex.mjs", "npm-release-manifest.json",
    "docs/model-access.md", "docs/development.md", "docs/installation.md",
    "scripts/npm_launcher.py", "scripts/npm_snapshot.py", "scripts/validate_local_install.py", "web/package.json",
    "web/scripts/validate-math.mjs", "web/scripts/math-checker.mjs", "web/scripts/shared-deps.mjs", "web/src/researchMath.js",
    "web/runtime/validate-math.mjs", "web/runtime/export-report.mjs", "web/runtime/KATEX-LICENSE.txt", "web/runtime/NOTICE.txt",
    "web/runtime/REACT-LICENSE.txt", "web/runtime/REACT-DOM-LICENSE.txt",
    "web/dist/FONT-NOTICE.txt", "web/dist/IBM-PLEX-SANS-LICENSE.txt", "web/dist/IBM-PLEX-MONO-LICENSE.txt", "web/dist/MARCELLUS-LICENSE.txt",
    ...catalogPaths,
  ]);
  for (const name of names) {
    const clean = !name.split("/").some((part) => part === ".." || part === "node_modules" || part === "__pycache__" || part.startsWith(".env"));
    const allowed = exact.has(name) || /^src\/model_forge_codex\/(?:[\w-]+\/)*[\w-]+\.py$/u.test(name)
      || /^web\/dist\/(?:assets\/[\w.-]+\.(?:js|css|woff2?|ttf)|index\.html)$/u.test(name)
      || /^web\/dist\/assets\/worn-silver-plates-[\w-]+\.svg$/u.test(name);
    if (!clean || !allowed) throw new Error(`Unexpected file in the npm package: ${name}`);
  }
  for (const required of [...exact, "src/model_forge_codex/local_app.py", "web/dist/index.html", "web/runtime/validate-math.mjs"]) {
    if (required === "npm-release-manifest.json" && !requireReleaseManifest) continue;
    if (!names.has(required)) throw new Error(`Required npm release file is missing: ${required}`);
  }
  if (!paths.some((name) => /^web\/dist\/assets\/.*\.js$/u.test(name)) || !paths.some((name) => /^web\/dist\/assets\/.*\.css$/u.test(name))) {
    throw new Error("The npm release is missing the built interface assets.");
  }
}

export function createReleaseManifest(root, paths) {
  const metadata = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8"));
  const files = {};
  for (const name of paths.filter((name) => name !== "npm-release-manifest.json").sort()) {
    const absolute = path.join(root, name);
    if (!fs.lstatSync(absolute).isFile()) throw new Error(`Release content must be an ordinary file: ${name}`);
    files[name] = digest(fs.readFileSync(absolute));
  }
  // The launcher computes this same identity before copying to a stable app directory.
  // Excluding the manifest itself avoids a self-referential content hash.
  const identity = { package: metadata.name, version: metadata.version, files };
  return { schema_version: 1, package: metadata.name, version: metadata.version,
    release_id: `npm-${metadata.version}-${digest(JSON.stringify(identity)).slice(0, 16)}`, files };
}

export function npmCliPath() {
  const candidates = [process.env.npm_execpath,
    path.join(path.dirname(process.execPath), "node_modules/npm/bin/npm-cli.js"),
    path.resolve(path.dirname(process.execPath), "../lib/node_modules/npm/bin/npm-cli.js"),
  ];
  const found = candidates.find((candidate) => candidate && fs.existsSync(candidate));
  if (!found) throw new Error("npm was not found beside the shared Node.js installation. Run this check through npm pack or npm run test:npm.");
  return found;
}

export function inspectPack(root = appRoot) {
  const result = spawnSync(process.execPath, [npmCliPath(), "pack", "--dry-run", "--ignore-scripts", "--json"], {
    cwd: root, encoding: "utf8", windowsHide: true,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(result.stderr || result.stdout || "npm could not inspect the package.");
  return JSON.parse(result.stdout)[0].files.map((entry) => entry.path);
}

export function preparePackage(root = appRoot) {
  const catalogPaths = verifyCatalog(root);
  const build = spawnSync(process.execPath, [path.join(root, "web/scripts/vite.mjs"), "build"], {
    cwd: root, stdio: "inherit", windowsHide: true,
  });
  if (build.error) throw build.error;
  if (build.status !== 0) throw new Error("The UI and mathematics bundle could not be built. Install the declared frontend dependencies in a shared npm location.");
  // npm's own file inventory is the final authority on what will leave this machine.
  const packedPaths = inspectPack(root);
  verifyPackageContents(packedPaths, catalogPaths, { requireReleaseManifest: false });
  const manifest = createReleaseManifest(root, packedPaths);
  fs.writeFileSync(path.join(root, "npm-release-manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
  verifyPackageContents(inspectPack(root), catalogPaths);
  console.log("npm release verified: current UI, bundled mathematics, and intact workflow catalog; no research records or development caches.");
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { preparePackage(); }
  catch (error) { console.error(`Cannot prepare npm release: ${error.message}`); process.exitCode = 1; }
}
