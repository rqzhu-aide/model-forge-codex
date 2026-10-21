import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { assumptionSource, conversationDraftKey, conversationPurpose, conversationsForTarget, isConversationTarget, isEarlierConversation } from "../src/assumptionConversations.js";
import { api } from "../src/api.js";
import { conversationSourceReference } from "../src/conversationSources.js";

const target = { kind: "report_section", branch: "method.example", phase: "P5", family: "technical_report", generation_id: "report.current", sha256: "a".repeat(64), object_id: "numerical_analysis", label: "Numerical results", assessmentPurpose: "model_dialogue", responsible_role: "research_lead" };
const frozenTarget = { ...assumptionSource(target), run_id: "run.report", package_id: "package.report" };
const reportUrl = `/api/v1/projects/project.example/branches/${target.branch}/phases/P5/records/technical_report/${target.generation_id}`;
const reportConversation = { target: frozenTarget, source_url: reportUrl,
  target_statement: '<a id="numerical-analysis"></a>\n## Numerical results\n\nThe estimate is $x=1$.\n\n<a id="supporting-detail"></a>\n### Supporting detail\n\nInterpretation.' };

test("report discussion links can use their own frozen target and exact main section anchor", () => {
  const context = { projectId: "project.example", conversation: reportConversation };
  for (const source of [reportUrl, `${reportUrl}#numerical-analysis`]) {
    assert.deepEqual(conversationSourceReference(source, "run.discussion", [], [], context), frozenTarget);
  }
  for (const source of [
    reportUrl.replace("project.example", "project.other"), reportUrl.replace("report.current", "report.other"),
    reportUrl.replace("method.example", "method.other"), reportUrl.replace("/P5/", "/P4/"),
    `${reportUrl}#numerical_analysis`, `${reportUrl}#invented`, `${reportUrl}#supporting-detail`,
    `${reportUrl}#`, `${reportUrl}?download=1`, "/api/v1/account", `https://example.com${reportUrl}#numerical-analysis`,
  ]) assert.equal(conversationSourceReference(source, "run.discussion", [], [], context), null, source);
  for (const conversation of [
    { ...reportConversation, source_url: reportUrl.replace("project.example", "project.other") },
    { ...reportConversation, target: { ...frozenTarget, generation_id: "report.newer" } },
    { ...reportConversation, target: { ...frozenTarget, sha256: null } },
    { ...reportConversation, target: { ...frozenTarget, run_id: null } },
    { ...reportConversation, target: { ...frozenTarget, package_id: null } },
    { ...reportConversation, target: { ...frozenTarget, kind: "phase_issue" } },
    { ...reportConversation, target_statement: '## Numerical results\n\nMissing anchor.' },
    { ...reportConversation, target_statement: `${reportConversation.target_statement}\n\n<a id="numerical-analysis"></a>` },
    { ...reportConversation, target_statement: '```html\n<a id="numerical-analysis"></a>\n```\n## Numerical results' },
    { ...reportConversation, source_error: "The frozen target is unavailable." },
  ]) assert.equal(conversationSourceReference(`${reportUrl}#numerical-analysis`, "run.discussion", [], [], { ...context, conversation }), null);
  assert.equal(conversationSourceReference(reportUrl, "run.discussion", [], [], { ...context, projectId: "project.other" }), null);
  assert.equal(conversationSourceReference(reportUrl, "run.discussion", [], [], { projectId: "project.example" }), null);
});

test("report conversations use exact recognized sections and preserve independent version histories", () => {
  assert.equal(isConversationTarget(target), true);
  assert.equal(conversationPurpose(target), "model_dialogue");
  for (const invalid of [{ phase: "P4" }, { family: "manuscript" }, { object_id: "invented" }, { sha256: null }]) assert.equal(isConversationTarget({ ...target, ...invalid }), false);
  const current = { assessment_id: "current", target: assumptionSource(target), assessment_purpose: "model_dialogue", created_at: "2026-10-20" };
  const earlier = { ...current, assessment_id: "earlier", target: { ...current.target, generation_id: "report.earlier", sha256: "b".repeat(64) }, created_at: "2026-10-19" };
  const foreign = [{ ...current, target: { ...current.target, object_id: "model" } }, { ...current, target: { ...current.target, branch: "method.other" } }];
  assert.deepEqual(conversationsForTarget([...foreign, earlier, current], target).map(item => item.assessment_id), ["current", "earlier"]);
  assert.equal(isEarlierConversation(earlier, target), true);
  assert.equal(isEarlierConversation(current, target), false);
  assert.notEqual(conversationDraftKey("p", target, "section-comment"), conversationDraftKey("p", earlier.target, "section-comment"));
  assert.notEqual(conversationDraftKey("p", target, "section-comment"), conversationDraftKey("p", target));
  assert.equal(assumptionSource(target).label, undefined);
});

