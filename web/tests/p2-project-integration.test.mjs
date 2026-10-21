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
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-p2-project-"));
const bundle = path.join(directory, "integration.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `export {default as React} from 'react'; export {renderToStaticMarkup} from 'react-dom/server'; export {api} from '${src}/api.js'; export {default as ProjectView} from '${src}/components/ProjectView.jsx'; export {default as LaunchRun} from '${src}/components/LaunchRun.jsx'; export {default as Methods} from '${src}/components/MethodProposals.jsx'; export {default as Issues} from '${src}/components/IssuesCard.jsx'; export {default as Conversation} from '${src}/components/AssumptionConversations.jsx'; export {default as Progress} from '${src}/components/ResearchProgress.jsx'; export {default as Dialogue} from '${src}/components/ResearcherDialogue.jsx'; export {default as Report} from '${src}/components/TechnicalReportReading.jsx'; export {default as FurtherWork} from '${src}/components/FurtherWorkCard.jsx'; export {default as ResearcherPause} from '${src}/components/ResearcherPause.jsx';`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);

function find(element, type) {
  if (Array.isArray(element)) return element.map(item => find(item, type)).find(Boolean);
  if (!element || typeof element !== "object") return null;
  return element.type === type ? element : find(element.props?.children, type);
}

// Exercise ProjectView's real selection callbacks without mounting unrelated
// readers. State persists across render calls; only data-loading effects run.
function hookHarness() {
  const slots = []; const pending = []; const cleanup = []; let cursor = 0;
  const internals = ui.React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED;
  const dispatcher = {
    useState(initial) {
      const index = cursor++;
      if (!Object.hasOwn(slots, index)) slots[index] = typeof initial === "function" ? initial() : initial;
      return [slots[index], value => { slots[index] = typeof value === "function" ? value(slots[index]) : value; }];
    },
    useRef(initial) { const index = cursor++; return slots[index] ||= { current: initial }; },
    useEffect(effect, dependencies) {
      const index = cursor++; const previous = slots[index];
      if (!previous || dependencies.some((value, offset) => value !== previous[offset])) pending.push(effect);
      slots[index] = dependencies;
    },
    useLayoutEffect() { cursor++; },
  };
  return {
    render(props) {
      cursor = 0; const previous = internals.ReactCurrentDispatcher.current;
      internals.ReactCurrentDispatcher.current = dispatcher;
      try { return ui.ProjectView(props); } finally { internals.ReactCurrentDispatcher.current = previous; }
    },
    async load() { for (const effect of pending.splice(0)) { const end = effect(); if (typeof end === "function") cleanup.push(end); } await new Promise(setImmediate); },
    close() { cleanup.forEach(end => end()); },
  };
}

const methodA = { method_id: "method.a", branch_id: "method.a", title: "Navigation model A", version: 1, identity: { stable_id: "method.a", version: 1, definition_sha256: "a".repeat(64) } };
const methodB = { method_id: "method.b", branch_id: "method.b", title: "Selected model B", identity: { stable_id: "method.b", version: 3, definition_sha256: "b".repeat(64) } };
const target = { kind: "phase_issue", branch: "trunk", phase: "P2", family: "theory_review", generation_id: "review.b", sha256: "c".repeat(64), run_id: "run.b", package_id: "package.b", object_id: "finding.b", entry_pointer: "/assessments/0/findings/0", label: "Support for model B" };

async function projectFixture(branch, action, { corrections = [], runs = [], phase = "P2" } = {}) {
  const originals = { api: { ...ui.api }, window: globalThis.window, document: globalThis.document };
  const harness = hookHarness(); const elements = new Map(); let starts = 0;
  globalThis.window = { addEventListener() {}, removeEventListener() {}, matchMedia: () => ({ matches: true }) };
  globalThis.document = { hidden: false, addEventListener() {}, removeEventListener() {}, getElementById: id => elements.get(id) };
  Object.assign(ui.api, {
    project: async () => ({ project: { name: "Integration project" }, workflow_capabilities: { researcher_dialogue: true } }),
    branches: async () => ({ branches: [] }), listRuns: async () => ({ runs }), run: async (_projectId, runId) => runs.find(run => run.run_id === runId),
    artifacts: async () => ({}), decisionsPending: async () => ({ attention: [], researcher_answers: [], runs_needing_correction: corrections }),
    readiness: async () => ({}), records: async () => ({ records: [] }),
    assessments: async () => ({ assessments: [] }), methods: async () => ({ methods: [methodA, methodB], diagnostics: [] }),
    startRun: async () => { starts++; throw new Error("This inspection must not start research."); },
  });
  const navigations = [];
  const props = { projectId: "project.integration", context: { phase, branch }, onContextChange(next) { navigations.push(next); } };
  const render = () => harness.render(props);
  try {
    render(); await harness.load();
    await action({ render, elements, navigations, starts: () => starts });
  } finally {
    harness.close(); Object.assign(ui.api, originals.api);
    if (originals.window === undefined) delete globalThis.window; else globalThis.window = originals.window;
    if (originals.document === undefined) delete globalThis.document; else globalThis.document = originals.document;
  }
}

test("P2 decisions and moved team findings discuss the selected model with its exact source", async () => {
  for (const branch of ["trunk", "method.a"]) await projectFixture(branch, async ({ render, starts }) => {
    const selected = { method: methodB, methodId: methodB.method_id, methodBranch: methodB.branch_id, catalogMethod: methodB };
    const reader = find(render(), ui.Methods);
    const decisions = reader.props.issues(selected);
    const teamWork = find(reader.props.furtherWork(selected).props.workDetails, ui.Issues);
    for (const surface of [decisions, teamWork]) {
      surface.props.onExplain(target);
      const discussion = find(render(), ui.Conversation);
      assert.equal(discussion.props.target.methodLabel, methodB.title);
      assert.equal(discussion.props.target.methodVersion, 3);
      assert.equal(discussion.props.target.assessmentPurpose, "model_dialogue");
      for (const [field, value] of Object.entries(target)) assert.equal(discussion.props.target[field], value, field);
      surface.props.onExplain({ ...target, assessmentPurpose: "issue_suggestions", researcherNoteDraft: "My draft for model B" });
      const suggestions = find(render(), ui.Conversation);
      assert.equal(suggestions.props.target.assessmentPurpose, "issue_suggestions");
      assert.equal(suggestions.props.target.methodLabel, methodB.title);
      assert.equal(suggestions.props.target.researcherNoteDraft, "My draft for model B");
    }
    assert.equal(starts(), 0);
  });
});

test("P2 empty work is exposed and activity recovery opens and focuses the moved correction", async () => {
  await projectFixture("trunk", async ({ render, elements, starts }) => {
    const tree = render(); const reader = find(tree, ui.Methods);
    assert.equal(reader.props.furtherWork({ emptyState: true }).props.defaultOpen, true);
    assert.equal(reader.props.furtherWork({ emptyState: false }).props.defaultOpen, false);
    const effects = []; const card = { open: false };
    elements.set("p2-additional-work", card);
    elements.set("p2-recovery", { scrollIntoView: options => effects.push(["scroll", options]), focus: options => effects.push(["focus", options]) });
    find(tree, ui.Progress).props.onShowIssues();
    assert.equal(card.open, true);
    assert.deepEqual(effects, [["scroll", { behavior: "instant", block: "start" }], ["focus", { preventScroll: true }]]);
    assert.equal(starts(), 0);
  }, { corrections: [{ run_id: "run.failed", branch_id: "trunk", phase: "P2", mode: "p2.full_catalog" }] });
});

test("P3 current activity and decisions omit a superseded correction while failed history remains readable", async () => {
  const failed = { run_id: "run.old-failure", branch_id: "method.a", phase: "P3", mode: "p3.theory_establishment", state: "failed", created_at: "2026-10-16T13:37:07.357Z" };
  const fresh = { ...failed, run_id: "run.fresh-revision", mode: "p3.theory_revision", state: "running", created_at: "2026-10-20T03:00:44.290Z" };
  for (const superseded of [true, false]) await projectFixture("method.a", async ({ render, starts }) => {
    const tree = render(); const progress = find(tree, ui.Progress); const dialogue = find(tree, ui.Dialogue);
    assert.equal(progress.props.correctionCount, superseded ? 0 : 1);
    assert.equal(dialogue.props.correctionCount, superseded ? 0 : 1);
    const activity = ui.renderToStaticMarkup(progress);
    assert.match(activity, superseded ? /latest update: Running/ : /latest update: Failed/);
    if (superseded) assert.doesNotMatch(activity, /work correction/);
    else assert.match(activity, /1 work correction/);
    const history = ui.renderToStaticMarkup(find(tree, "tbody"));
    assert.match(history, /Establish theory/);
    assert.match(history, /Failed/);
    assert.match(history, /ProjectView:3:run.old-failure/);
    assert.match(history, /Open history/);
    assert.equal(starts(), 0);
  }, { phase: "P3", corrections: [failed], runs: superseded ? [fresh, failed] : [failed] });
});

test("P5 omits general problem discussion while report sections keep their exact discussion target", async () => {
  for (const branch of ["trunk", "method.a"]) await projectFixture(branch, async ({ render, starts }) => {
    assert.ok(!find(render(), ui.Dialogue));
    if (branch !== "trunk") {
      const reader = find(render(), ui.Report);
      assert.ok(reader);
      assert.ok(find(render(), ui.FurtherWork));
      const section = { kind: "report_section", branch, phase: "P5", family: "technical_report", generation_id: "report.current", sha256: "d".repeat(64), object_id: "numerical_analysis", label: "Numerical results", assessmentPurpose: "model_dialogue" };
      reader.props.onDiscussSection(section);
      const conversation = find(render(), ui.Conversation);
      assert.deepEqual(conversation.props.target, { ...section, methodLabel: methodA.title, methodVersion: methodA.version });
    }
    assert.equal(starts(), 0);
  }, { phase: "P5" });
});

test("P5 activity opens Next revision for retained execution recovery and an active researcher pause", async () => {
  const failed = { run_id: "run.p5.failed", branch_id: "method.a", phase: "P5", mode: "p5.assembly", state: "failed", created_at: "2026-10-20T03:00:00Z" };
  const paused = { ...failed, run_id: "run.p5.paused", state: "awaiting_user", researcher_pause: { pending_request: { request_id: "request.report", revision: 1, question: "Which retained analysis should the report emphasize?" } } };
  for (const run of [failed, paused]) await projectFixture("method.a", async ({ render, elements, starts }) => {
    const tree = render(); const nextRevision = find(tree, ui.FurtherWork);
    assert.ok(!find(tree, ui.Dialogue));
    const recovery = find(nextRevision.props.children, "div");
    assert.equal(recovery.props.id, "p5-recovery");
    if (run === paused) assert.equal(find(recovery, ui.ResearcherPause).props.run, run);
    else assert.match(ui.renderToStaticMarkup(recovery), /Work that could not be completed|Review what happened/);
    const effects = []; const card = { open: false };
    elements.set("p5-additional-work", card);
    elements.set("p5-recovery", { scrollIntoView: options => effects.push(["scroll", options]), focus: options => effects.push(["focus", options]) });
    find(tree, ui.Progress).props.onShowIssues();
    assert.equal(card.open, true);
    assert.deepEqual(effects, [["scroll", { behavior: "instant", block: "start" }], ["focus", { preventScroll: true }]]);
    assert.equal(starts(), 0);
  }, { phase: "P5", corrections: run === failed ? [failed] : [], runs: [run] });
});


test("P2 Run this Method prepares the exact selected branch without starting work or replacing the reader", async () => {
  for (const phase of ["P3", "P4"]) await projectFixture("method.a", async ({ render, navigations, starts }) => {
    const activations = [];
    ui.api.activateMethod = async (...args) => { activations.push(args); return { branch_id: "branch.selected.b" }; };
    await find(render(), ui.Methods).props.onContinue(methodB, phase, { prepareRun: true });
    const dialog = find(render(), ui.LaunchRun);
    assert.ok(dialog);
    assert.equal(dialog.props.request.branch, "branch.selected.b");
    assert.equal(dialog.props.request.phase, phase);
    assert.equal(dialog.props.request.methodLabel, "Selected model B \u00b7 Version 3");
    assert.deepEqual(activations, [["project.integration", "method.b", methodB.identity]]);
    assert.deepEqual(navigations, []);
    assert.equal(starts(), 0);
    dialog.props.onClose();
    assert.ok(!find(render(), ui.LaunchRun));
    assert.ok(find(render(), ui.Methods));
    // The history-only route keeps its browsing behavior.
    await find(render(), ui.Methods).props.onContinue(methodB, phase);
    assert.deepEqual(navigations, [{ branch: "branch.selected.b", phase }]);
    assert.ok(!find(render(), ui.LaunchRun));
    assert.equal(starts(), 0);
  });
});
