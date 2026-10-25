import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { memberForm, memberDraft, refreshMemberDrafts, memberUpdatePayload, providerIsControlled } from "../src/teamSettings.js";

const file = { path: "C:\\Research\\providers.toml", exists: true, active: true, error: null };
const effective = {
  provider: "custom", provider_id: "lab", model: "lab-current", reasoning_effort: "high",
  provider_base_url: "https://provider.example/v1", provider_env_key: "LAB_KEY", soul: "Current instructions",
  auto_compact_tokens: 90000, max_turn_input_tokens: 0, provider_source: "file", provider_config_path: file.path,
  credential_source: "file", credential_configured: true,
};
const oldManualDraft = {
  provider: "openai", model: "old-model", reasoning_effort: "low", provider_id: "old-provider",
  provider_env_key: "OLD_KEY", soul: "My unsaved instructions", auto_compact_tokens: "50000", max_turn_input_tokens: "0",
};

test("blank member settings start at Sol 6.1 xhigh while explicit saved choices survive", () => {
  const initial = memberForm();
  assert.equal(initial.model, "gpt-6.1-sol"); assert.equal(initial.reasoning_effort, "xhigh");
  const saved = memberForm({ model: "chosen-model", reasoning_effort: "medium" });
  assert.equal(saved.model, "chosen-model"); assert.equal(saved.reasoning_effort, "medium");
});

test("effective file settings replace stale manual session fields while keeping unsaved member edits", () => {
  const form = memberForm(effective, oldManualDraft, file);
  assert.equal(form.provider, "custom");
  assert.equal(form.model, "lab-current");
  assert.equal(form.reasoning_effort, "high");
  assert.equal(form.provider_env_key, "LAB_KEY");
  assert.equal(form.soul, "My unsaved instructions");
  assert.equal(form.auto_compact_tokens, "50000");
  assert.equal(form.provider_source, undefined);
  assert.deepEqual(memberDraft(effective, form, file), { soul: "My unsaved instructions", auto_compact_tokens: "50000" });
});

test("refresh updates file-controlled values for every member and preserves only editable drafts", () => {
  const members = { research_lead: effective, theorist: { ...effective, model: "theory-new" } };
  const drafts = refreshMemberDrafts(members, { research_lead: oldManualDraft, theorist: { model: "theory-old", soul: "Theorist draft" } }, file);
  assert.deepEqual(drafts.research_lead, { soul: "My unsaved instructions", auto_compact_tokens: "50000" });
  assert.deepEqual(drafts.theorist, { soul: "Theorist draft" });
  assert.equal(memberForm(members.theorist, drafts.theorist, file).model, "theory-new");
  const refreshed = { ...members, research_lead: { ...effective, model: "lab-next", reasoning_effort: "xhigh" } };
  const next = memberForm(refreshed.research_lead, refreshMemberDrafts(refreshed, drafts, file).research_lead, file);
  assert.equal(next.model, "lab-next");
  assert.equal(next.reasoning_effort, "xhigh");
  assert.equal(next.soul, "My unsaved instructions");
});

test("saving file-managed instructions and thresholds never sends provider, model, or credential fields", () => {
  const form = memberForm(effective, oldManualDraft, file);
  assert.deepEqual(memberUpdatePayload(effective, form, file), { soul: "My unsaved instructions", auto_compact_tokens: 50000, max_turn_input_tokens: 0 });
  assert.deepEqual(memberDraft(effective, memberForm(effective), file), {});
  assert.equal(providerIsControlled(effective, null), true);
});

test("invalid file blocks manual-provider drafts and payloads while allowing instruction saves", () => {
  const invalid = { ...file, active: false, error: "model must be specified" };
  const stored = { ...effective, provider_source: "member", model: "stored-manual" };
  const form = memberForm(stored, oldManualDraft, invalid);
  assert.equal(providerIsControlled(stored, invalid), true);
  assert.equal(form.model, "stored-manual");
  assert.equal(form.soul, "My unsaved instructions");
  assert.deepEqual(memberUpdatePayload(stored, form, invalid), { soul: "My unsaved instructions", auto_compact_tokens: 50000, max_turn_input_tokens: 0 });
});