test("comment APIs transmit exact targets and expected revisions and preserve conflict status", async () => {
  const originalFetch = globalThis.fetch;
  const requests = [];
  try {
    globalThis.fetch = async (url, options) => { requests.push({ url, options }); return { ok: true, status: 200, json: async () => ({ comment: null }) }; };
    await api.reportSectionComment("project.example", assumptionSource(target));
    await api.saveReportSectionComment("project.example", { target: assumptionSource(target), note: "A concern", expected_revision: 3 });
    assert.deepEqual(JSON.parse(decodeURIComponent(requests[0].url.split("?target=")[1])), assumptionSource(target));
    assert.equal(requests[1].options.method, "PUT");
    assert.equal(JSON.parse(requests[1].options.body).expected_revision, 3);
    globalThis.fetch = async () => ({ ok: false, status: 409, json: async () => ({ detail: "Comment changed" }) });
    await assert.rejects(api.saveReportSectionComment("project.example", {}), error => error.status === 409 && error.message === "Comment changed");
  } finally { globalThis.fetch = originalFetch; }
});

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "report-dialogue-test-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Conversations,{ConversationTranscript} from '${src}/components/AssumptionConversations.jsx'; export {default as Comment} from '${src}/components/ReportSectionComment.jsx'; export {api} from '${src}/api.js'; export {readConversationDraft,saveConversationDraft} from '${src}/assumptionConversations.js'; export const internals=React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED; export const render=props=>renderToStaticMarkup(React.createElement(Conversations,props)); export const transcript=props=>renderToStaticMarkup(React.createElement(ConversationTranscript,props));`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle);
const render = ui.render;
fs.unlinkSync(bundle); fs.rmdirSync(directory);
test("report discussion answers render exact target and supporting sources without trusting other report links", () => {
  const supportingRef = { branch: target.branch, phase: "P4", family: "empirical_synthesis", generation_id: "synthesis.frozen", sha256: "b".repeat(64), run_id: "run.empirical", package_id: "package.empirical" };
  const supportingUrl = `/api/v1/projects/project.example/branches/${target.branch}/phases/P4/records/empirical_synthesis/synthesis.frozen`;
  const answer = `[Table 1](${reportUrl}#numerical-analysis) and [Scope of the findings](${reportUrl}#numerical-analysis). [Supporting interpretation](${supportingUrl}). The estimate is $x=1$.\n\n[Other project](${reportUrl.replace("project.example", "project.other")}#numerical-analysis), [Other generation](${reportUrl.replace("report.current", "report.other")}#numerical-analysis), [Other anchor](${reportUrl}#supporting-detail).`;
  const turn = { run_id: "run.discussion", state: "assessed", instructions: "Explain this section.", assessment_markdown: answer,
    evidence_refs: [{ generation_ref: supportingRef, source_url: supportingUrl }] };
  for (const messages of [false, true]) {
    const conversation = { ...reportConversation, turns: messages ? [] : [turn],
      ...(messages ? { messages: [{ ...turn, role: "assistant", content: answer }] } : {}) };
    const before = JSON.stringify(conversation);
    const html = ui.transcript({ conversation, projectId: "project.example", onSource() {} });
    for (const label of ["Table 1", "Scope of the findings", "Supporting interpretation"]) assert.match(html, new RegExp(`<button(?=[^>]*data-action="source")[^>]*>[\\s\\S]*?${label}<\\/button>`));
    for (const label of ["Other project", "Other generation", "Other anchor"]) assert.ok(html.includes(`${label} (source unavailable)`), label);
    assert.doesNotMatch(html, /href="\/api\/|\[Table 1\]|katex-error/);
    assert.match(html, /class="katex/);
    assert.equal(JSON.stringify(conversation), before);
  }
});

test("section dialog exposes separate comment and question actions without repeating the report", () => {
  const html = render({ projectId: "project.example", target: { ...target, statement: "Entire report section must stay behind the dialog." }, onClose() {}, onSource() {} });
  for (const label of ["Discuss this section", "Numerical results", "Leave a comment", "Your comment on this section", "Save comment", "Your question about this section", "Read this report version"]) assert.ok(html.includes(label), label);
  assert.doesNotMatch(html, /Entire report section must stay behind/);
  assert.match(html, /data-ui-role="research"/);
  assert.match(html, /aria-label="Close dialog"/);
});

const walk = node => Array.isArray(node) ? node.flatMap(walk) : !node || typeof node !== "object" ? [] : [node, ...walk(node.props?.children)];

// Exercise the real component's asynchronous handlers across separate mounts.
// State slots and effect cleanup reproduce closing and reopening the editor.
function commentInstance(props) {
  const slots = [], dependencies = [], cleanups = [], effects = [];
  let index = 0;
  const dispatcher = {
    useRef(value) { const at = index++; return slots[at] ??= { current: value }; },
    useState(value) {
      const at = index++;
      if (!(at in slots)) slots[at] = typeof value === "function" ? value() : value;
      return [slots[at], next => { slots[at] = typeof next === "function" ? next(slots[at]) : next; }];
    },
    useId() { return `comment-${index++}`; },
    useEffect(effect, next) {
      const at = index++;
      if (!dependencies[at] || next.some((value, position) => value !== dependencies[at][position])) {
        dependencies[at] = next;
        effects.push(() => { cleanups[at]?.(); cleanups[at] = effect(); });
      }
    },
  };
  return {
    render() {
      index = 0;
      const previous = ui.internals.ReactCurrentDispatcher.current;
      ui.internals.ReactCurrentDispatcher.current = dispatcher;
      try { return ui.Comment(props); }
      finally { ui.internals.ReactCurrentDispatcher.current = previous; }
    },
    runEffects() { effects.splice(0).forEach(effect => effect()); },
    unmount() { cleanups.forEach(cleanup => cleanup?.()); },
  };
}

const flushPromises = async () => { for (let index = 0; index < 6; index++) await Promise.resolve(); };

test("a late save response cannot erase a newer draft after closing and reopening the same section", async () => {
  const props = { projectId: "project.comment-reopen", target };
  const key = conversationDraftKey(props.projectId, target, "section-comment");
  const previousLoad = ui.api.reportSectionComment, previousSave = ui.api.saveReportSectionComment;
  let complete;
  ui.api.reportSectionComment = async () => ({ comment: null });
  ui.api.saveReportSectionComment = () => new Promise(resolve => { complete = resolve; });
  const first = commentInstance(props), reopened = commentInstance(props);
  try {
    first.render(); first.runEffects(); await flushPromises();
    walk(first.render()).find(node => node.type === "textarea").props.onChange({ target: { value: "Submitted comment" } });
    walk(first.render()).find(node => node.type === "form").props.onSubmit({ preventDefault() {} });
    assert.equal(typeof complete, "function");
    first.unmount();

    reopened.render(); reopened.runEffects(); await flushPromises();
    walk(reopened.render()).find(node => node.type === "textarea").props.onChange({ target: { value: "Newer unsaved comment" } });
    assert.equal(ui.readConversationDraft(key)?.text, "Newer unsaved comment");
    complete({ comment: { note: "Submitted comment", revision: 1 } });
    await flushPromises();

    assert.equal(ui.readConversationDraft(key)?.text, "Newer unsaved comment");
    assert.equal(walk(reopened.render()).find(node => node.type === "textarea").props.value, "Newer unsaved comment");
  } finally {
    reopened.unmount();
    ui.saveConversationDraft(key, null);
    ui.api.reportSectionComment = previousLoad;
    ui.api.saveReportSectionComment = previousSave;
  }
});
