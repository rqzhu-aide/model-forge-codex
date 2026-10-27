import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import {
  editorFromDocument, documentFromEditor, maskKey, isShimConnection, blankDocument, EMPTY_MEMBER_EDITOR, EMPTY_CONNECTION,
} from "../src/providerEditor.js";

test("new connections use Sol 6.1 xhigh while shared inheritance and saved effort remain intact", () => {
  assert.equal(EMPTY_CONNECTION.model, "gpt-6.1-sol"); assert.equal(EMPTY_CONNECTION.reasoning_effort, "xhigh");
  const editor = editorFromDocument({ provider: { type: "openai", model: "gpt-6.1-sol" }, members: { theorist: { type: "openai", model: "chosen-model", reasoning_effort: "medium" } } });
  assert.equal(editor.shared.reasoning_effort, "xhigh");
  assert.equal(editor.members.research_lead.model, ""); assert.equal(editor.members.research_lead.reasoning_effort, "");
  assert.equal(editor.members.theorist.model, "chosen-model"); assert.equal(editor.members.theorist.reasoning_effort, "medium");
});

const KEY = "sk-fixture-1234";
const DOCUMENT = {
  provider: { type: "custom", id: "lab", base_url: "https://provider.example/v1", model: "lab-current", reasoning_effort: "high", api_key: KEY },
  members: {
    research_lead: { type: "openai", model: "gpt-5.6-sol", reasoning_effort: "medium" },
    theorist: { model: "theory-model", reasoning_effort: "low" },
  },
};

test("stored keys mask to their last characters, and short keys never leak", () => {
  assert.equal(maskKey(KEY), "••••••1234");
  assert.equal(maskKey("abc"), "••••••");
  assert.equal(maskKey(""), "");
  assert.equal(maskKey(null), "");
});

test("shim connections are recognized by id or loopback shim port", () => {
  assert.equal(isShimConnection({ id: "shim", base_url: "https://remote.example/v1" }), true);
  assert.equal(isShimConnection({ id: "lab", base_url: "http://127.0.0.1:8780/v1" }), true);
  assert.equal(isShimConnection({ id: "lab", base_url: "https://provider.example/v1" }), false);
});

test("the editor document round-trips through editor state and back into the save payload", () => {
  const editor = editorFromDocument(DOCUMENT);
  assert.equal(editor.shared.id, "lab");
  assert.equal(editor.shared.api_key, KEY);
  assert.equal(editor.members.research_lead.mode, "openai");
  assert.equal(editor.members.theorist.mode, "default");
  assert.equal(editor.members.data_analyst.mode, "default");
  assert.equal(editor.members.data_analyst.model, "");
  assert.equal(editor.members.data_analyst.reasoning_effort, "");
  assert.deepEqual(documentFromEditor(editor), DOCUMENT);
});

