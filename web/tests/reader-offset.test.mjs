import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-reader-offset-"));
const bundle = path.join(directory, "offset.cjs");
await build({ entryPoints: [fileURLToPath(new URL("../src/useReaderOffset.js", import.meta.url))], outfile: bundle, bundle: true, platform: "node", format: "cjs", alias: { react: sharedPackage("react") }, logLevel: "silent" });
const { observeReaderOffset } = require(bundle);
fs.unlinkSync(bundle); fs.rmdirSync(directory);

test("anchor offset follows actual header size without moving reading position or focus", () => {
  const previous = { window: globalThis.window, ResizeObserver: globalThis.ResizeObserver, getComputedStyle: globalThis.getComputedStyle };
  let height = 199.1; let inset = "0px"; let resize; let observed; let disconnected = false;
  const values = new Map(); const writes = [];
  const toolbar = { getBoundingClientRect: () => ({ height }) };
  const root = { querySelector: () => toolbar, style: { getPropertyValue: key => values.get(key), setProperty: (key, value) => { values.set(key, value); writes.push(value); } } };
  const listeners = new Map();
  globalThis.window = { addEventListener: (name, fn) => listeners.set(name, fn), removeEventListener: (name, fn) => { assert.equal(listeners.get(name), fn); listeners.delete(name); }, scrollTo: () => assert.fail("Offset measurement must not scroll") };
  globalThis.getComputedStyle = () => ({ top: inset });
  globalThis.ResizeObserver = class { constructor(fn) { resize = fn; } observe(node) { observed = node; } disconnect() { disconnected = true; } };
  try {
    const dispose = observeReaderOffset(root);
    assert.equal(observed, toolbar); assert.equal(values.get("--reader-scroll-offset"), "212px");
    resize(); assert.equal(writes.length, 1, "An unchanged header must not rewrite the style");
    height = 131; inset = "8px"; resize(); assert.equal(values.get("--reader-scroll-offset"), "151px");
    height = 180; listeners.get("resize")(); assert.equal(values.get("--reader-scroll-offset"), "200px");
    dispose(); assert.ok(disconnected); assert.equal(listeners.size, 0);
    assert.equal(observeReaderOffset(null), undefined, "Loading has no toolbar to observe");
  } finally { for (const [key, value] of Object.entries(previous)) { if (value === undefined) delete globalThis[key]; else globalThis[key] = value; } }
});
