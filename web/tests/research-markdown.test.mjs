import test from "node:test";
import assert from "node:assert/strict";
import { referenceMarkdown, researchBlocks, tableCells } from "../src/researchMarkdown.js";

test("scientific Markdown preserves ordered steps, nested evidence and heading depth", () => {
  const blocks = researchBlocks("# Method\n## Procedure\n3. Initialize $x_0$.\n   - Use the supplied seed.\n   - Record $n$.\n4. Iterate.\n\n### Limits\nKeep the stated regime.");
  assert.deepEqual(blocks.filter(x => x.kind === "heading").map(x => x.level), [1, 2, 3]);
  const steps = blocks.find(x => x.kind === "list");
  assert.equal(steps.ordered, true);
  assert.deepEqual(steps.items.map(x => x.value), [3, 4]);
  assert.equal(steps.items[0].blocks[1].items.length, 2);
  assert.equal(steps.items[0].blocks[0].text, "Initialize $x_0$.");
});

test("display mathematics stays intact across blank lines and Markdown-looking content", () => {
  const text = "The update is\n\\[\n\\begin{aligned}\n\n x &= y \\\\\n1. & z\n\\end{aligned}\n\\]\nunder the recorded assumption.";
  assert.deepEqual(researchBlocks(text), [{ kind: "paragraph", text }]);
});

test("standalone-dollar blocks stay intact in paragraphs, list items and quoted scientific accounts", () => {
  const equation = "$\n\\begin{aligned}\n\nx&=1\\\\\n1. & y=2\n\\end{aligned}\n$";
  assert.deepEqual(researchBlocks(`Before.\n${equation}\nAfter.`), [{ kind: "paragraph", text: `Before.\n${equation}\nAfter.` }]);
  assert.deepEqual(researchBlocks(`Before.\r\n${equation.replaceAll("\n", "\r\n")}\r\nAfter.`), [{ kind: "paragraph", text: `Before.\n${equation}\nAfter.` }]);
  const listed = researchBlocks(`1. A stated formula\n   ${equation.replaceAll("\n", "\n   ")}\n2. A separate step.`);
  assert.equal(listed[0].items.length, 2);
  assert.equal(listed[0].items[0].blocks[0].text, `A stated formula\n${equation}`);
  const quoted = researchBlocks(`> ${equation.replaceAll("\n", "\n> ")}`);
  assert.deepEqual(quoted, [{ kind: "quote", blocks: [{ kind: "paragraph", text: equation }] }]);
  const fenced = researchBlocks("$\nx=1\n```tex\n$\n```\nAfter.");
  assert.equal(fenced[1].kind, "code"); assert.equal(fenced[1].text, "$");
});

test("pipes in scientific table math, code, links and escapes do not split cells", () => {
  const row = "| $P(A|B)$ | `x|y` | a\\|b | [Source](https://example.test/a|b) |";
  assert.deepEqual(tableCells(row), ["$P(A|B)$", "`x|y`", "a|b", "[Source](https://example.test/a|b)"]);
  const table = researchBlocks("| Quantity | Value |\n| :--- | ---: |\n| $x$ | 0.000001 |\n\nAfter.");
  assert.equal(table[0].kind, "table");
  assert.deepEqual(table[0].rows, [["$x$", "0.000001"]]);
  assert.equal(table[1].text, "After.");
});

test("code and authored HTML stay literal and are never treated as document markup", () => {
  assert.deepEqual(researchBlocks("```tex\n# Literal heading\n$x$\n```\n<script>alert(1)</script>"), [
    { kind: "code", text: "# Literal heading\n$x$" },
    { kind: "paragraph", text: "<script>alert(1)</script>" },
  ]);
});

test("root indented code is opaque and may be followed directly by an authored heading anchor", () => {
  const text = '    <a id="fake"></a>\n    ## Example heading\n\n\t$x=1$\n<a id="actual"></a>\n## Actual heading';
  assert.deepEqual(researchBlocks(text), [
    { kind: "code", text: '<a id="fake"></a>\n## Example heading\n\n$x=1$' },
    { kind: "paragraph", text: '<a id="actual"></a>' },
    { kind: "heading", level: 2, text: "Actual heading" },
  ]);
});

