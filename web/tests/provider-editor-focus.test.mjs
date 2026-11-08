import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-provider-focus-"));
const bundle = path.join(directory, "test.cjs");
const src = fileURLToPath(new URL("../src", import.meta.url)).replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; export {default as TeamView} from '${src}/components/TeamView.jsx'; export {default as ProviderFileEditor,ProviderFileEditorForm} from '${src}/components/ProviderFileEditor.jsx'; export {ProviderConfigNotice,EffectiveProviderSettings} from '${src}/components/ProviderSettings.jsx'; export {api} from '${src}/api.js'; export const dispatcher=React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher;`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const nodes = tree => Array.isArray(tree) ? tree.flatMap(nodes) : tree && typeof tree === "object" && tree.props ? [tree, ...nodes(tree.props.children)] : [];
const find = (tree, predicate) => nodes(tree).find(predicate);

// Attach the settings regions before committing shipped effects, as React does.
function mount(Component, props, attach = () => {}) {
  const slots = []; let cursor = 0; let pending = []; let dirty = true; let tree;
  const state = initial => { const index = cursor++; if (!slots[index]) slots[index] = { value: typeof initial === "function" ? initial() : initial }; return [slots[index].value, update => { const next = typeof update === "function" ? update(slots[index].value) : update; if (!Object.is(next, slots[index].value)) { slots[index].value = next; dirty = true; } }]; };
  const effect = (run, dependencies) => { const index = cursor++; const old = slots[index]; if (!old || dependencies.some((value, offset) => !Object.is(value, old.dependencies?.[offset]))) { slots[index] = { dependencies, cleanup: old?.cleanup }; pending.push({ index, run }); } };
  const hooks = { useState: state, useEffect: effect, useLayoutEffect: effect, useRef: initial => { const index = cursor++; return (slots[index] ||= { value: { current: initial } }).value; } };
  const draw = () => { cursor = 0; pending = []; dirty = false; const previous = ui.dispatcher.current; try { ui.dispatcher.current = hooks; tree = Component(props); } finally { ui.dispatcher.current = previous; } attach(tree); for (const { index, run } of pending) { slots[index].cleanup?.(); slots[index].cleanup = run(); } };
  return { get tree() { return tree; }, async settle() { for (let index = 0; index < 25; index++) { if (dirty) draw(); await new Promise(resolve => setImmediate(resolve)); if (!dirty) return tree; } throw new Error("Settings did not settle."); }, unmount() { for (const slot of slots) slot?.cleanup?.(); } };
}

async function settings({ embedded, exit, origin = "notice", removeInvoker = false, controlled = false }, check) {
  const previous = { api: { ...ui.api }, sessionStorage: globalThis.sessionStorage };
  globalThis.sessionStorage = { getItem: () => null, setItem() {} };
  const member = { provider: "openai", provider_source: controlled ? "file" : "member", model: "fixture-model", reasoning_effort: "high" };
  ui.api.project = async () => ({ members: { research_lead: member }, provider_config: { exists: false, active: false } });
  ui.api.providerOptions = async () => ({ openai_models: ["fixture-model"] });
  ui.api.providerEditor = async () => {
    if (exit === "load-error") throw new Error("Fixture provider load failed.");
    return { path: "fixture/providers.toml", token: "fixture", document: exit === "invalid-file" ? null : { provider: { type: "openai", model: "fixture-model" }, members: {} } };
  };
  const focused = []; let noticeButton; let memberButton; let returned = false;
  const element = textContent => ({ textContent, isConnected: true, disabled: false, hidden: false, closest() { return this.hidden ? {} : null; }, focus(options) { focused.push({ element: this, options }); } });
  const header = element("Team Settings"), editorRegion = element("Provider editor");
  const noticeRegion = { querySelectorAll: () => noticeButton?.isConnected ? [noticeButton] : [] };
  const memberRegion = { querySelectorAll: () => memberButton?.isConnected ? [memberButton] : [] };
  const fixture = mount(ui.TeamView, { projectId: "project.focus", embedded }, tree => {
    find(tree, node => node.type === "header").ref.current = header;
    find(tree, node => node.props.children?.type === ui.ProviderConfigNotice).ref.current = noticeRegion;
    const notice = find(tree, node => node.type === ui.ProviderConfigNotice);
    const editor = find(tree, node => node.type === ui.ProviderFileEditor);
    if (notice.props.onEdit) {
      if (!noticeButton?.isConnected) noticeButton = element("Configure agent models and providers");
      if (returned && removeInvoker && origin === "notice") noticeButton.isConnected = false;
    } else if (noticeButton) noticeButton.isConnected = false;
    const body = find(tree, node => node.props.className === "body" && node.ref);
    if (body) { body.ref.current = memberRegion; memberButton ||= element(controlled ? "Configure provider" : "Configure provider and API key"); memberButton.hidden = Boolean(editor); }
    if (returned && removeInvoker && origin === "member") memberButton.isConnected = false;
    if (editor) find(tree, node => node.props.className === "team-provider-editor-region").ref.current = editorRegion;
  });
  let child;
  try {
    await fixture.settle(); assert.equal(focused.length, 0, "Loading settings leaves focus alone.");
    const original = origin === "notice" ? noticeButton : memberButton;
    const invoke = origin === "notice" ? find(fixture.tree, node => node.type === ui.ProviderConfigNotice).props.onEdit
      : controlled ? find(fixture.tree, node => node.type === ui.EffectiveProviderSettings).props.onEdit
        : find(fixture.tree, node => node.props.children === "Configure provider and API key").props.onClick;
    invoke({ currentTarget: original }); await fixture.settle();
    assert.equal(focused.at(-1).element, editorRegion);
    child = mount(ui.ProviderFileEditor, find(fixture.tree, node => node.type === ui.ProviderFileEditor).props);
    await child.settle();
    const form = find(child.tree, node => node.type === ui.ProviderFileEditorForm);
    const close = exit === "normal" ? find(form.type(form.props), node => node.props.children === "Back to team settings")
      : find(child.tree, node => node.props.children === "Close editor");
    assert.ok(close, `${exit} exposes its exit control.`);
    returned = true; close.props.onClick(); await fixture.settle();
    const expected = removeInvoker ? origin === "member" ? noticeButton : header : origin === "notice" ? noticeButton : original;
    assert.equal(focused.at(-1).element, expected);
    assert.deepEqual(focused.at(-1).options, { preventScroll: true });
    if (origin === "notice" && !removeInvoker) assert.notEqual(noticeButton, original, "The exact notice action is recovered after remount.");
    const count = focused.length;
    await find(fixture.tree, node => node.type === ui.ProviderConfigNotice).props.onRefresh(); await fixture.settle();
    assert.equal(focused.length, count, "An unchanged settings refresh does not move focus.");
    await check?.({ focused, original });
  } finally { child?.unmount(); fixture.unmount(); Object.assign(ui.api, previous.api); if (previous.sessionStorage === undefined) delete globalThis.sessionStorage; else globalThis.sessionStorage = previous.sessionStorage; }
}

for (const embedded of [false, true]) for (const exit of ["normal", "load-error", "invalid-file"]) for (const origin of ["notice", "member"]) {
  test(`${embedded ? "embedded" : "full-page"} provider ${exit} exit returns to its ${origin} invoker`, async () => settings({ embedded, exit, origin }));
}
test("a removed member invoker falls back to provider configuration nearby", async () => settings({ embedded: true, exit: "load-error", origin: "member", removeInvoker: true }));
test("missing provider controls fall back to the settings heading", async () => settings({ embedded: false, exit: "normal", removeInvoker: true }));
for (const embedded of [false, true]) for (const exit of ["normal", "load-error"]) {
  test(`${embedded ? "embedded" : "full-page"} file-managed member ${exit} exit returns to Configure provider`, async () => settings({ embedded, exit, origin: "member", controlled: true }));
}
