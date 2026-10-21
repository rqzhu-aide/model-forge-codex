import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { assumptionTarget as target, assumptionConversations as conversations } from "./fixtures/assumption-conversations.mjs";
import { assumptionSource, conversationDraftKey, conversationsForTarget, isEarlierConversation, readConversationDraft, saveConversationDraft } from "../src/assumptionConversations.js";
import { conversationSourceReference } from "../src/conversationSources.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-assumption-render-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({
  stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Theory from '${src}/components/TheoryWorkbench.jsx'; import Conversations,{ConversationTranscript} from '${src}/components/AssumptionConversations.jsx'; import Assessments from '${src}/components/Assessments.jsx'; const render = Component => props => renderToStaticMarkup(React.createElement(Component, props)); export const theory=render(Theory); export const conversations=render(Conversations); export const transcript=render(ConversationTranscript); export const assessments=render(Assessments);`, resolveDir: src },
  outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" },
  alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent",
});
const render = require(bundle);
fs.unlinkSync(bundle); fs.rmdirSync(directory);
const noop = () => {};
const map = { branch: target.branch, phase: "P3", theory_generation_ref: assumptionSource(target), assumptions: [{ assumption_id: target.object_id, text: target.statement, label: target.label }], claims: [{ statement_id: "statement.bound", label: "Concentration bound", depends_on: [target.object_id, "assumption.unresolved"], text: "Concentration holds." }] };
const theoryProps = { branch: target.branch, selected: target.object_id, claimMaps: [map], onSelect: noop, onRequest: noop, onSource: noop, onAssumptionConversation: noop };

test("only a registered source-linked assumption has the conversation icon, with isolated history count", () => {
  const html = render.theory({ ...theoryProps, conversations });
  assert.match(html, /aria-label="Explain this assumption\. View assumption conversations \(2\)"/);
  assert.match(html, /aria-haspopup="dialog"/);
  assert.doesNotMatch(html, /Why is this assumption needed|Could this assumption be weakened|conversation-transcript/);
  assert.match(render.theory(theoryProps), /aria-label="Explain this assumption"/);
  for (const selected of ["statement.bound", "assumption.unresolved"]) assert.doesNotMatch(render.theory({ ...theoryProps, selected }), /assumption-conversation-icon/);
  const unlinked = render.theory({ ...theoryProps, claimMaps: [{ ...map, theory_generation_ref: null }] });
  assert.doesNotMatch(unlinked, /assumption-conversation-icon/);
  assert.match(unlinked, /exact linked theory source/);
  const glossaryOnly = render.theory({ ...theoryProps, claimMaps: [{ ...map, assumptions: [] }], glossaries: [{ branch: target.branch, phase: "P3", glossary: { [target.object_id]: { kind: "assumption", label: target.label } } }] });
  assert.doesNotMatch(glossaryOnly, /assumption-conversation-icon/);
});

test("history matching excludes other branches, record families, assumption IDs and ordinary assessments", () => {
  const foreign = [
    { ...conversations[0], target: { ...target, branch: "method.other" } },
    { ...conversations[0], target: { ...target, family: "complete_theory" } },
    { ...conversations[0], target: { ...target, object_id: "assumption.other" } },
    { ...conversations[0], target: { ...target, kind: "statement" } },
    { ...conversations[0], assessment_purpose: "assessment" },
  ];
  assert.deepEqual(conversationsForTarget([...conversations, ...foreign], target).map((item) => item.assessment_id), ["conversation.current", "conversation.earlier"]);
  assert.equal(isEarlierConversation(conversations[0], target), false);
  assert.equal(isEarlierConversation(conversations[1], target), true);
  assert.deepEqual(conversationsForTarget(conversations, { ...target, sha256: null }), []);
  assert.equal(assumptionSource(target).statement, undefined);
});

test("dialog has a labeled question form, exact source, separate histories and enabled Close", () => {
  const html = render.conversations({ projectId: "project.a", target, conversations, onClose: noop, onSource: noop });
  for (const text of ["About this assumption", "Your question", "Open exact assumption source", "This source version", "Earlier source versions", "New conversation", "What happens without this assumption?", "Could this assumption be weakened?"]) assert.ok(html.includes(text), text);
  assert.match(html, /class="katex/);
  assert.match(html, /aria-label="Close dialog"[^>]*>[\s\S]*?<\/svg>Close<\/button>/);
  assert.doesNotMatch(html, /aria-label="Close dialog"[^>]*disabled/);
  assert.match(html, /<label for="[^"]+">Your question<\/label>/);
  assert.match(html, /<button(?=[^>]*disabled="")(?=[^>]*type="submit")(?=[^>]*data-action="ask")[^>]*><svg[^>]*aria-hidden="true"[\s\S]*?<\/svg>Discuss<\/button>/);
});

test("pending and failed first questions render durably alongside previous successful answers", () => {
  const first = conversations[0].turns[0];
  const pending = render.transcript({ conversation: { ...conversations[0], turns: [first, { run_id: "run.followup", instructions: "Give me a failure case.", state: "running" }] }, onSource: noop });
  assert.match(pending, /sufficient condition/);
  assert.match(pending, /Give me a failure case/);
  assert.match(pending, /role="status">Answering/);
  assert.match(pending, /Sources used/);
  assert.match(pending, /class="katex/);
  const failed = render.transcript({ conversation: { ...conversations[0], turns: [{ run_id: "run.failed", instructions: "Why is this needed?", state: "failed", terminal_reason: "The service restarted." }] }, onRetry: noop });
  assert.match(failed, /Why is this needed/);
  assert.match(failed, /role="alert"/);
  assert.match(failed, /The service restarted/);
  assert.match(failed, /Retry question/);
  const retried = render.transcript({ conversation: { ...conversations[0], turns: [{ run_id: "run.failed", instructions: "Original question", state: "failed" }, { ...first, retry_run_id: "run.failed" }] }, onSource: noop });
  assert.match(retried, /A later attempt is shown below/);
  assert.doesNotMatch(retried, /Retry question/);
});

test("explanations never duplicate into Focused assessments while legacy assessments remain", () => {
  assert.equal(render.assessments({ projectId: "project.a", assessments: conversations }), "");
  const html = render.assessments({ projectId: "project.a", assessments: [...conversations, { assessment_id: "legacy", title: "Existing focused review", target, messages: [] }], onSource: noop });
  assert.match(html, /Existing focused review/);
  assert.doesNotMatch(html, /Why is this assumption needed|Could this assumption be weakened/);
});

test("authored follow-up questions retain their reason and scope even when omitted from answer prose", () => {
  const question = { question: "How does a visit enter the sample?", why_it_matters: "Selection changes the population interpretation.", consequence_markdown: "An unknown mechanism requires a conditional interpretation.", responsible_role: "data_analyst", scope: { kind: "project" } };
  const turn = { ...conversations[0].turns[0], assessment_markdown: "The mechanism remains unresolved.", followup_questions: [question] };
  const html = render.transcript({ conversation: { ...conversations[0], turns: [turn] } });
  for (const text of [question.question, question.why_it_matters, question.consequence_markdown, "Data Analyst", "Across models", "leave the information unknown"]) assert.ok(html.includes(text), text);
  assert.doesNotMatch(html, /type="submit"/);
});

const replyRun = "run.reply";
const inputPath = `C:/Users/researcher/ModelForge/projects/project.a/runs/${replyRun}/inputs/${target.branch}/p3/${target.family}/${target.generation_id}.json`;
const linkedEvidence = { family: target.family, generation_id: target.generation_id, generation_ref: target };
const recordUrl = `/api/v1/projects/project.a/branches/${target.branch}/phases/P3/records/${target.family}/${target.generation_id}`;
const apiEvidence = { ...linkedEvidence, source_url: recordUrl, object_id: "statement.bound" };

test("inline discussion input citations resolve only against exact frozen evidence for their own turn", () => {
  assert.deepEqual(conversationSourceReference(inputPath, replyRun, [linkedEvidence]), target);
  assert.deepEqual(conversationSourceReference(inputPath.replaceAll("/", "\\"), replyRun, [linkedEvidence]), target);
  assert.deepEqual(conversationSourceReference(inputPath, replyRun, [linkedEvidence, { ...linkedEvidence, object_id: "statement.another" }]), target);
  for (const [source, run, evidence] of [
    [inputPath, "run.other", [linkedEvidence]],
    [inputPath.replace("/method.a/", "/method.other/"), replyRun, [linkedEvidence]],
    [inputPath.replace("/p3/", "/p4/"), replyRun, [linkedEvidence]],
    [inputPath.replace("/theory_record/", "/complete_theory/"), replyRun, [linkedEvidence]],
    [inputPath.replace("theory.v2.json", "theory.v1.json"), replyRun, [linkedEvidence]],
    [inputPath.replace("/inputs/", "/outputs/"), replyRun, [linkedEvidence]],
    [inputPath.replace("/projects/", "/../projects/"), replyRun, [linkedEvidence]],
    [inputPath, replyRun, [{ ...linkedEvidence, source_error: "Not uniquely linked." }]],
    [inputPath, replyRun, [{ ...target }]],
    [inputPath, replyRun, [{ ...linkedEvidence, generation_ref: { ...target, sha256: null } }]],
    [inputPath, replyRun, [linkedEvidence, { ...linkedEvidence, generation_ref: { ...target, sha256: "b".repeat(64) } }]],
    ["javascript:alert(1)", replyRun, [linkedEvidence]],
    ["file:///private/patient.csv", replyRun, [linkedEvidence]],
  ]) assert.equal(conversationSourceReference(source, run, evidence), null);
});

test("discussion citations use source-window controls without rendering filesystem URLs or altering mathematics", () => {
  const markdown = `The offer is $A=1$. [Frozen definition](${inputPath}) [Patient file](C:/private/patient.csv) [Primary paper](https://example.com/paper).\n\nThe guarantee remains conditional.`;
  const turn = { run_id: replyRun, instructions: "Explain the offer.", state: "assessed", assessment_markdown: markdown, evidence_refs: [linkedEvidence] };
  const conversation = { ...conversations[0], turns: [turn] };
  const before = JSON.stringify(conversation);
  const html = render.transcript({ conversation, onSource: noop });
  assert.match(html, /<button(?=[^>]*data-action="source")[^>]*>[\s\S]*?Frozen definition<\/button>/);
  assert.match(html, /Patient file \(source unavailable\)/);
  assert.doesNotMatch(html, /C:[/\\]|file:\/\/|\[Frozen definition\]/);
  assert.match(html, /href="https:\/\/example.com\/paper"/);
  assert.match(html, /class="katex/);
  assert.doesNotMatch(html, /katex-error/);
  assert.match(html, /The guarantee remains conditional/);
  assert.match(html, /Sources used/);
  assert.equal(JSON.stringify(conversation), before);
});

