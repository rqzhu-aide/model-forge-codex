import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { catalogSelectionKey, proposalKey } from "../src/methodWorkspace.js";
import { issueCardEntries, issueDisplayState } from "../src/phaseUiState.js";

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
  return element.type === type ? element : find(element.props?.children, type) || find(element.props?.furtherWork, type) || find(element.props?.issues, type);
}

function findClass(element, className) {
  if (Array.isArray(element)) return element.map(item => findClass(item, className)).find(Boolean);
  if (!element || typeof element !== "object") return null;
  return element.props?.className === className ? element : findClass(element.props?.children, className);
}

// Exercise ProjectView's real selection callbacks without mounting unrelated
// readers. State persists across render calls; only data-loading effects run.
function hookHarness({ layout = false } = {}) {
  const slots = []; const pending = []; const layouts = []; const cleanup = []; let cursor = 0;
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
    useLayoutEffect(effect, dependencies) {
      const index = cursor++; const previous = slots[index];
      if (layout && (!previous || dependencies.some((value, offset) => value !== previous[offset]))) layouts.push(effect);
      slots[index] = dependencies;
    },
    useId() { const index = cursor++; return slots[index] ||= `fixture-${index}`; },
  };
  return {
    render(props, component = ui.ProjectView) {
      cursor = 0; const previous = internals.ReactCurrentDispatcher.current;
      internals.ReactCurrentDispatcher.current = dispatcher;
      try { return component(props); } finally { internals.ReactCurrentDispatcher.current = previous; }
    },
    settleLayout() { for (const effect of layouts.splice(0)) { const end = effect(); if (typeof end === "function") cleanup.push(end); } },
    async load() { for (const effect of pending.splice(0)) { const end = effect(); if (typeof end === "function") cleanup.push(end); } await new Promise(setImmediate); },
    close() { cleanup.forEach(end => end()); },
  };
}

const methodA = { method_id: "method.a", branch_id: "method.a", title: "Navigation model A", version: 1, identity: { stable_id: "method.a", version: 1, definition_sha256: "a".repeat(64) } };
const methodB = { method_id: "method.b", branch_id: "method.b", title: "Selected model B", identity: { stable_id: "method.b", version: 3, definition_sha256: "b".repeat(64) } };
const target = { kind: "phase_issue", branch: "trunk", phase: "P2", family: "theory_review", generation_id: "review.b", sha256: "c".repeat(64), run_id: "run.b", package_id: "package.b", object_id: "finding.b", entry_pointer: "/assessments/0/findings/0", label: "Support for model B" };

