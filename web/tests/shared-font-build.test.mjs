import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import test from "node:test";
import makeConfig from "../vite.config.js";
import { buildFontNotices } from "../scripts/build-font-notices.mjs";
import { sharedPackage } from "../scripts/shared-deps.mjs";

test("all imported font stylesheets and their assets resolve through allowed shared paths", async () => {
  const config = await makeConfig();
  const main = await fs.readFile(new URL("../src/main.jsx", import.meta.url), "utf8");
  const imports = [...main.matchAll(/import "(@fontsource[^\"]+)"/g)].map((match) => match[1]);
  assert.equal(imports.length, 5);
  for (const specifier of imports) {
    const alias = config.resolve.alias.find(({ find }) => find.test(specifier));
    assert.ok(alias, `Shared alias missing for ${specifier}`);
    const cssPath = specifier.replace(alias.find, alias.replacement);
    assert.equal(alias.replacement, sharedPackage(specifier.split("/").slice(0, 2).join("/")));
    assert.ok(config.server.fs.allow.includes(alias.replacement), `Shared files are not allowed for ${specifier}`);
    const css = await fs.readFile(cssPath, "utf8");
    const assets = [...css.matchAll(/url\(([^)]+)\)/g)].map((match) => match[1].replace(/^['"]|['"]$/g, ""));
    assert.ok(assets.length, `Font assets missing from ${specifier}`);
    for (const asset of assets) await fs.access(path.resolve(path.dirname(cssPath), asset));
  }
});

test("a shared installation without the three fonts gives an actionable failure", async () => {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), "model-forge-shared-font-check-"));
  try {
    // Only discovery fixtures are written, not installed or executable packages.
    for (const name of ["react", "react-dom", "katex", "vite", "@vitejs/plugin-react"]) {
      await fs.mkdir(path.join(directory, name), { recursive: true });
      await fs.writeFile(path.join(directory, name, "package.json"), JSON.stringify({ name }));
    }
    const result = spawnSync(process.execPath, [fileURLToPath(new URL("../scripts/shared-deps.mjs", import.meta.url))], {
      encoding: "utf8", env: { ...process.env, MF_SHARED_NODE_MODULES: directory }, windowsHide: true,
    });
    assert.notEqual(result.status, 0);
    for (const name of ["@fontsource-variable/ibm-plex-sans", "@fontsource/ibm-plex-mono", "@fontsource/marcellus"]) {
      assert.ok(result.stderr.includes(name), result.stderr);
    }
    assert.match(result.stderr, /user-wide or machine-wide/);
  } finally {
    assert.equal(path.dirname(path.resolve(directory)), path.resolve(os.tmpdir()));
    await fs.rm(directory, { recursive: true, force: true });
  }
});

test("the built interface retains each font's original license and version notice", async () => {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), "model-forge-font-notices-"));
  try {
    await buildFontNotices(directory);
    const notice = await fs.readFile(path.join(directory, "FONT-NOTICE.txt"), "utf8");
    for (const [name, license] of [
      ["@fontsource-variable/ibm-plex-sans", "IBM-PLEX-SANS-LICENSE.txt"],
      ["@fontsource/ibm-plex-mono", "IBM-PLEX-MONO-LICENSE.txt"],
      ["@fontsource/marcellus", "MARCELLUS-LICENSE.txt"],
    ]) {
      assert.equal(await fs.readFile(path.join(directory, license), "utf8"), await fs.readFile(sharedPackage(name, "LICENSE"), "utf8"));
      const metadata = JSON.parse(await fs.readFile(sharedPackage(name, "package.json"), "utf8"));
      assert.ok(notice.includes(`${name} ${metadata.version}`));
      assert.ok(notice.includes(license));
    }
  } finally {
    assert.equal(path.dirname(path.resolve(directory)), path.resolve(os.tmpdir()));
    await fs.rm(directory, { recursive: true, force: true });
  }
});