test("indentation does not interrupt a continuing prose paragraph or its mathematics", () => {
  const prose = 'An authored paragraph continues.\n    This remains prose with $x=1$.\n\tA tab remains a continuation too.';
  assert.deepEqual(researchBlocks(prose), [{ kind: "paragraph", text: prose }]);
  const math = "The stated equation is\n$$\n    x=1\n$$";
  assert.deepEqual(researchBlocks(math), [{ kind: "paragraph", text: math }]);
});

test("reference labels resolve document-wide with first-definition, case and whitespace semantics", () => {
  const markdown = "[Recorded concern][ Logging  Input ] and **[logging input][]**; [logging input]. [Missing][undefined].\n\n[logging input]: <C:/Model Forge/exact.json>\n[LOGGING INPUT]: https://example.test/wrong\n";
  const resolved = referenceMarkdown(markdown);
  assert.match(resolved, /\[Recorded concern\]\(<C:\/Model Forge\/exact.json>\)/);
  assert.match(resolved, /\*\*\[logging input\]\(<C:\/Model Forge\/exact.json>\)\*\*/);
  assert.match(resolved, /; \[logging input\]\(<C:\/Model Forge\/exact.json>\)\./);
  assert.match(resolved, /\[Missing\]\[undefined\]/);
  assert.doesNotMatch(resolved, /\]:|example.test\/wrong/);
  assert.equal(referenceMarkdown(markdown.replaceAll("\n", "\r\n")).replaceAll("\r\n", "\n"), resolved);
});

test("reference resolution preserves code, mathematics, escaped uses and existing links", () => {
  const opaque = "```md\n[code][ref]\n[ref]: https://example.test/code\n```\n\n    [ref]: https://example.test/indented\n\n`[inline][ref]` and ``[double][ref]``.\n\n$$\n[math][ref]\n[ref]: x\n$$\n\n$[inline][ref]$ and \\( [other][ref] \\).\n\\[escaped][ref] and [Existing](https://example.test/ref).";
  const markdown = `${opaque}\n\n[Visible][ref].\n\n[ref]: https://example.test/actual`;
  const resolved = referenceMarkdown(markdown);
  assert.equal(resolved.slice(0, opaque.length), opaque);
  assert.match(resolved, /\[Visible\]\(<https:\/\/example.test\/actual>\)/);
});

test("quoted fenced code preserves reference bytes across longer closes and quote boundaries", () => {
  const cases = [
    "> ```md\n> [literal][ref]\n> ````",
    "> ```md\n> [literal][ref]",
    "> > ~~~md\n> > [literal][ref]\n> > ~~~~",
    "> > ```md\n> > [literal][ref]\n> Outside [Visible][ref].",
    "> ```md\n> > ```\n> [literal][ref]\n> ````",
    ">     [literal][ref]",
    "- > ```md\n  > [literal][ref]\n  > ````",
    "- ```md\n  [literal][ref]\n  ````",
    "> - > ```md\n>   > [literal][ref]\n>   > ````",
    "- > ```md\n  > [literal][ref]",
    "- Intro\n  > ```md\n  > [literal][ref]\n> Outside [Visible][ref].",
  ];
  const codeBodies = (blocks) => blocks.flatMap(block => block.kind === "code" ? [block.text]
    : block.kind === "quote" ? codeBodies(block.blocks)
      : block.kind === "list" ? block.items.flatMap(item => codeBodies(item.blocks)) : []);
  for (const quoted of cases) {
    const markdown = `${quoted}\n\n[Visible][ref].\n\n[ref]: https://example.test/exact`;
    const resolved = referenceMarkdown(markdown);
    assert.deepEqual(codeBodies(researchBlocks(resolved)), codeBodies(researchBlocks(markdown)), quoted);
    assert.ok(resolved.includes("[literal][ref]"), quoted);
    assert.match(resolved, /\[Visible\]\(<https:\/\/example.test\/exact>\)/, quoted);
    assert.equal((resolved.match(/\[Visible\]\(<https:\/\/example.test\/exact>\)/g) || []).length,
      (quoted.match(/\[Visible\]\[ref\]/g) || []).length + 1, quoted);
    assert.doesNotMatch(resolved, /\[ref\]: https:/, quoted);
    assert.equal(referenceMarkdown(markdown.replaceAll("\n", "\r\n")).replaceAll("\r\n", "\n"), resolved, quoted);
  }
});
