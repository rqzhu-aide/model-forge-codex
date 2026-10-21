import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { teamProbeSignature, editorProbeSignature, hasUnsavedProviderChanges, ProbeController } from "../src/providerProbe.js";
import { editorFromDocument } from "../src/providerEditor.js";

const MEMBER = {
  provider: "custom", provider_id: "lab", provider_base_url: "https://p.example/v1",
  provider_env_key: "LAB_KEY", model: "m1", reasoning_effort: "high",
  credential_source: "environment", credential_configured: true, provider_source: "member",
  soul: "Long member instructions",
};
const FORM = {
  provider: "custom", provider_id: "lab", provider_base_url: "https://p.example/v1",
  provider_env_key: "LAB_KEY", model: "m1", reasoning_effort: "high", soul: "Long member instructions",
};

test("team probe signature is stable without edits and tracks provider-relevant changes", () => {
  const config = { active: false, error: null };
  const base = teamProbeSignature(MEMBER, FORM, config);
  assert.equal(teamProbeSignature(MEMBER, FORM, config), base);
  // Instructions and token thresholds are not provider connection settings.
  assert.equal(teamProbeSignature({ ...MEMBER, soul: "changed" }, { ...FORM, soul: "changed" }, config), base);
  assert.notEqual(teamProbeSignature({ ...MEMBER, model: "m2" }, FORM, config), base);
  assert.notEqual(teamProbeSignature(MEMBER, { ...FORM, model: "m2" }, config), base);
  assert.notEqual(teamProbeSignature(MEMBER, FORM, { active: true, error: null }), base);
  assert.notEqual(teamProbeSignature(MEMBER, FORM, { active: false, error: "bad file" }), base);
});

test("editor probe signature covers exactly the member table and the shared default", () => {
  const document = {
    provider: { type: "custom", id: "lab", base_url: "https://p.example/v1", model: "m1", reasoning_effort: "high", api_key: "k" },
    members: { research_lead: { type: "openai", model: "gpt-5.6", reasoning_effort: "medium" } },
  };
  const editor = editorFromDocument(document);
  const base = editorProbeSignature(editor, "theorist");
  assert.equal(editorProbeSignature(editor, "theorist"), base);
  // Editing another member does not invalidate this member's probe result.
  const other = { ...editor, members: { ...editor.members, research_lead: { ...editor.members.research_lead, model: "other" } } };
  assert.equal(editorProbeSignature(other, "theorist"), base);
  const edited = { ...editor, members: { ...editor.members, theorist: { ...editor.members.theorist, model: "changed" } } };
  assert.notEqual(editorProbeSignature(edited, "theorist"), base);
  const shared = { ...editor, shared: { ...editor.shared, model: "changed" } };
  assert.notEqual(editorProbeSignature(shared, "theorist"), base);
});

test("an edit clears the previous result and retires an in-flight probe", async () => {
  const controller = new ProbeController();
  assert.equal(controller.sync("settings-a"), true);
  let resolve;
  const pending = controller.probe(() => new Promise((r) => { resolve = r; }));
  assert.equal(controller.state.pending, true);
  // The user edits a relevant field while the probe is running: the pending
  // flag clears and the late response is discarded, never displayed.
  controller.sync("settings-b");
  assert.deepEqual(controller.state, { pending: false, result: null, error: null });
  resolve({ status: "ok" });
  await pending;
  assert.deepEqual(controller.state, { pending: false, result: null, error: null });
  // A fresh probe against the edited settings displays normally.
  await controller.probe(async () => ({ status: "ok" }));
  assert.equal(controller.state.result.status, "ok");
  // Re-rendering with an unchanged signature keeps the result; an edit clears it.
  assert.equal(controller.sync("settings-b"), false);
  assert.equal(controller.state.result.status, "ok");
  assert.equal(controller.sync("settings-c"), true);
  assert.equal(controller.state.result, null);
});

test("switching identically configured members retires the previous member's pending and completed results", async () => {
  const controller = new ProbeController();
  const signature = (role) => teamProbeSignature(MEMBER, FORM, null, role);
  controller.sync(signature("research_lead"));
  let resolve;
  const pending = controller.probe(() => new Promise((done) => { resolve = done; }));
  assert.equal(controller.state.pending, true);
  assert.equal(controller.sync(signature("theorist")), true);
  resolve({ status: "ok", member: "research_lead" });
  await pending;
  assert.equal(controller.state.result, null);
  await controller.probe(async () => ({ status: "failed", member: "theorist" }));
  assert.equal(controller.state.result.member, "theorist");
  controller.sync(signature("research_lead"));
  assert.equal(controller.state.result, null);
});

test("unsaved provider edits require saving before a saved-settings probe; instruction edits do not", () => {
  assert.equal(hasUnsavedProviderChanges(MEMBER, FORM), false);
  assert.equal(hasUnsavedProviderChanges(MEMBER, { ...FORM, model: "new-model" }), true);
  assert.equal(hasUnsavedProviderChanges(MEMBER, { ...FORM, reasoning_effort: "none" }), true);
  assert.equal(hasUnsavedProviderChanges(MEMBER, { ...FORM, provider_env_key: "OTHER_KEY" }), true);
  assert.equal(hasUnsavedProviderChanges(MEMBER, { ...FORM, soul: "new instructions", auto_compact_tokens: 5000 }), false);
});

