import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";

const css = fs.readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");
const declarations = (body) => Object.fromEntries([...body.matchAll(/([\w-]+)\s*:\s*([^;]+);/g)].map(([, name, value]) => [name, value.trim()]));
const root = declarations(css.match(/(?:^|\n):root\s*\{([\s\S]*?)\n\}/)?.[1] || "");
const dark = declarations(css.match(/(?:^|\n):root\[data-theme="dark"\]\s*\{([\s\S]*?)\n\}/)?.[1] || "");
const rule = (selector) => {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return declarations(css.match(new RegExp(`(?:^|\\n)${escaped}\\s*\\{([^}]+)\\}`))?.[1] || "");
};
const resolve = (value, tokens, seen = new Set()) => {
  const name = value?.match(/^var\((--[\w-]+)\)$/)?.[1];
  if (!name) return value;
  assert.ok(!seen.has(name), `Cyclic color token ${name}`);
  return resolve(tokens[name], tokens, new Set([...seen, name]));
};
const rgb = (value) => {
  assert.match(value || "", /^#[\da-f]{6}$/i, `Expected an opaque sRGB color, got ${value}`);
  return value.slice(1).match(/../g).map((part) => parseInt(part, 16) / 255);
};
const luminance = (channels) => channels.map((v) => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4).reduce((sum, v, i) => sum + v * [.2126, .7152, .0722][i], 0);
const contrast = (foreground, background, opacity = 1) => {
  const back = rgb(background);
  const front = rgb(foreground).map((v, i) => v * opacity + back[i] * (1 - opacity));
  const values = [luminance(front), luminance(back)].sort((a, b) => b - a);
  return (values[0] + .05) / (values[1] + .05);
};
const themes = { light: root, dark: { ...root, ...dark } };

test("ordinary, unrelated and selected theory dependencies retain 3:1 contrast in both themes", () => {
  const base = rule(".theory-edge");
  for (const [theme, tokens] of Object.entries(themes)) {
    for (const state of ["", ".unrelated", ".related"]) {
      const style = { ...base, ...(state ? rule(`.theory-edge${state}`) : {}) };
      const opacity = Number(style.opacity ?? 1);
      assert.ok(Number.isFinite(opacity) && opacity >= 0 && opacity <= 1);
      const color = resolve(tokens[state === ".related" ? "--accent" : "--graph-edge"], tokens);
      const ratio = contrast(color, resolve(tokens["--graph-surface"], tokens), opacity);
      assert.ok(ratio >= 3, `${theme} ${state || "ordinary"} dependency contrast is ${ratio.toFixed(3)}:1`);
    }
  }
});

test("selected reader boundary retains 3:1 contrast against its fill and adjacent reading surfaces", () => {
  const selected = rule(':is(.p1-reader-tabs,.phase-reader-tabs,.empirical-tabs) > button[aria-selected="true"]');
  assert.ok(selected["border-color"], "Selected readers need a visible boundary");
  for (const [theme, tokens] of Object.entries(themes)) {
    const boundary = resolve(selected["border-color"], tokens);
    for (const surface of ["--tab-selected", "--panel", "--panel-subtle"]) {
      const ratio = contrast(boundary, resolve(tokens[surface], tokens));
      assert.ok(ratio >= 3, `${theme} selected reader boundary against ${surface} is ${ratio.toFixed(3)}:1`);
    }
  }
});
