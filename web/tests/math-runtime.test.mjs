import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { buildMathRuntime } from "../scripts/build-math-runtime.mjs";

test("the distributed math checker runs independently of source files and shared npm packages", async () => {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), "model-forge-math-runtime-"));
  try {
    await buildMathRuntime(directory);
    const items = [
      { text: String.raw`x=\frac{1}{2}`, raw: true },
      { text: String.raw`Bound $\unknownMacro{x}$.`, raw: false },
      { text: String.raw`$$\begin{aligned}x&=1\\y&=2\end{aligned}$$`, raw: false },
      { text: String.raw`$\\Pr(H>B)\\le1-\\tau$`, raw: false },
      { text: String.raw`x=\unknownMacro{Y}`, raw: "named-definition" },
      { text: String.raw`The value x=\unknownMacro{Y} is prose.`, raw: "named-definition" },
      { text: "$\n\\unknownAssociationMacro{x}\n$", raw: false },
      { text: "$\n\\begin{aligned}x&=1\\\\y&=2\\end{aligned}\n$", raw: false },
    ];
    const input = JSON.stringify(items);
    const source = spawnSync(process.execPath, [fileURLToPath(new URL("../scripts/validate-math.mjs", import.meta.url))],
      { encoding: "utf8", input });
    assert.equal(source.status, 0, source.stderr);
    const bundled = spawnSync(process.execPath, [path.join(directory, "validate-math.mjs")], {
      cwd: directory, encoding: "utf8", input,
      env: { ...process.env, MF_SHARED_NODE_MODULES: path.join(directory, "no-packages"), NODE_PATH: "" },
    });
    assert.equal(bundled.status, 0, bundled.stderr);
    assert.deepEqual(JSON.parse(bundled.stdout), JSON.parse(source.stdout));
    const reports = JSON.parse(bundled.stdout);
    assert.equal(reports[1][0].code, "math.invalid_latex");
    assert.equal(reports[3][0].code, "math.overescaped_latex");
    assert.deepEqual(reports[5], []);
    assert.equal(reports[6][0].code, "math.invalid_latex");
    assert.deepEqual(reports[7], []);
    assert.match(await fs.readFile(path.join(directory, "KATEX-LICENSE.txt"), "utf8"), /Permission is hereby granted/);
    assert.match(await fs.readFile(path.join(directory, "REACT-LICENSE.txt"), "utf8"), /Permission is hereby granted/);
    assert.match(await fs.readFile(path.join(directory, "REACT-DOM-LICENSE.txt"), "utf8"), /Permission is hereby granted/);
    assert.match(await fs.readFile(path.join(directory, "NOTICE.txt"), "utf8"), /KaTeX \d+\.\d+/);
  } finally {
    // mkdtemp created this directory directly under the system temporary root.
    assert.equal(path.dirname(path.resolve(directory)), path.resolve(os.tmpdir()));
    await fs.rm(directory, { recursive: true, force: true });
  }
});