async function projectFixture(branch, action, { corrections = [], runs = [], branches = [], phase = "P2", attention = [], answers = [], artifacts = {}, awaiting = runs.filter(run => run.state === "awaiting_user"), p2ProposalKey, layout = false } = {}) {
  const originals = { api: { ...ui.api }, window: globalThis.window, document: globalThis.document,
    requestAnimationFrame: globalThis.requestAnimationFrame, cancelAnimationFrame: globalThis.cancelAnimationFrame, MutationObserver: globalThis.MutationObserver, setTimeout: globalThis.setTimeout };
  const harness = hookHarness({ layout }); const elements = new Map(); let starts = 0;
  globalThis.window = { addEventListener() {}, removeEventListener() {}, matchMedia: () => ({ matches: true }) };
  globalThis.document = { hidden: false, addEventListener() {}, removeEventListener() {}, getElementById: id => elements.get(id) };
  Object.assign(ui.api, {
    project: async () => ({ project: { name: "Integration project" }, workflow_capabilities: { researcher_dialogue: true } }),
    branches: async () => ({ branches }), listRuns: async () => ({ runs }), run: async (_projectId, runId) => runs.find(run => run.run_id === runId),
    artifacts: async () => artifacts, decisionsPending: async () => ({ attention, researcher_answers: answers, runs_needing_correction: corrections, runs_awaiting_direction: awaiting }),
    readiness: async () => ({}), records: async () => ({ records: [] }),
    assessments: async () => ({ assessments: [] }), methods: async () => ({ methods: [methodA, methodB], diagnostics: [] }),
    startRun: async () => { starts++; throw new Error("This inspection must not start research."); },
  });
  const navigations = [];
  const props = { projectId: "project.integration", context: { phase, branch, p2ProposalKey }, onContextChange(next) { navigations.push(next); } };
  const render = () => harness.render(props);
  try {
    render(); await harness.load();
    await action({ render, elements, navigations, props, load: harness.load, settleLayout: harness.settleLayout, starts: () => starts });
  } finally {
    harness.close(); Object.assign(ui.api, originals.api);
    if (originals.window === undefined) delete globalThis.window; else globalThis.window = originals.window;
    if (originals.document === undefined) delete globalThis.document; else globalThis.document = originals.document;
    for (const name of ["requestAnimationFrame", "cancelAnimationFrame", "MutationObserver", "setTimeout"]) {
      if (originals[name] === undefined) delete globalThis[name]; else globalThis[name] = originals[name];
    }
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

const responseCount = (card) => issueCardEntries(card.props).entries.filter(issue => issueDisplayState(issue).state === "response").length;
const nextButton = (tree) => findClass(tree, "project-next").props.children.at(-1);
// These wrappers have no hooks. Keep the actual ExploreMethod hooks mounted
// while ProjectView changes the selected model through its public props.
function exploreElement(reader) {
  const direct = reader.type(reader.props);
  return direct.type(direct.props).props.children;
}

test("Next counts exact P2 questions and changes an already mounted reader to the named model", async () => {
  const exact = { attention_id: "question.exact.b", kind: "researcher_decision", phase: "P2", branch: "trunk", disposition: "open",
    question: "Which regime should model B target?", generation_ref: { phase: "P2", branch: "trunk", family: "attention_items", generation_id: "attention.exact", sha256: "f".repeat(64), run_id: "run.exact", package_id: "package.exact" },
    scope: { kind: "model", branch: "trunk", model_ref: methodB.identity } };
  const legacy = { ...exact, attention_id: "question.legacy.b", scope: undefined, affected_record_ids: ["method.b"] };
  for (const attention of [[exact], [legacy]]) await projectFixture("method.a", async ({ render, navigations, props, starts }) => {
    const harness = hookHarness({ layout: true });
    try {
      const before = find(render(), ui.Methods);
      let explore = exploreElement(before);
      harness.render(explore.props, explore.type); harness.settleLayout();
      const initial = harness.render(explore.props, explore.type);
      assert.equal(responseCount(find(initial, ui.Dialogue)), 0);
      assert.match(ui.renderToStaticMarkup(findClass(render(), "project-resume")), /1 question.*Selected model B.*Version 3/);
      nextButton(render()).props.onClick();
      assert.deepEqual(navigations, [{ phase: "P2", p2ProposalKey: catalogSelectionKey(methodB) }]);
      props.context = { ...props.context, ...navigations[0] };
      const after = find(render(), ui.Methods);
      assert.equal(after.key, before.key);
      explore = exploreElement(after);
      harness.render(explore.props, explore.type); harness.settleLayout();
      const selected = harness.render(explore.props, explore.type);
      const card = find(selected, ui.Dialogue);
      assert.equal(card.props.methodId, methodB.method_id);
      assert.deepEqual(card.props.modelRef, methodB.identity);
      assert.equal(responseCount(card), 1);
      assert.equal(starts(), 0);
    } finally { harness.close(); }
  }, { attention, p2ProposalKey: catalogSelectionKey(methodA) });
});

test("Next opens the exact historical P2 proposal instead of its current successor", async () => {
  const oldIdentity = { ...methodB.identity, version: 2, definition_sha256: "c".repeat(64) };
  const old = { phase: "P2", branch: "trunk", proposal_id: "proposal.old", generation_ref: { run_id: "run.old" },
    is_current_package: false, method: { title: "Earlier model B", identity: oldIdentity } };
  const current = { ...old, proposal_id: "proposal.current", generation_ref: { run_id: "run.current" }, is_current_package: true, method: { title: methodB.title, identity: methodB.identity } };
  const attention = [{ attention_id: "question.old", kind: "researcher_decision", phase: "P2", branch: "trunk", disposition: "open", question: "Which earlier target?",
    generation_ref: { ...old.generation_ref, phase: "P2", branch: "trunk", family: "attention_items", generation_id: "attention.old", sha256: "f".repeat(64), package_id: "package.old" },
    scope: { kind: "model", branch: "trunk", model_ref: oldIdentity } }];
  await projectFixture("method.a", async ({ render, navigations, props, starts }) => {
    assert.match(ui.renderToStaticMarkup(findClass(render(), "project-resume")), /Earlier model B.*Version 2/);
    nextButton(render()).props.onClick();
    assert.deepEqual(navigations, [{ phase: "P2", p2ProposalKey: proposalKey(old) }]);
    props.context = { ...props.context, ...navigations[0] };
    const reader = find(render(), ui.Methods);
    assert.equal(reader.props.initialPick, proposalKey(old));
    const card = reader.props.issues({ proposal: old, method: old.method, methodId: methodB.method_id, methodBranch: methodB.branch_id, catalogMethod: null });
    assert.equal(responseCount(card), 1);
    assert.equal(starts(), 0);
  }, { attention, artifacts: { method_proposals: [current, old] }, p2ProposalKey: proposalKey(current) });
});

test("Next finds project-wide paused work and routes to that method even within the same phase", async () => {
  for (const phase of ["P3", "P4", "P5"]) {
    const paused = { run_id: `run.paused.b.${phase}`, phase, branch_id: "method.b", state: "awaiting_user",
      researcher_pause: { pending_request: { request_id: "request.b", revision: 1, question: "Which limit should B target?" } },
      ...(phase === "P4" ? { p4_progress: { pause_request: { request_id: "request.b", revision: 1, question: "Which limit should B target?" } } } : {}) };
    // The pending endpoint is the project-wide source even if a run list
    // refresh does not yet include the newly paused run.
    for (const runs of [[], [paused]]) await projectFixture("method.a", async ({ render, navigations, props, load, starts }) => {
      const html = ui.renderToStaticMarkup(findClass(render(), "project-resume"));
      assert.match(html, /Selected model B is waiting for your direction/);
      assert.doesNotMatch(html, /Nothing needs your decision/);
      nextButton(render()).props.onClick();
      assert.deepEqual(navigations, [{ phase, branch: "method.b" }]);
      props.context = { ...props.context, ...navigations[0] };
      render(); await load();
      const destination = render();
      if (phase === "P5") assert.equal(find(find(destination, ui.FurtherWork).props.children, ui.ResearcherPause).props.run, paused);
      else {
        const dialogue = find(destination, ui.Dialogue);
        assert.equal(dialogue.props.activePause, true);
        if (phase === "P3") assert.equal(dialogue.props.pause.props.run, paused);
      }
      assert.equal(starts(), 0);
    }, { phase, runs, awaiting: [paused] });
  }
});

test("Next uses the default P2 selection and counts shared questions in its current exact card", async () => {
  const attention = [{ attention_id: "shared", kind: "researcher_decision", phase: "P2", branch: "trunk", disposition: "open", question: "Which shared objective?" },
    { attention_id: "model-a", kind: "researcher_decision", phase: "P2", branch: "trunk", disposition: "open", question: "Which A target?", affected_record_ids: ["method.a"] },
    { attention_id: "p1", kind: "researcher_decision", phase: "P1", branch: "trunk", disposition: "open", question: "Which setting?" }];
  for (const p2ProposalKey of [undefined, "unavailable:proposal"]) await projectFixture("method.b", async ({ render }) => {
    const tree = render();
    assert.match(ui.renderToStaticMarkup(findClass(tree, "project-next")), /2 questions.*need your response in this phase/);
    const reader = find(tree, ui.Methods);
    assert.equal(responseCount(reader.props.issues({ method: methodA, methodId: methodA.method_id, methodBranch: methodA.branch_id, catalogMethod: methodA })), 2);
  }, { attention, p2ProposalKey });
});

test("a same-phase P2 Next arrival focuses the new card after its selection layout settles", async () => {
  const attention = [{ attention_id: "question.b", kind: "researcher_decision", phase: "P2", branch: "trunk", disposition: "open", question: "Which B target?", affected_record_ids: ["method.b"] }];
  await projectFixture("method.a", async ({ render, props, navigations, settleLayout }) => {
    const frames = []; const effects = []; const child = hookHarness({ layout: true }); let selectedId;
    try {
      globalThis.requestAnimationFrame = callback => { frames.push(callback); return frames.length; };
      globalThis.cancelAnimationFrame = () => {};
      globalThis.setTimeout = () => 0;
      const tree = render(); settleLayout();
      let explore = exploreElement(find(tree, ui.Methods));
      child.render(explore.props, explore.type); child.settleLayout();
      selectedId = find(child.render(explore.props, explore.type), ui.Dialogue).props.methodId;
      const target = { isConnected: true, dataset: {}, hasAttribute: () => true, getBoundingClientRect: () => ({ top: 16 }),
        focus: () => effects.push(["focus", selectedId]), addEventListener() {} };
      const root = { querySelector: selector => selector === "#phase-issues" ? target : null }; target.parentElement = root;
      tree.ref.current = root; window.scrollY = 0;
      nextButton(tree).props.onClick();
      props.context = { ...props.context, ...navigations[0] };
      const changed = render(); settleLayout();
      assert.deepEqual(effects, []);
      explore = exploreElement(find(changed, ui.Methods));
      child.render(explore.props, explore.type); child.settleLayout();
      selectedId = find(child.render(explore.props, explore.type), ui.Dialogue).props.methodId;
      frames.splice(0).forEach(callback => callback());
      assert.deepEqual(effects, [["focus", "method.b"]]);
      assert.equal(target.dataset.arrival, "true");
    } finally { child.close(); }
  }, { attention, p2ProposalKey: catalogSelectionKey(methodA), layout: true });
});

test("a cross-method pause arrival waits for reader restoration and opens P5 recovery before focus", async () => {
  const paused = { run_id: "run.paused.b", phase: "P5", branch_id: "method.b", state: "awaiting_user",
    researcher_pause: { pending_request: { request_id: "request.b", revision: 1, question: "Which report target?" } } };
  await projectFixture("method.a", async ({ render, props, navigations, load, settleLayout }) => {
    const frames = []; const effects = []; let contentPending = true; let observer;
    globalThis.requestAnimationFrame = callback => { frames.push(callback); return frames.length; };
    globalThis.cancelAnimationFrame = () => {};
    globalThis.setTimeout = () => 0;
    globalThis.MutationObserver = class { constructor(callback) { observer = callback; } observe() {} disconnect() {} };
    const initial = render(); settleLayout();
    nextButton(initial).props.onClick();
    props.context = { ...props.context, ...navigations[0] };
    render(); settleLayout(); await load();
    const destination = render();
    const disclosure = { tagName: "DETAILS", open: false };
    const target = { isConnected: true, parentElement: disclosure, dataset: {}, hasAttribute: () => true, getBoundingClientRect: () => ({ top: 16 }),
      focus: () => effects.push(["focus", disclosure.open]), addEventListener() {} };
    const root = { querySelectorAll: () => [disclosure], querySelector: selector => selector === '[data-reading-pending="true"]' ? contentPending ? {} : null : selector === "#p5-recovery" ? target : null };
    disclosure.parentElement = root; destination.ref.current = root;
    window.scrollY = 0; window.scrollTo = options => effects.push(["scroll", options.top]);
    settleLayout();
    assert.equal(frames.length, 0); assert.equal(disclosure.open, false);
    contentPending = false; observer();
    frames.splice(0).forEach(callback => callback());
    assert.deepEqual(effects, [["scroll", 0], ["focus", true]]);
    assert.equal(target.dataset.arrival, "true");
  }, { phase: "P5", awaiting: [paused], layout: true });
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

test("one preparation card follows scientific history in its exact phase and method", async () => {
  for (const phase of ["P1", "P2", "P3", "P4", "P5"]) {
    const branch = ["P1", "P2"].includes(phase) ? "trunk" : "method.a";
    const run = { run_id: "run.lifecycle", branch_id: branch, phase, state: "published" };
    const cases = [
      { expected: false, runs: [] },
      { expected: false, runs: [{ ...run, branch_id: "method.b" }] },
      { expected: false, runs: [{ ...run, intent: "assessment" }] },
      { expected: false, runs: [{ ...run, assessment_purpose: "model_dialogue" }] },
      { expected: true, runs: [run] },
      { expected: true, runs: [{ ...run, state: "failed" }] },
      { expected: true, runs: [{ ...run, state: "running" }] },
      { expected: true, runs: [{ ...run, state: "awaiting_user" }] },
      { expected: true, runs: [], branches: [{ branch_id: branch, phases: { [phase.toLowerCase()]: ["retained.output"] } }] },
    ];
    for (const scenario of cases) await projectFixture("method.a", async ({ render, starts }) => {
      const tree = render();
      const card = find(tree, ui.FurtherWork) || find(tree, ui.Methods)?.props.furtherWork({});
      assert.ok(card, `${phase} preparation exists`);
      assert.equal(card.props.hasRun, scenario.expected, `${phase}: ${JSON.stringify(scenario)}`);
      assert.equal(starts(), 0);
    }, { ...scenario, phase });
  }
});
