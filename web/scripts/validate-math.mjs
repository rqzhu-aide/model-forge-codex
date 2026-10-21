import { createRequire } from "node:module";
import { sharedPackage } from "./shared-deps.mjs";
import { checkStdin } from "./math-checker.mjs";

const require = createRequire(import.meta.url);
const katex = require(sharedPackage("katex"));
checkStdin(katex);
