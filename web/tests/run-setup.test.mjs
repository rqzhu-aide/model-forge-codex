import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { runSetupStatus } from "../src/runSetup.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-run-setup-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({
  stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import RunSetupGuidance from '${src}/components/RunSetupGuidance.jsx'; export const render = props => renderToStaticMarkup(React.createElement(RunSetupGuidance, props));`, resolveDir: src },
  outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic",
  alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom") }, logLevel: "silent",
});
const { render } = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const noop = () => {};
const account = (configured) => ({ provider: "openai", credential_source: "account", credential_configured: configured });
const custom = (configured, extra = {}) => ({ provider: "custom", provider_id: "lab", credential_source: "environment", provider_env_key: "LAB_API_KEY", credential_configured: configured, ...extra });
const props = (project) => ({ id: "launch-setup", project, onTeamSettings: noop, onOpenAIAccount: noop });

test("all-custom effective credentials do not require a global OpenAI account", () => {
  const project = { members: { research_lead: custom(true), theorist: custom(true, { provider_source: "file", credential_source: "file" }) }, account: { connected: false } };
  const state = runSetupStatus(project);
  assert.deepEqual(state, { summary: "Credentials configured for all 2 team members.", issues: [], needsOpenAI: false });
  const html = render(props(project));
  assert.match(html, /Team Settings/);
  assert.doesNotMatch(html, /OpenAI Account|Setup details|verified|ready/);
  assert.match(html, /Connections and runtime have not been tested here/);
});

test("existing account credentials remain configured without a global connection record", () => {
  const project = { members: { research_lead: account(true), theorist: account(true) } };
  assert.equal(runSetupStatus(project).needsOpenAI, false);
  const html = render(props(project));
  assert.match(html, /Credentials configured for all 2/);
  assert.doesNotMatch(html, /OpenAI Account|not configured/);
});

test("mixed teams direct only missing account members to OpenAI and name the missing custom key", () => {
  const project = { members: { research_lead: account(false), theorist: custom(true), data_analyst: custom(false), outside_reviewer: account(true) } };
  const state = runSetupStatus(project);
  assert.equal(state.summary, "Credentials configured for 2 of 4 team members.");
  assert.equal(state.needsOpenAI, true);
  assert.equal(state.issues.length, 2);
  assert.match(state.issues[0], /^Research Lead: OpenAI account credentials/);
  assert.match(state.issues[1], /^Data Analyst: LAB_API_KEY is unavailable to the backend/);
  const html = render(props(project));
  assert.match(html, /OpenAI Account/);
  assert.match(html, /Team Settings/);
  assert.doesNotMatch(html, /Theorist:|Outside Reviewer:/);
});

test("a missing custom environment key uses Team Settings with no account action", () => {
  const html = render(props({ members: { research_lead: custom(false) } }));
  assert.match(html, /LAB_API_KEY is unavailable to the backend/);
  assert.match(html, /Check the provider and environment in Team Settings/);
  assert.doesNotMatch(html, /OpenAI Account/);
});

test("an invalid provider file takes priority over fallback account fields", () => {
  const project = { provider_config: { error: "Provider configuration is not valid TOML. Check its syntax locally." }, members: { research_lead: account(false) } };
  const html = render(props(project));
  assert.match(html, /Provider settings need attention/);
  assert.match(html, /Provider configuration is not valid TOML/);
  assert.match(html, /Team Settings/);
  assert.doesNotMatch(html, /OpenAI Account|account credentials are not configured/);
});

test("unknown readiness points to settings without inventing missing account credentials", () => {
  for (const project of [undefined, {}, { members: {} }, { members: { research_lead: { provider: "openai" } } }]) {
    const state = runSetupStatus(project);
    assert.equal(state.needsOpenAI, false);
    const html = render(props(project));
    assert.match(html, /unavailable|configured for 0/);
    assert.match(html, /Team Settings/);
    assert.doesNotMatch(html, /OpenAI Account/);
  }
});

test("guidance is descriptive and its settings controls never submit the research form", () => {
  const html = render(props({ members: { research_lead: account(false) } }));
  assert.match(html, /id="launch-setup" role="status"/);
  assert.match(html, /<summary>Setup details<\/summary>/);
  assert.equal((html.match(/type="button"/g) || []).length, 2);
  assert.doesNotMatch(html, /type="submit"|Test connection|Connect account to research team/);
});