test("a follow-up may reuse only a prior input path verified in that same conversation", () => {
  const prior = { run_id: replyRun, evidence_refs: [linkedEvidence] };
  assert.deepEqual(conversationSourceReference(inputPath, "run.followup", [], [prior]), target);
  assert.equal(conversationSourceReference(inputPath, "run.followup", [linkedEvidence], []), null);
  assert.equal(conversationSourceReference(inputPath, "run.followup", [linkedEvidence], [{ ...prior, evidence_refs: [] }]), null);
  assert.equal(conversationSourceReference(inputPath, "run.followup", [linkedEvidence], [{ ...prior, run_id: "run.another-conversation" }]), null);
  const html = render.transcript({ conversation: { ...conversations[0], turns: [
    { ...prior, state: "assessed", instructions: "Original question.", assessment_markdown: "Original answer." },
    { run_id: "run.followup", state: "assessed", instructions: "Explain the same source.", assessment_markdown: `[Prior definition](${inputPath})`, evidence_refs: [] },
  ] }, onSource: noop });
  assert.match(html, /<button(?=[^>]*data-action="source")[^>]*>[\s\S]*?Prior definition<\/button>/);
  assert.doesNotMatch(html, /source unavailable|C:[/\\]/);
});

test("exact projected API citations and known object fragments open source windows without changing web links", () => {
  assert.deepEqual(conversationSourceReference(recordUrl, replyRun, [apiEvidence]), target);
  assert.deepEqual(conversationSourceReference(`${recordUrl}#statement.bound`, replyRun, [apiEvidence]), target);
  for (const source of [`${recordUrl}#statement.unlisted`, `${recordUrl}?download=1`, `${recordUrl}/other`, "/api/v1/account", recordUrl.replace("project.a", "project.other")]) {
    assert.equal(conversationSourceReference(source, replyRun, [apiEvidence]), null);
  }
  assert.equal(conversationSourceReference(recordUrl, replyRun, [{ ...apiEvidence, source_error: "Unavailable." }]), null);
  const turn = { run_id: replyRun, instructions: "Explain.", state: "assessed", evidence_refs: [apiEvidence],
    assessment_markdown: `[Exact definition](${recordUrl}) [Known bound](${recordUrl}#statement.bound) [Unknown target](/api/v1/account) [Web paper](https://example.com/paper).\n\n| Source | Meaning |\n| --- | --- |\n| [Table source](${recordUrl}) | The bound is $x<1$. |` };
  const html = render.transcript({ conversation: { ...conversations[0], turns: [turn] }, onSource: noop });
  for (const label of ["Exact definition", "Known bound", "Table source"]) assert.match(html, new RegExp(`<button(?=[^>]*data-action="source")[^>]*>[\\s\\S]*?${label}<\\/button>`));
  assert.match(html, /Unknown target \(source unavailable\)/);
  assert.doesNotMatch(html, /href="\/api\//);
  assert.match(html, /href="https:\/\/example.com\/paper"/);
  assert.match(html, /class="katex/);
});

test("legacy assistant messages use their own verified citations while researcher text remains verbatim", () => {
  const markdown = `[Frozen definition](${inputPath})`;
  const html = render.transcript({ conversation: { ...conversations[0], turns: [], messages: [
    { role: "user", content: markdown, run_id: replyRun },
    { role: "assistant", content: markdown, run_id: replyRun, evidence_refs: [linkedEvidence] },
  ] }, onSource: noop });
  assert.equal(html.split("data-action=\"source\"").length - 1, 1);
  assert.equal(html.split(inputPath).length - 1, 1);
});

test("session drafts retain text and submission identity and cannot leak across exact targets", () => {
  const stored = new Map();
  const previous = Object.getOwnPropertyDescriptor(globalThis, "sessionStorage");
  Object.defineProperty(globalThis, "sessionStorage", { configurable: true, value: { getItem: (key) => stored.get(key), setItem: (key, value) => stored.set(key, value), removeItem: (key) => stored.delete(key) } });
  try {
    const key = conversationDraftKey("project.a", target, "conversation.current");
    const draft = { text: "My unsent follow-up", idempotencyKey: "same-submission" };
    saveConversationDraft(key, draft);
    assert.deepEqual(readConversationDraft(key), draft);
    for (const other of [conversationDraftKey("project.b", target, "conversation.current"), conversationDraftKey("project.a", { ...target, branch: "method.other" }, "conversation.current"), conversationDraftKey("project.a", { ...target, sha256: "c".repeat(64) }, "conversation.current"), conversationDraftKey("project.a", target, "conversation.other"), conversationDraftKey("project.a", target)]) assert.equal(readConversationDraft(other), null);
    saveConversationDraft(key, null); assert.equal(readConversationDraft(key), null);
  } finally { if (previous) Object.defineProperty(globalThis, "sessionStorage", previous); else delete globalThis.sessionStorage; }
});