test("absent shared file retains editable manual provider settings and validation", () => {
  const manual = { ...effective, provider_source: "member" };
  const absent = { ...file, exists: false, active: false };
  const form = memberForm(manual, oldManualDraft, absent);
  assert.equal(providerIsControlled(manual, absent), false);
  assert.equal(form.model, "old-model");
  assert.equal(memberUpdatePayload(manual, form, absent).provider, "openai");
  assert.equal(memberUpdatePayload(manual, form, absent).reasoning_effort, "low");
  assert.throws(() => memberUpdatePayload(manual, { ...form, auto_compact_tokens: "3.5" }, absent), /whole numbers/);
});

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-team-render-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({
  stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import {ProviderConfigNotice,EffectiveProviderSettings} from '${src}/components/ProviderSettings.jsx'; import TeamView from '${src}/components/TeamView.jsx'; import {Dialog} from '${src}/components/Shared.jsx'; export const notice = props => renderToStaticMarkup(React.createElement(ProviderConfigNotice, props)); export const effective = props => renderToStaticMarkup(React.createElement(EffectiveProviderSettings, props)); export const team = props => renderToStaticMarkup(React.createElement(TeamView, props)); export const teamDialog = () => renderToStaticMarkup(React.createElement(Dialog, {title: 'Team Settings', onClose: () => {}}, React.createElement(TeamView, {projectId: 'project.test', embedded: true})));`, resolveDir: src },
  outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic",
  loader: { ".css": "empty" },
  alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom") }, logLevel: "silent",
});
const render = require(bundle);
fs.unlinkSync(bundle); fs.rmdirSync(directory);

test("embedded team settings reuse the dialog heading and preserve the description", () => {
  const page = render.team({ projectId: "project.test" });
  assert.match(page, /<h1>Team Settings<\/h1>/);
  const overlay = render.teamDialog();
  assert.equal((overlay.match(/<h[12]\b[^>]*>Team Settings<\/h[12]>/g) || []).length, 1);
  assert.doesNotMatch(overlay, /<h1\b/);
  assert.match(overlay, /Agent models, providers, instructions, and context settings/);
  assert.match(overlay, /Changes apply to the next turn/);
});

test("file-managed summary renders effective values and credential status without controls or secrets", () => {
  const html = render.effective({ member: { ...effective, api_key: "never-display-this-secret" } });
  assert.match(html, /lab-current/);
  assert.match(html, /high/);
  assert.match(html, /Provider file/);
  assert.match(html, /Configured/);
  assert.match(html, /Base URL<\/dt><dd>https:\/\/provider.example\/v1/);
  assert.doesNotMatch(html, /<input|<select|<textarea|never-display-this-secret|LAB_KEY/);
  const missing = render.effective({ member: { ...effective, credential_source: "environment", credential_configured: false } });
  assert.match(missing, /Host environment/);
  assert.match(missing, /Not configured/);
  assert.match(missing, /API key environment variable<\/dt><dd>LAB_KEY/);
  assert.doesNotMatch(missing, /never-display-this-secret/);
});

test("active file notice names shared source, refresh behavior, and next-turn timing compactly", () => {
  const html = render.notice({ config: file });
  assert.match(html, /Agent models and providers/);
  assert.match(html, /Shared provider defaults and member overrides/);
  assert.match(html, /next turn across all projects/);
  assert.match(html, /Refresh settings/);
  assert.doesNotMatch(html, /<input|<select/);
  assert.match(render.notice({ config: file, refreshing: true }), /disabled="".*Refreshing/);
});

test("mixed member providers display each member's effective connection independently", () => {
  const lead = render.effective({ member: { ...effective, provider_id: "glm", model: "glm-5", provider_base_url: "https://glm.example/v1" } });
  const theorist = render.effective({ member: { ...effective, provider: "openai", provider_id: "", model: "gpt-5.6-sol", credential_source: "account", provider_base_url: "" } });
  assert.match(lead, /Provider<\/dt><dd>glm/);
  assert.match(lead, /glm-5/);
  assert.match(lead, /Base URL<\/dt><dd>https:\/\/glm.example\/v1/);
  assert.match(theorist, /Provider<\/dt><dd>OpenAI account/);
  assert.match(theorist, /gpt-5.6-sol/);
  assert.doesNotMatch(theorist, /glm|Base URL|LAB_KEY/);
});

test("invalid file is actionable and never displays stored manual fallback as effective", () => {
  const invalid = { ...file, active: false, error: "model must be specified" };
  const notice = render.notice({ config: invalid });
  assert.match(notice, /role="alert"/);
  assert.match(notice, /model must be specified/);
  assert.match(notice, /Open configuration to fix provider settings/);
  assert.match(notice, /instructions and token thresholds can still be saved/);
  const summary = render.effective({ member: effective, invalid: true });
  assert.match(summary, /unavailable until the provider file is corrected/);
  assert.doesNotMatch(summary, /lab-current|<input|<select/);
});

test("absent file offers an optional path without replacing manual configuration", () => {
  const html = render.notice({ config: { ...file, exists: false, active: false } });
  assert.match(html, /Agent models and providers/);
  assert.match(html, /or use the member settings below/);
  assert.doesNotMatch(html, /Edit provider file/);
  assert.doesNotMatch(html, /role="alert"/);
});

test("the entry point and selected-member summary expose provider configuration directly", () => {
  const notice = render.notice({ config: file, onEdit: () => {} });
  assert.match(notice, /<button\b(?=[^>]*class="btn ui-action")(?=[^>]*data-action="edit")[^>]*>/);
  assert.match(notice, />Configure agent models and providers</);
  const summary = render.effective({ member: effective, onEdit: () => {} });
  assert.match(summary, />Configure provider</);
  assert.match(summary, /Shared across projects/);
  assert.match(summary, /API key, or reasoning effort/);
});
