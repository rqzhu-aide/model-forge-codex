import fs from "node:fs";
import katex from "katex";
import css from "virtual:report-katex-css";
import { renderReport } from "./report-renderer.mjs";
import { reportAssetInput } from "./report-assets.mjs";

process.stdout.write(JSON.stringify(renderReport(katex, css, reportAssetInput(JSON.parse(fs.readFileSync(0, "utf8"))))));
