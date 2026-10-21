import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { appRoot, createReleaseManifest, inspectPack, verifyCatalog, verifyPackageContents } from "../scripts/prepare_npm_package.mjs";

test("application versions agree across npm, Python and the interface", () => {
  const read = (name) => fs.readFileSync(path.join(appRoot, name), "utf8");
  const version = JSON.parse(read("package.json")).version;
  assert.equal(JSON.parse(read("web/package.json")).version, version);
  assert.equal(/^version = "([^"]+)"$/mu.exec(read("pyproject.toml"))?.[1], version);
  assert.equal(/^__version__ = "([^"]+)"$/mu.exec(read("src/model_forge_codex/__init__.py"))?.[1], version);
});

test("npm release includes its runtime and complete catalog, and excludes local research", () => {
  const catalogPaths = verifyCatalog(appRoot);
  const packed = inspectPack();
  verifyPackageContents(packed, catalogPaths);
  const manifest = JSON.parse(fs.readFileSync(path.join(appRoot, "npm-release-manifest.json"), "utf8"));
  assert.deepEqual(manifest, createReleaseManifest(appRoot, packed));
  assert.equal(manifest.files["npm-release-manifest.json"], undefined);
  assert.deepEqual(Object.keys(manifest.files).sort(), packed.filter((name) => name !== "npm-release-manifest.json").sort());
  for (const unexpected of [".env", "config/providers.toml", "src/model_forge_codex/__pycache__/api.pyc", "architecture/evidence/screenshot.png", "web/runtime/.env"]) {
    assert.throws(() => verifyPackageContents([...packed, unexpected], catalogPaths), /Unexpected file/u);
  }
  assert.throws(() => verifyPackageContents(packed.filter((name) => name !== "web/runtime/validate-math.mjs"), catalogPaths), /Required npm release file/u);
  assert.throws(() => verifyPackageContents(packed.filter((name) => name !== "web/runtime/export-report.mjs"), catalogPaths), /Required npm release file/u);
  for (const guide of ["docs/model-access.md", "docs/development.md"]) {
    assert.ok(packed.includes(guide));
    assert.throws(() => verifyPackageContents(packed.filter((name) => name !== guide), catalogPaths), /Required npm release file/u);
  }
});

test("snapshot identity follows application content and ignores manifest serialization", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-package-check-"));
  try {
    fs.writeFileSync(path.join(root, "package.json"), JSON.stringify({ name: "@rqzhu-aide/model-forge-codex", version: "0.1.0" }));
    fs.writeFileSync(path.join(root, "app.py"), "print('first')\n");
    fs.writeFileSync(path.join(root, "npm-release-manifest.json"), "old manifest\n");
    const paths = ["app.py", "package.json", "npm-release-manifest.json"];
    const first = createReleaseManifest(root, paths);
    assert.deepEqual(first, createReleaseManifest(root, [...paths].reverse()));
    fs.writeFileSync(path.join(root, "npm-release-manifest.json"), "different serialization\n");
    assert.deepEqual(first, createReleaseManifest(root, paths));
    fs.writeFileSync(path.join(root, "app.py"), "print('second')\n");
    assert.notEqual(first.release_id, createReleaseManifest(root, paths).release_id);
  } finally {
    assert.equal(path.dirname(path.resolve(root)), path.resolve(os.tmpdir()));
    assert.ok(path.basename(root).startsWith("model-forge-package-check-"));
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("packaging refuses a modified or incomplete scientific catalog without resealing it", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-package-check-"));
  try {
    const catalog = path.join(root, "contracts");
    fs.mkdirSync(catalog);
    const contents = "reviewed instructions\n";
    const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
    const manifest = `${sha(contents)}  instructions.md\n`;
    fs.writeFileSync(path.join(catalog, "instructions.md"), contents);
    fs.writeFileSync(path.join(catalog, "MANIFEST.sha256"), manifest);
    fs.writeFileSync(path.join(catalog, "catalog-pin.json"), JSON.stringify({ catalog_manifest_sha256: sha(manifest) }));
    assert.equal(verifyCatalog(root).length, 3);
    fs.writeFileSync(path.join(catalog, "instructions.md"), "unreviewed changes\n");
    assert.throws(() => verifyCatalog(root), /differs from its manifest/u);
    fs.writeFileSync(path.join(catalog, "instructions.md"), contents);
    fs.writeFileSync(path.join(catalog, "extra.json"), "{}");
    assert.throws(() => verifyCatalog(root), /file inventory differs/u);
  } finally {
    assert.equal(path.dirname(path.resolve(root)), path.resolve(os.tmpdir()));
    assert.ok(path.basename(root).startsWith("model-forge-package-check-"));
    fs.rmSync(root, { recursive: true, force: true });
  }
});
