import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { createRequire } from "node:module";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { inlineTokens, mathBody, isBareMathDefinition, mathSegments, legacyMathCandidate, validateMathText, renderMath } from "../src/researchMath.js";

const katex = createRequire(import.meta.url)(sharedPackage("katex"));
const associationFixture = JSON.parse(fs.readFileSync(new URL("./fixtures/p3-linked-association-equations.json", import.meta.url), "utf8"));

test("standalone-dollar equation fixtures share exact tokens and bodies between rendering and checking", () => {
  assert.equal(associationFixture.fixture_kind, "Standalone equation-rendering regression");
  assert.equal(associationFixture.blocks.length, 3);
  for (const { token, latex } of associationFixture.blocks) {
    const original = token; const text = `Before.\n${token}\nAfter.`;
    assert.deepEqual(mathSegments(text), [{ latex, display: true, offset: 8 }]);
    assert.deepEqual(text.split(inlineTokens), ["Before.\n", token, "\nAfter."], "String.split retains one outer token capture.");
    assert.deepEqual(mathBody(token), { latex, display: true });
    assert.deepEqual(validateMathText(katex, text), []);
    assert.match(renderMath(katex, latex, true), /class="katex-display"/);
    assert.equal(token, original, "No stored equation text is rewritten.");
  }
  const invalid = "$\n\\unknownAssociationMacro{x}\n$";
  const finding = validateMathText(katex, `Before.\n${invalid}`)[0];
  assert.equal(finding.code, "math.invalid_latex"); assert.equal(finding.offset, 8);
});

test("standalone-dollar support preserves CRLF, escaping and existing display delimiter precedence", () => {
  const token = "  $ \r\nx=1+\\$2\r\n  $ ";
  assert.deepEqual(mathSegments(token), [{ latex: " \r\nx=1+\\$2\r\n  ", display: true, offset: 0 }]);
  assert.deepEqual(validateMathText(katex, token), []);
  const continued = "$\nx=1\\\ny=2\n$";
  assert.deepEqual(mathSegments(continued), [{ latex: "\nx=1\\\ny=2\n", display: true, offset: 0 }]);
  assert.deepEqual(validateMathText(katex, continued), []);
  const text = "$$\nx=1\n$$\n\\[\ny=2\n\\]\n$\nz=3\n$";
  assert.deepEqual(mathSegments(text).map(({ display, latex }) => ({ display, latex })), [
    { display: true, latex: "\nx=1\n" }, { display: true, latex: "\ny=2\n" }, { display: true, latex: "\nz=3\n" },
  ]);
  assert.deepEqual(validateMathText(katex, text), []);
});

test("an explicitly bounded block sends invalid inner dollars to KaTeX instead of checking an unrelated inline fragment", () => {
  const token = "$\n x+$y$\n$";
  const text = `Before.\n${token}\nAfter.`;
  assert.deepEqual(mathSegments(text), [{ latex: "\n x+$y$\n", display: true, offset: 8 }]);
  assert.deepEqual(text.split(inlineTokens), ["Before.\n", token, "\nAfter."]);
  const findings = validateMathText(katex, text);
  assert.equal(findings.length, 1);
  assert.equal(findings[0].code, "math.invalid_latex");
  assert.equal(findings[0].offset, 8);
  assert.match(renderMath(katex, mathBody(token).latex, true), /katex-error/);
});

test("standalone-dollar support does not pair currency, inline text or opaque code across lines", () => {
  for (const text of ["Price $5\nNext price $10.", "Cost $5\n\nAnother budget $20.", "Text $\nx=1\n$ end", "\\$\nx=1\n\\$", "`$\n\\badMacro\n$`", "```tex\n$\n\\badMacro\n$\n```", "~~~tex\n$\n\\badMacro\n$\n~~~", "https://example.test/$\nx=1\nend", "`opaque` $\nx=1\nend"]) {
    assert.deepEqual(mathSegments(text), [], text);
    assert.deepEqual(validateMathText(katex, text), [], text);
  }
  for (const text of ["The price is $5 and the budget is $10.", "`opaque` then $x$.", "https://example.test/path then $x$."]) {
    assert.deepEqual(validateMathText(katex, text), []);
    assert.ok(mathSegments(text).every(({ display }) => display === false));
  }
});

test("explicit standalone-dollar blocks reject unclosed and mismatched display delimiters", () => {
  for (const text of ["$\nx=1", "$\nx=1\n$$", "$\nx=1\n\\]", "$$\nx=1\n$", "\\[\nx=1\n$", "$\nx=1\n```tex\n$\n```", "$\nx=1\n~~~tex\n$\n~~~"]) {
    assert.ok(validateMathText(katex, text).some(({ code }) => code === "math.invalid_delimiter"), text);
  }
});

test("the UI and checker distinguish display equations, inline symbols, code and URLs", () => {
  const text = [String.raw`Use $\tau$ with $$\Pr(H>B)\le1-\tau$$ and \[G=\sum_t\gamma^tR_t\].`,
    String.raw`Keep \(B\) inline and code \`$\notACommand$\` literal.`,
    "```tex\n$\\badMacro$\n```", "https://example.org/$invalidMacro$"].join("\n");
  const parts = mathSegments(text);
  assert.deepEqual(parts.map(({ display }) => display), [false, true, true, false]);
  assert.deepEqual(validateMathText(katex, text), []);
  assert.deepEqual(mathSegments("There is no equation in this prose or code URL https://example.org/a"), []);
});

