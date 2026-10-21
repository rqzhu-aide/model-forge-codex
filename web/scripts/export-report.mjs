// Development entry point. Installed releases use the bundled runtime.
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { sharedPackage } from "./shared-deps.mjs";
import { renderReport } from "./report-renderer.mjs";
import { reportAssetInput } from "./report-assets.mjs";

const katex = (await import(pathToFileURL(sharedPackage("katex", "dist/katex.mjs")).href)).default;
const cssFile = sharedPackage("katex", "dist/katex.min.css");
const css = fs.readFileSync(cssFile, "utf8").replace(/url\(([^)]+)\)/g, (_, source) => {
  const name = source.replace(/^['"]|['"]$/g, "");
  const file = path.resolve(path.dirname(cssFile), name);
  const extension = path.extname(file).slice(1);
  return `url(data:font/${extension};base64,${fs.readFileSync(file).toString("base64")})`;
});
process.stdout.write(JSON.stringify(renderReport(katex, css, reportAssetInput(JSON.parse(fs.readFileSync(0, "utf8"))))));