test("member-first payloads: ungoverned members vanish, openai needs no key, blank overrides disappear", () => {
  const editor = editorFromDocument({ provider: {}, members: {} });
  assert.deepEqual(Object.values(editor.members).map((member) => member.mode), ["ungoverned", "ungoverned", "ungoverned", "ungoverned"]);
  assert.equal(editor.shared, null);
  assert.deepEqual(documentFromEditor(editor), { provider: {}, members: {} });
  const custom = { ...EMPTY_MEMBER_EDITOR, mode: "custom", id: "leadlab", base_url: "https://lead.example/v1", model: "m1", reasoning_effort: "medium", api_key: "k1" };
  const openai = { ...EMPTY_MEMBER_EDITOR, mode: "openai", model: "gpt-5.6-sol", reasoning_effort: "high" };
  const account = { ...EMPTY_MEMBER_EDITOR, mode: "custom", id: "envlab", base_url: "https://env.example/v1", model: "m2", reasoning_effort: "medium", credential: "env", api_key: "ignored", api_key_env: "ENV_KEY" };
  const document = documentFromEditor({ shared: null, members: { research_lead: custom, theorist: openai, data_analyst: account, outside_reviewer: { ...EMPTY_MEMBER_EDITOR } } });
  assert.deepEqual(document, { provider: {}, members: {
    research_lead: { type: "custom", model: "m1", reasoning_effort: "medium", id: "leadlab", base_url: "https://lead.example/v1", api_key: "k1" },
    theorist: { type: "openai", model: "gpt-5.6-sol", reasoning_effort: "high" },
    data_analyst: { type: "custom", model: "m2", reasoning_effort: "medium", id: "envlab", base_url: "https://env.example/v1", api_key_env: "ENV_KEY" },
  } });
  // A shared-default member with no overrides needs no table; removing the
  // shared default drops the provider table but keeps standalone members.
  const withDefault = editorFromDocument(DOCUMENT);
  withDefault.members.theorist = { ...EMPTY_MEMBER_EDITOR, mode: "default" };
  assert.deepEqual(documentFromEditor(withDefault).members.theorist, undefined);
  withDefault.shared = null;
  const withoutDefault = documentFromEditor(withDefault);
  assert.deepEqual(withoutDefault.provider, {});
  assert.deepEqual(withoutDefault.members.research_lead, DOCUMENT.members.research_lead);
  assert.deepEqual(blankDocument(), { provider: {}, members: {} });
});

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-provider-editor-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({
  stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import {ProviderFileEditorForm, SecretKeyField} from '${src}/components/ProviderFileEditor.jsx'; export const form = props => renderToStaticMarkup(React.createElement(ProviderFileEditorForm, props)); export const secret = props => renderToStaticMarkup(React.createElement(SecretKeyField, props));`, resolveDir: src },
  outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic",
  alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom") }, logLevel: "silent",
});
const render = require(bundle);
fs.unlinkSync(bundle); fs.rmdirSync(directory);
const noop = () => {};

const VIEW = { path: "C:\\Research\\providers.toml", exists: true, error: null, token: "sha256:test", document: DOCUMENT };
const formProps = (overrides = {}) => ({
  view: VIEW, editor: editorFromDocument(DOCUMENT), onEditorChange: noop, onSave: noop, onRemove: noop,
  onRefresh: noop, onClose: noop, onToggleRemove: noop, ...overrides,
});

test("the editor masks stored keys behind a reveal toggle and never renders the raw key", () => {
  const html = render.form(formProps());
  assert.match(html, /readonly=""[^>]*value="••••••1234"/);
  assert.match(html, /type="password"/);
  assert.match(html, /aria-pressed="false">Show</);
  assert.doesNotMatch(html, new RegExp(KEY));
  const revealed = render.secret({ value: KEY, onChange: noop });
  assert.match(revealed, /aria-pressed="false">Show</);
  assert.match(revealed, /Focus the field or choose Show/);
  const empty = render.secret({ value: "", onChange: noop });
  assert.match(empty, /type="password"/);
  assert.doesNotMatch(empty, /Show</);
});

test("member cards offer shared default, OpenAI account, or a complete custom connection", () => {
  const html = render.form(formProps());
  for (const label of ["Research Lead", "Theorist", "Data Analyst", "Outside Reviewer"]) {
    assert.match(html, new RegExp(`<h3>${label}</h3>`));
  }
  assert.match(html, /aria-pressed="true"[^>]*>OpenAI account</);
  assert.match(html, /aria-pressed="true"[^>]*>Shared default</);
  assert.match(html, /one shared sign-in; each member gets its own conversation/);
  assert.match(html, /Shared connection/);
  assert.match(html, /Provider name \/ ID/);
  assert.match(html, /C:\\Research\\providers.toml/);
  assert.match(html, /Save model and provider settings/);
  assert.doesNotMatch(html, /disabled=""[^>]*>Shared default</);
});

test("without a shared default the shared option is disabled and ungoverned members are explained", () => {
  const editor = editorFromDocument({ provider: {}, members: {} });
  const html = render.form(formProps({ editor, view: { ...VIEW, exists: false } }));
  assert.match(html, /disabled=""[^>]*>Shared default</);
  assert.equal(html.match(/This member uses its saved project settings/g).length, 4);
  assert.match(html, /No shared default/);
  assert.match(html, /Add shared default/);
  assert.doesNotMatch(html, /Remove provider file/);
});

test("a conflict shows the changed-outside notice with a refresh action", () => {
  const html = render.form(formProps({ conflict: true }));
  assert.match(html, /role="alert"[^>]*>Provider settings changed outside this editor/);
  assert.match(html, /Review the latest settings before saving/);
  assert.match(html, /Refresh editor/);
  assert.match(render.form(formProps({ saveError: "members.theorist: bad value" })), /members\.theorist: bad value/);
  assert.match(render.form(formProps({ savedNotice: true })), /Saved\. New turns read the updated settings/);
});

test("a draft kept across a refresh offers reapply and discard actions, never a force-overwrite", () => {
  const html = render.form(formProps({ draftKept: true }));
  assert.match(html, /role="alert"[^>]*>Provider settings changed outside this editor/);
  assert.match(html, /Review the latest settings before saving/);
  assert.match(html, /unsaved edits were kept/);
  assert.match(html, /Reapply your edits/);
  assert.match(html, /Discard your edits/);
  assert.doesNotMatch(html, /force-overwrite|Overwrite the latest/i);
});

test("an invalid file on disk is repaired in place, and shim help explains both auth modes", () => {
  const broken = render.form(formProps({ view: { ...VIEW, error: "provider.type must be 'openai' or 'custom'." } }));
  assert.match(broken, /currently invalid/);
  assert.match(broken, /provider\.type must be/);
  const shim = editorFromDocument({ provider: { type: "custom", id: "shim", base_url: "http://127.0.0.1:8780/v1", model: "m", api_key: "x" }, members: {} });
  const html = render.form(formProps({ editor: shim }));
  // The note explains both modes without asserting which one is running.
  assert.match(html, /depends on how the shim was started/);
  assert.match(html, /--auth env/);
  assert.match(html, /--auth forward/);
  assert.match(html, /real key from its own env file/);
  assert.match(html, /the real key belongs here/);
});

test("removing the whole file is a two-step action that restores per-member settings", () => {
  const html = render.form(formProps());
  assert.match(html, /Remove provider file/);
  const confirming = render.form(formProps({ confirmingRemove: true }));
  assert.match(confirming, /Confirm removal/);
  assert.match(confirming, /Keep file/);
  assert.match(confirming, /restores each member.{1,8}s per-project saved settings/);
});

test("configuration focuses the chosen member while keeping separate drafts and all-project scope explicit", () => {
  const html = render.form(formProps({ selectedRole: "theorist", projectId: "project.demo" }));
  assert.match(html, /<h2>Configure agent models and providers<\/h2>/);
  assert.match(html, /Saved changes apply across all projects from the next turn/);
  assert.match(html, /<div><section class="provider-member-editor" aria-label="Theorist provider"/);
  assert.match(html, /<div hidden=""><section class="provider-member-editor" aria-label="Research Lead provider"/);
  assert.match(html, /aria-pressed="true">Theorist<\/button>/);
  assert.match(html, /placeholder="lab-current"/);
  assert.match(html, /Shared default \(high\)/);
  assert.match(html, />Test these settings</);
  assert.match(html, /<details class="provider-file-details"><summary>Configuration file and reset/);
});

test("custom provider fields expose credentials and model parameters together and accept nonreasoning models", () => {
  const editor = editorFromDocument({ provider: {}, members: { theorist: {
    type: "custom", id: "research", base_url: "https://research.example/v1", api_key: KEY,
    model: "own-model", reasoning_effort: "none",
  } } });
  const html = render.form(formProps({ editor, selectedRole: "theorist", reasoningEfforts: ["none", "medium", "high"] }));
  assert.match(html, /aria-label="Theorist model"[^>]*value="own-model"/);
  assert.match(html, /aria-label="Theorist base URL"/);
  assert.match(html, /aria-label="Theorist API key"/);
  assert.match(html, /value="none" selected="">none<\/option>/);
  assert.match(html, />Enter API key</);
  assert.doesNotMatch(html, new RegExp(KEY));
});