test("a failed probe surfaces the error and the next edit clears it", async () => {
  const controller = new ProbeController();
  controller.sync("a");
  await controller.probe(async () => { throw new Error("backend unavailable"); });
  assert.equal(controller.state.error.message, "backend unavailable");
  assert.equal(controller.state.pending, false);
  controller.sync("b");
  assert.deepEqual(controller.state, { pending: false, result: null, error: null });
});

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-provider-probe-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({
  stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import {ProviderProbe, ProviderProbeResult} from '${src}/components/ProviderProbe.jsx'; import {ProviderFileEditorForm} from '${src}/components/ProviderFileEditor.jsx'; export const probeResult = props => renderToStaticMarkup(React.createElement(ProviderProbeResult, props)); export const probe = props => renderToStaticMarkup(React.createElement(ProviderProbe, props)); export const form = props => renderToStaticMarkup(React.createElement(ProviderFileEditorForm, props));`, resolveDir: src },
  outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic",
  alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom") }, logLevel: "silent",
});
const render = require(bundle);
fs.unlinkSync(bundle); fs.rmdirSync(directory);
const noop = () => {};

const CHECKS_OK = { configuration: "ok", connection: "ok", model_response: "ok", tool_exchange: "ok", final_response: "ok" };

test("a successful probe renders every check OK with scope and elapsed time", () => {
  const html = render.probeResult({ scopeLabel: "Saved settings", result: {
    status: "ok", summary: "Basic connection and tool use verified.", checks: CHECKS_OK,
    failure: null, scope: "saved", simulated: false, elapsed_ms: 1234,
  } });
  assert.match(html, /provider-probe-result ok/);
  assert.match(html, /Connection verified/);
  assert.match(html, /Basic connection and tool use verified\./);
  assert.match(html, /Saved settings/);
  assert.match(html, /1\.2s/);
  for (const label of ["Configuration", "Connection", "Model response", "Tool exchange", "Final response"]) {
    assert.match(html, new RegExp(label));
  }
  assert.equal(html.match(/<span class="provider-probe-check-state">OK</g).length, 5);
  assert.doesNotMatch(html, /Failed|Not reached/);
});

test("a partial probe distinguishes the tool exchange from the working connection", () => {
  const html = render.probeResult({ scopeLabel: "Unsaved draft", result: {
    status: "partial",
    summary: "The provider connected and responded, but the probe tool exchange did not complete.",
    checks: { ...CHECKS_OK, tool_exchange: "failed" },
    failure: { category: "tool_call", message: "The model responded, but the probe tool exchange did not complete; research turns need function-calling support." },
    scope: "draft", simulated: false, elapsed_ms: 900,
  } });
  assert.match(html, /provider-probe-result partial/);
  assert.match(html, /Partial success/);
  assert.match(html, /Unsaved draft/);
  assert.match(html, /function-calling support/);
  assert.match(html, /Tool exchange<\/span><span class="provider-probe-check-state">Failed/);
  assert.match(html, /Model response<\/span><span class="provider-probe-check-state">OK/);
});

test("a failed probe shows the fixed category message and unreached checks", () => {
  const message = "The provider rejected the configured credential. Check the API key or its environment variable.";
  const html = render.probeResult({ scopeLabel: "Saved settings", result: {
    status: "failed", summary: message,
    checks: { configuration: "ok", connection: "failed", model_response: "skipped", tool_exchange: "skipped", final_response: "skipped" },
    failure: { category: "authentication", message }, scope: "saved", simulated: false, elapsed_ms: 300,
  } });
  assert.match(html, /provider-probe-result failed/);
  assert.match(html, /Connection test failed/);
  assert.equal(html.match(/rejected the configured credential/g).length, 1); // summary == failure: shown once
  assert.match(html, /Connection<\/span><span class="provider-probe-check-state">Failed/);
  assert.equal(html.match(/<span class="provider-probe-check-state">Not reached</g).length, 3);
});

test("probe controls distinguish a draft test from saved settings before sending any request", () => {
  const html = render.probe({ signature: "sig", onProbe: noop });
  assert.match(html, />Test saved settings</);
  assert.match(html, /saved connection/);
  assert.match(html, /may use provider tokens/);
  const draft = render.probe({ signature: "sig", onProbe: noop, scope: "draft" });
  assert.match(draft, />Test these settings</);
  assert.match(draft, /values shown here without saving/);
  const unsaved = render.probe({ signature: "changed", onProbe: noop, disabled: true, disabledReason: "Save provider changes before testing." });
  assert.match(unsaved, /<button\b(?=[^>]*disabled="")(?=[^>]*data-action="check")[^>]*>/);
  assert.match(unsaved, />Test saved settings</);
  assert.match(unsaved, /Save provider changes before testing/);
});

const VIEW = { path: "C:\\Research\\providers.toml", exists: true, error: null, token: "sha256:test" };
const DOCUMENT = {
  provider: { type: "custom", id: "lab", base_url: "https://provider.example/v1", model: "lab-current", reasoning_effort: "high", api_key: "k" },
  members: { research_lead: { type: "openai", model: "gpt-5.6-sol", reasoning_effort: "medium" } },
};
const formProps = (overrides = {}) => ({
  view: VIEW, editor: editorFromDocument(DOCUMENT), onEditorChange: noop, onSave: noop, onRemove: noop,
  onRefresh: noop, onClose: noop, onToggleRemove: noop, ...overrides,
});

test("the file editor offers a draft probe per governed member when a project is known", () => {
  const html = render.form(formProps({ projectId: "project.demo" }));
  assert.equal(html.match(/>Test these settings</g).length, 4); // Hidden panels preserve each member's probe state.
  const ungoverned = render.form(formProps({ projectId: "project.demo", editor: editorFromDocument({ provider: {}, members: {} }) }));
  assert.doesNotMatch(ungoverned, />Test these settings</);
  const noProject = render.form(formProps());
  assert.doesNotMatch(noProject, />Test these settings</);
});
