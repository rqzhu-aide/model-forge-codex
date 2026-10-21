import fs from "node:fs";
import { isBareMathDefinition, validateMathText } from "../src/researchMath.js";

export function checkStdin(katex) {
  const items = JSON.parse(fs.readFileSync(0, "utf8"));
  process.stdout.write(JSON.stringify(items.map(({ text, raw }) =>
    validateMathText(katex, text, raw === "named-definition" ? isBareMathDefinition(text) : raw === true))));
}
