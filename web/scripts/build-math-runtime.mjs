import path from "node:path";
import fs from "node:fs/promises";
import { fileURLToPath, pathToFileURL } from "node:url";
import { sharedPackage } from "./shared-deps.mjs";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

export async function buildMathRuntime(outDir = path.join(webRoot, "runtime")) {
  const vite = await import(pathToFileURL(sharedPackage("vite", "dist/node/index.js")).href);
  await vite.build({
    configFile: false,
    root: webRoot,
    resolve: { alias: { katex: sharedPackage("katex", "dist/katex.mjs") } },
    ssr: { noExternal: true },
    build: {
      ssr: path.join(webRoot, "scripts/math-runtime-entry.mjs"),
      target: "node18",
      outDir,
      emptyOutDir: true,
      minify: false,
      rollupOptions: {
        external: ["node:fs"],
        output: { entryFileNames: "validate-math.mjs" },
      },
    },
  });
  const cssFile = sharedPackage("katex", "dist/katex.min.css");
  let css = await fs.readFile(cssFile, "utf8");
  for (const source of new Set([...css.matchAll(/url\(([^)]+)\)/g)].map((match) => match[1]))) {
    const file = path.resolve(path.dirname(cssFile), source.replace(/^['"]|['"]$/g, ""));
    const bytes = await fs.readFile(file);
    css = css.replaceAll(`url(${source})`, `url(data:font/${path.extname(file).slice(1)};base64,${bytes.toString("base64")})`);
  }
  await vite.build({
    configFile: false,
    root: webRoot,
    plugins: [{
      name: "portable-report-css",
      resolveId(id) { if (id === "virtual:report-katex-css") return "\0report-katex-css"; },
      load(id) { if (id === "\0report-katex-css") return `export default ${JSON.stringify(css)};`; },
    }],
    resolve: { alias: { katex: sharedPackage("katex", "dist/katex.mjs") } },
    ssr: { noExternal: true },
    build: {
      ssr: path.join(webRoot, "scripts/report-runtime-entry.mjs"),
      target: "node18", outDir, emptyOutDir: false, minify: false,
      rollupOptions: { external: ["node:fs", "node:path", "node:crypto"], output: { entryFileNames: "export-report.mjs" } },
    },
  });
  const notices = [];
  for (const [name, license] of [["katex", "KATEX-LICENSE.txt"], ["react", "REACT-LICENSE.txt"], ["react-dom", "REACT-DOM-LICENSE.txt"]]) {
    const metadata = JSON.parse(await fs.readFile(sharedPackage(name, "package.json"), "utf8"));
    await fs.copyFile(sharedPackage(name, "LICENSE"), path.join(outDir, license));
    notices.push(`${name === "katex" ? "KaTeX" : name} ${metadata.version} is distributed under the ${metadata.license} License; see ${license}.`);
  }
  await fs.writeFile(path.join(outDir, "NOTICE.txt"),
    "The built interface, mathematical notation checker and portable report exporter include these dependencies:\n" + notices.join("\n") + "\n");
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  await buildMathRuntime();
}