test("unknown commands and incomplete groups are rejected at their exact equation offset", () => {
  const text = String.raw`A symbol $x$ and invalid $\notACommand{x}$ followed by $$\frac{1}{$$.`;
  const findings = validateMathText(katex, text);
  assert.equal(findings.length, 2);
  assert.deepEqual(findings.map(({ code }) => code), ["math.invalid_latex", "math.invalid_latex"]);
  assert.equal(findings[0].offset, text.indexOf("$\\notACommand"));
  assert.equal(findings[1].offset, text.indexOf("$$"));
  assert.match(findings[0].message, /Undefined control sequence/);
});

test("uniformly doubled JSON commands are reported even when KaTeX accepts them as line breaks", () => {
  const latex = String.raw`\\Pr(H_\\gamma^\\pi>B)\\le1-\\tau`;
  const silentlyAccepted = String.raw`\\Pr(H>B)\\le1-\\tau`;
  assert.doesNotThrow(() => katex.renderToString(silentlyAccepted, { throwOnError: true }));
  assert.equal(validateMathText(katex, `$${silentlyAccepted}$`)[0].code, "math.overescaped_latex");
  assert.equal(validateMathText(katex, `$${latex}$`)[0].code, "math.overescaped_latex");
  assert.equal(legacyMathCandidate(katex, latex), String.raw`\Pr(H_\gamma^\pi>B)\le1-\tau`);
  const rendered = renderMath(katex, latex, false);
  assert.match(rendered, /<annotation[^>]*>\\Pr\(H_/);
  assert.doesNotMatch(rendered, /katex-error/);
  assert.equal(legacyMathCandidate(katex, String.raw`\\frac{1}{2}`), String.raw`\frac{1}{2}`);
});

test("valid aligned and matrix rows, including adjacent Greek commands, are preserved exactly", () => {
  for (const latex of [String.raw`\begin{aligned}x&=1\\\theta&=2\end{aligned}`,
    String.raw`\begin{matrix}\alpha&1\\\theta&2\end{matrix}`,
    String.raw`\Pr(H>B)\le1-\tau`, String.raw`x=1\\next`, String.raw`x=1\\y=2`]) {
    assert.equal(legacyMathCandidate(katex, latex), null);
    assert.deepEqual(validateMathText(katex, latex, true), []);
    assert.doesNotMatch(renderMath(katex, latex, true), /katex-error/);
  }
});

test("recovery never rewrites mixed escaping or an unrecognized command", () => {
  assert.equal(legacyMathCandidate(katex, String.raw`\Pr(H)>\\tau`), null);
  assert.equal(legacyMathCandidate(katex, String.raw`\\notACommand{x}`), null);
});

test("raw latex fields and Markdown use the same KaTeX check", () => {
  assert.equal(validateMathText(katex, String.raw`\badMacro`, true)[0].code, "math.invalid_latex");
  assert.deepEqual(validateMathText(katex, String.raw`\badMacro`, false), []);
  assert.match(renderMath(katex, "x=1", true), /katex-display/);
  assert.doesNotMatch(renderMath(katex, "x", false), /katex-display/);
});

test("known bare definitions use the same recovery boundary for rendering and validation", () => {
  for (const text of [String.raw`\theta = E[Y]`, String.raw`x=\unknownCommand{y}`, String.raw`x=\frac{1}{`]) {
    assert.equal(isBareMathDefinition(text), true);
  }
  for (const text of [String.raw`Expected value \theta = E[Y].`, String.raw`x = 1 is required.`,
    String.raw`$x=\unknownCommand$`, String.raw`\[x=\unknownCommand\]`, "`x=\\unknownCommand`", "https://example.org/?x=1"]) {
    assert.equal(isBareMathDefinition(text), false, text);
  }
  assert.deepEqual(validateMathText(katex, String.raw`\theta = E[Y]`, isBareMathDefinition(String.raw`\theta = E[Y]`)), []);
  assert.equal(validateMathText(katex, String.raw`x=\unknownCommand{y}`, isBareMathDefinition(String.raw`x=\unknownCommand{y}`))[0].code, "math.invalid_latex");
});

test("unfinished and mismatched explicit display delimiters fail without treating prices as math", () => {
  for (const text of [String.raw`Choose $$q_\tau(H)\le B`, String.raw`Choose \[q_\tau(H)\le B`,
    String.raw`Choose \[q_\tau(H)\le B$$`, String.raw`Choose $$q_\tau(H)\le B\]`, String.raw`q_\tau(H)\le B\]`]) {
    assert.ok(validateMathText(katex, text).some(({ code }) => code === "math.invalid_delimiter"));
  }
  for (const text of ["The price is $5 and the remaining budget is $10.", "Code `$$x` stays literal.",
    "```tex\n$$x\n```", "```tex\n$$x", "https://example.org/$$unfinished", String.raw`Escape \$\$ as literal dollars.`]) {
    assert.deepEqual(validateMathText(katex, text), []);
  }
  assert.equal(validateMathText(katex, "Target $$x")[0].offset, 7);
});
