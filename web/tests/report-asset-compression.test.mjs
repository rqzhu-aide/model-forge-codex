import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { createHash, randomBytes } from "node:crypto";
import { gunzipSync } from "node:zlib";
import { createRequire } from "node:module";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { reportAssetInput } from "../scripts/report-assets.mjs";
import { renderReport } from "../scripts/report-renderer.mjs";

const katex = createRequire(import.meta.url)(sharedPackage("katex"));
const digest = bytes => createHash("sha256").update(bytes).digest("hex");
const descriptor = (name, bytes, media_type) => ({ path: path.resolve(name), sha256: digest(bytes), media_type,
  artifact_id: `artifact.${name}`, authored_path: name });

test("large compressible text downloads retain exact bytes and hashes through native gzip links", () => {
  const source = Buffer.from('λ,value\r\n0.04133735,"retained scientific evidence"\r\n'.repeat(10_000));
  const table = Buffer.from(JSON.stringify({ values: ["Recorded evidence ".repeat(10_000)] }));
  const files = { "metrics_long.txt": descriptor("metrics_long.txt", source, "text/plain"),
    "values.json": descriptor("values.json", table, "application/json") };
  let reads = 0;
  const prepared = reportAssetInput({ markdown: '# Report\n\n<a id="finding"></a>\nConditional $x=1$. [Metrics](metrics_long.txt) [Same metrics](metrics_long.txt) [Values](values.json#row)',
    shareable_export: true, asset_files: files }, filename => { reads++; return filename === files["metrics_long.txt"].path ? source : table; });
  const output = renderReport(katex, "math-css", prepared);
  assert.equal(reads, 2);
  assert.equal((output.html.match(/download="metrics_long.txt.gz"/g) || []).length, 1);
  assert.equal((output.html.match(/href="#report-evidence-1"/g) || []).length, 2);
  assert.match(output.html, /download="values.json.gz"/);
  assert.match(output.html, /Gzip-compressed source\. Extract it to recover metrics_long.txt\./);
  assert.match(output.html, /class="katex"/);
  assert.match(output.html, /id="finding"/);
  assert.doesNotMatch(output.html.split('<section class="report-supplement')[0], /Gzip-compressed|\.gz/);
  assert.ok(output.html.length < 30_000, "Highly compressible sources must not dominate the HTML export");
  for (const [name, bytes] of [["metrics_long.txt", source], ["values.json", table]]) {
    const link = new RegExp(`href="data:application/gzip;base64,([^"]+)" download="${name.replaceAll(".", "\\.")}.gz"[^>]+`).exec(output.html);
    assert.ok(link);
    const compressed = Buffer.from(link[1], "base64");
    assert.deepEqual(gunzipSync(compressed), bytes);
    const material = output.encoded_materials.find(item => item.artifact_id === files[name].artifact_id);
    assert.equal(material.delivery.decoded_sha256, digest(bytes));
    assert.equal(material.delivery.sha256, digest(compressed));
    assert.equal(material.delivery.decoded_filename, name);
    assert.ok(link[0].includes(`data-export-sha256="${digest(bytes)}"`));
    assert.ok(link[0].includes(`data-download-sha256="${digest(compressed)}"`));
  }
  assert.equal(prepared.assets["metrics_long.txt"], `data:text/plain;base64,${source.toString("base64")}`, "The source representation stays exact");
});

test("small, incompressible, image and hosted downloads preserve their existing plain delivery", () => {
  const small = Buffer.from("Exact small source\r\n");
  const incompressible = randomBytes(256 * 1024);
  const image = Buffer.alloc(256 * 1024, 1);
  const large = Buffer.from("retained source\n".repeat(20_000));
  const inputs = [["small.txt", small, "text/plain"], ["noise.txt", incompressible, "text/plain"],
    ["figure.png", image, "image/png"], ["hosted.txt", large, "text/plain"]];
  const files = Object.fromEntries(inputs.map(([name, bytes, media]) => [name, descriptor(name, bytes, media)]));
  files["hosted.txt"].download_url = "/api/verified-scientific-source";
  const bytes = new Map(inputs.map(([name, value]) => [files[name].path, value]));
  const prepared = reportAssetInput({ shareable_export: true, asset_files: files }, filename => bytes.get(filename));
  for (const [name, value, media] of inputs.slice(0, 3)) {
    assert.deepEqual(prepared.downloadForAsset(name), { url: `data:${media};base64,${value.toString("base64")}`, filename: name });
  }
  assert.deepEqual(prepared.downloadForAsset("hosted.txt"), { url: "/api/verified-scientific-source", filename: "hosted.txt" });
  const historical = reportAssetInput({ asset_files: { "large.txt": descriptor("large.txt", large, "text/plain") } }, () => large);
  assert.equal(historical.downloadForAsset("large.txt").filename, "large.txt", "Compression is confined to shareable scientific exports");
});
