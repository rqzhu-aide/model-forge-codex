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
import { phaseQuestionAnchor } from "../src/phaseInputSummary.js";
import { navigationDom } from "./fixtures/saved-input-navigation-dom.mjs";

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
    useContext(context) { return context._currentValue; },
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

async function projectFixture(branch, action, { corrections = [], runs = [], branches = [], phase = "P2", attention = [], answers = [], artifacts = {}, methods = [methodA, methodB], problemContext, readiness = {}, awaiting = runs.filter(run => run.state === "awaiting_user"), p2ProposalKey, layout = false } = {}) {
  const originals = { api: { ...ui.api }, window: globalThis.window, document: globalThis.document,
    requestAnimationFrame: globalThis.requestAnimationFrame, cancelAnimationFrame: globalThis.cancelAnimationFrame, MutationObserver: globalThis.MutationObserver, setTimeout: globalThis.setTimeout };
  const harness = hookHarness({ layout }); const elements = new Map(); const afterClose = []; let starts = 0;
  globalThis.window = { addEventListener() {}, removeEventListener() {}, matchMedia: () => ({ matches: true }) };
  globalThis.document = { hidden: false, addEventListener() {}, removeEventListener() {}, getElementById: id => elements.get(id) };
  Object.assign(ui.api, {
    project: async () => ({ project: { name: "Integration project" }, problem_context: problemContext, workflow_capabilities: { researcher_dialogue: true } }),
    branches: async () => ({ branches }), listRuns: async () => ({ runs }), run: async (_projectId, runId) => runs.find(run => run.run_id === runId),
    artifacts: async () => artifacts, decisionsPending: async () => ({ attention, researcher_answers: answers, runs_needing_correction: corrections, runs_awaiting_direction: awaiting }),
    readiness: async () => readiness, records: async () => ({ records: [] }),
    assessments: async () => ({ assessments: [] }), methods: async () => ({ methods, diagnostics: [] }),
    startRun: async () => { starts++; throw new Error("This inspection must not start research."); },
  });
  const navigations = [];
  const props = { projectId: "project.integration", context: { phase, branch, p2ProposalKey }, onContextChange(next) { navigations.push(next); } };
  const render = () => harness.render(props);
  try {
    render(); await harness.load();
    await action({ render, elements, navigations, props, load: harness.load, settleLayout: harness.settleLayout, starts: () => starts, afterClose: callback => afterClose.push(callback) });
  } finally {
    harness.close(); afterClose.forEach(callback => callback()); Object.assign(ui.api, originals.api);
    if (originals.window === undefined) delete globalThis.window; else globalThis.window = originals.window;
    if (originals.document === undefined) delete globalThis.document; else globalThis.document = originals.document;
    for (const name of ["requestAnimationFrame", "cancelAnimationFrame", "MutationObserver", "setTimeout"]) {
      if (originals[name] === undefined) delete globalThis[name]; else globalThis[name] = originals[name];
    }
  }
}

test("P3 method selection keeps the shared goal label current and follows a replaced P1 source on refresh", async () => {
  const reference = { branch: "trunk", phase: "P1", family: "research_basis", generation_id: "goal.current", sha256: "c".repeat(64), run_id: "run.goal", package_id: "package.goal" };
  const basis = { branch: "trunk", phase: "P1", generation_ref: reference, research_setting: { research_goal_markdown: "Keep cost and chance constraints separate." } };
  const item = { item_id: "context.goal", revision: 1, status: "confirmed", topic: "research_goal", statement: "Cost and chance constraints have separate roles.", origin: "researcher_reported", scope: { kind: "project" }, source_refs: [{ ...reference, kind: "research_goal", entry_pointer: "/research_setting/research_goal_markdown" }] };
  const problemContext = { revision: 9, items: [item] };
  const readiness = { basis: { records: [{ ...reference, content_sha256: reference.sha256 }] } };
  const original = JSON.stringify(problemContext);
  await projectFixture("trunk", async ({ render, props, load, starts }) => {
    const label = () => ui.renderToStaticMarkup(find(render(), ui.Dialogue));
    assert.match(label(), /Research goal correction · current published goal/);
    ui.api.artifacts = async () => ({});
    props.context = { phase: "P3", branch: "method.a" };
    render(); await load();
    assert.match(label(), /Research goal correction · current published goal/);
    assert.equal(find(render(), ui.Dialogue).props.branch, "method.a");
    readiness.basis.records[0] = { ...reference, generation_id: "goal.replaced", content_sha256: "d".repeat(64) };
    find(render(), ui.Dialogue).props.onSaved(); render(); await load();
    assert.match(label(), /Research goal correction · earlier published goal/);
    readiness.basis.records = [];
    find(render(), ui.Dialogue).props.onSaved(); render(); await load();
    assert.match(label(), /Research goal correction · published goal status unavailable/);
    assert.equal(starts(), 0);
    assert.equal(JSON.stringify(problemContext), original);
  }, { phase: "P3", artifacts: { research_bases: [basis] }, problemContext, readiness });
});

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
const nextButton = (tree) => findClass(tree, "project-next").props.children.at(-1) || findClass(tree, "project-setting-link project-question-link");

function questionLinks(tree) {
  if (Array.isArray(tree)) return tree.flatMap(questionLinks);
  if (!tree || typeof tree !== "object") return [];
  return tree.props?.className === "project-setting-link project-question-link" ? [tree] : questionLinks(tree.props?.children);
}
test("unanswered questions and an actual pause have different navigation cues without losing phase labels", async () => {
  const question = { attention_id: "question.navigation", kind: "researcher_decision", phase: "P1", branch: "trunk", disposition: "open",
    severity: "blocking", question: "Which population should this estimate describe?", scope: { kind: "project" } };
  for (const paused of [false, true]) await projectFixture("trunk", async ({ render, starts }) => {
    const tree = render(); const next = findClass(tree, "project-next");
    assert.equal(next.props["data-next"], paused ? "decision" : "questions");
    const nextHtml = ui.renderToStaticMarkup(next);
    assert.match(nextHtml, paused ? /Work is paused in Phase 1/ : /1 unanswered question/);
    assert.match(nextHtml, paused ? /data-icon="pause"/ : /data-icon="ask"/);
    const navigation = ui.renderToStaticMarkup(findClass(tree, "phase-stepper"));
    for (let number = 1; number <= 5; number++) assert.match(navigation, new RegExp(`class="phase-short-name" aria-hidden="true">Phase ${number}<`));
    assert.match(navigation, /aria-label="Phase 1 - Define and Explore:.*1 unanswered question/);
    if (paused) assert.match(navigation, /class="phase-step waiting current"/);
    else {
      assert.match(navigation, /data-icon="ask"/);
      assert.doesNotMatch(navigation, /Work is paused|>Paused<|M6 2\.7/);
    }
    assert.equal(starts(), 0);
  }, { phase: "P1", attention: [question], runs: paused ? [{ run_id: "run.navigation", phase: "P1", branch_id: "trunk", state: "awaiting_user" }] : [] });
});

test("theory shortcuts select the requested view and focus its selected tab without a second scroll", async () => {
  await projectFixture("method.a", async ({ render, props, starts }) => {
    const previousStyle = globalThis.getComputedStyle;
    const requests = [], focusCalls = []; let frame;
    props.onReadingChange = value => requests.push(value);
    const tree = render(), root = { querySelectorAll: () => [panel], querySelector: () => ({ offsetHeight: 40 }) };
    const tab = { hasAttribute: () => true, focus: value => focusCalls.push(value) };
    const panel = { parentElement: root, tagName: "SECTION", isConnected: true, dataset: {},
      getAttribute: () => "theory-reading", closest: () => null, getBoundingClientRect: () => ({ top: 56 }),
      querySelector: selector => selector === '[role="tab"][aria-selected="true"]' ? tab : null,
      addEventListener() {} };
    try {
      globalThis.getComputedStyle = () => ({ display: "block", visibility: "visible" });
      globalThis.requestAnimationFrame = callback => { frame = callback; return 1; };
      globalThis.setTimeout = () => 1;
      Object.assign(globalThis.window, { scrollY: 300, scrollTo: () => assert.fail("An already aligned reader should not scroll."), innerHeight: 800 });
      tree.ref.current = root;
      const walk = node => Array.isArray(node) ? node.map(walk).find(Boolean) : !node?.props ? null
        : node.props.onReadTheory ? node : walk(node.props.children);
      walk(tree).props.onReadTheory("arguments");
      assert.deepEqual(requests, [{ tab: "arguments" }]); frame();
      assert.deepEqual(focusCalls, [{ preventScroll: true }]);
      assert.equal(panel.dataset.arrival, "true"); assert.equal(starts(), 0);
    } finally {
      if (previousStyle === undefined) delete globalThis.getComputedStyle; else globalThis.getComputedStyle = previousStyle;
    }
  }, { phase: "P3" });
});
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
      assert.match(ui.renderToStaticMarkup(findClass(render(), "project-resume")), /1 unanswered question.*Selected model B.*Version 3/);
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
      assert.match(html, new RegExp(`Work is paused in Phase ${phase.slice(1)}[^<]*Selected model B`));
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

test("earlier P2 questions share a compact phase summary while retaining every exact model destination", async () => {
  const attention = [methodA, methodB].map(method => ({ attention_id: `question.${method.method_id}`, kind: "researcher_decision", phase: "P2", branch: "trunk", disposition: "open", question: "Which target applies?", generation_ref: { phase: "P2", branch: "trunk", family: "attention_items", generation_id: "attention.exact", sha256: "f".repeat(64), run_id: "run.exact", package_id: "package.exact" }, scope: { kind: "model", branch: "trunk", model_ref: method.identity } }));
  await projectFixture("method.a", async ({ render, navigations, starts }) => {
    const tree = render(), summary = findClass(tree, "project-question-destinations");
    assert.ok(summary, "Different model destinations use a native keyboard-accessible disclosure.");
    assert.equal(summary.type, "details");
    assert.equal(summary.props.open, undefined, "Long model names stay collapsed initially.");
    assert.equal(summary.props.children[0].type, "summary");
    assert.equal(summary.props.children[0].props.children, "2 earlier questions in Phase 2");
    const links = questionLinks(summary);
    assert.equal(links.length, 2);
    links.forEach(link => { assert.equal(link.type, "button"); assert.equal(link.props.type, "button"); link.props.onClick(); });
    assert.deepEqual(navigations, [methodA, methodB].map(method => ({ phase: "P2", p2ProposalKey: catalogSelectionKey(method) })));
    assert.equal(starts(), 0);
  }, { phase: "P4", attention });
  await projectFixture("method.a", async ({ render, navigations }) => {
    const link = questionLinks(render())[0];
    assert.equal(link.props["aria-label"] || link.props.children, "1 earlier question in Phase 2");
    link.props.onClick();
    assert.deepEqual(navigations, [{ phase: "P2", p2ProposalKey: catalogSelectionKey(methodB) }]);
  }, { phase: "P4", attention: [attention[1]] });
});

test("a compact phase summary preserves questions on multiple branches and exact report anchors", async () => {
  for (const questionPhase of ["P3", "P4", "P5"]) {
    const attention = [methodA, methodB].map(method => ({ attention_id: `question.${questionPhase}.${method.method_id}`, kind: "researcher_decision", phase: questionPhase, target_phase: questionPhase, branch: method.branch_id, disposition: "open", question: "Which target applies?" }));
    await projectFixture("trunk", async ({ render, navigations }) => {
      const tree = render(), summary = findClass(tree, "project-question-destinations");
      assert.equal(summary.props.children[0].props.children, `2 unanswered questions in Phase ${questionPhase.slice(1)}`);
      questionLinks(summary).forEach(link => link.props.onClick());
      assert.deepEqual(navigations, [methodA, methodB].map(method => ({ phase: questionPhase, branch: method.branch_id })));
    }, { phase: "P1", attention, branches: [methodA, methodB].map(method => ({ branch_id: method.branch_id })) });
  }
});

test("earlier question links work from each later phase and leave current questions and recovery primary", async () => {
  const earlier = { attention_id: "earlier", kind: "researcher_decision", phase: "P1", branch: "trunk", disposition: "open", question: "Which population applies?" };
  for (const phase of ["P2", "P3", "P4", "P5"]) {
    await projectFixture("method.a", async ({ render, navigations }) => {
      const link = questionLinks(render())[0];
      assert.equal(link.props.children, "1 earlier question in Phase 1");
      link.props.onClick();
      assert.deepEqual(navigations, [{ phase: "P1" }]);
    }, { phase, attention: [earlier] });
  }
  const current = { ...earlier, attention_id: "current", phase: "P3", branch: "method.a" };
  await projectFixture("method.a", async ({ render, navigations }) => {
    const tree = render();
    assert.match(ui.renderToStaticMarkup(findClass(tree, "project-next")), /1 unanswered question.*in this phase/);
    assert.equal(nextButton(tree).props.children, "Go to the questions");
    assert.equal(questionLinks(tree)[0].props.children, "1 earlier question in Phase 1");
    assert.deepEqual(navigations, []);
  }, { phase: "P3", attention: [earlier, current], branches: [{ branch_id: methodA.branch_id }] });
  await projectFixture("method.a", async ({ render }) => {
    const tree = render();
    assert.equal(nextButton(tree).props.children, "Review what stopped");
    assert.equal(questionLinks(tree)[0].props.children, "1 earlier question in Phase 1");
  }, { phase: "P3", attention: [earlier], corrections: [{ run_id: "failed.current", phase: "P3", branch_id: "method.a", state: "failed" }] });
});

test("Next uses the default P2 selection and counts shared questions in its current exact card", async () => {
  const attention = [{ attention_id: "shared", kind: "researcher_decision", phase: "P2", branch: "trunk", disposition: "open", question: "Which shared objective?" },
    { attention_id: "model-a", kind: "researcher_decision", phase: "P2", branch: "trunk", disposition: "open", question: "Which A target?", affected_record_ids: ["method.a"] },
    { attention_id: "p1", kind: "researcher_decision", phase: "P1", branch: "trunk", disposition: "open", question: "Which setting?" }];
  for (const p2ProposalKey of [undefined, "unavailable:proposal"]) await projectFixture("method.b", async ({ render }) => {
    const tree = render();
    assert.match(ui.renderToStaticMarkup(findClass(tree, "project-next")), /2 unanswered questions.*in this phase/);
    const reader = find(tree, ui.Methods);
    assert.equal(responseCount(reader.props.issues({ method: methodA, methodId: methodA.method_id, methodBranch: methodA.branch_id, catalogMethod: methodA })), 2);
  }, { attention, p2ProposalKey });
});

test("a same-phase P2 Next arrival skips a saved first question and focuses the unanswered summary after selection settles", async () => {
  const attention = [{ attention_id: "question.b", kind: "researcher_decision", phase: "P2", branch: "trunk", disposition: "open", question: "Which B target?", affected_record_ids: ["method.b"] }];
  const savedFirst = { ...attention[0], attention_id: "question.saved-first" };
  await projectFixture("method.a", async ({ render, props, navigations, settleLayout }) => {
    const frames = []; const effects = []; const child = hookHarness({ layout: true }); const previousStyle = globalThis.getComputedStyle; let selectedId;
    try {
      globalThis.requestAnimationFrame = callback => { frames.push(callback); return frames.length; };
      globalThis.cancelAnimationFrame = () => {};
      globalThis.setTimeout = () => 0;
      const tree = render(); settleLayout();
      let explore = exploreElement(find(tree, ui.Methods));
      child.render(explore.props, explore.type); child.settleLayout();
      selectedId = find(child.render(explore.props, explore.type), ui.Dialogue).props.methodId;
      const summary = { tagName: "SUMMARY", focus(options) { assert.deepEqual(options, { preventScroll: true }); effects.push(["focus", selectedId]); } };
      const target = { tagName: "DETAILS", open: false, isConnected: true, dataset: {}, closest: () => null, getAttribute: () => phaseQuestionAnchor(attention[0]), getBoundingClientRect: () => ({ top: 16 }),
        querySelector: selector => selector === ":scope > summary" ? summary : null, addEventListener() {} };
      const saved = { ...target, getAttribute: () => phaseQuestionAnchor(savedFirst), querySelector: () => { throw new Error("The saved question must never receive arrival focus."); } };
      const root = { querySelectorAll: () => [saved, target], querySelector: () => null }; target.parentElement = root; saved.parentElement = root;
      globalThis.getComputedStyle = () => ({ display: "block", visibility: "visible" });
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
      assert.equal(target.open, true);
      assert.equal(saved.open, false);
      assert.equal(target.dataset.arrival, "true");
    } finally { child.close(); if (previousStyle === undefined) delete globalThis.getComputedStyle; else globalThis.getComputedStyle = previousStyle; }
  }, { attention: [savedFirst, ...attention], answers: [{ attention_id: savedFirst.attention_id, revision: 1, attention: savedFirst, note: "Saved first answer." }], p2ProposalKey: catalogSelectionKey(methodA), layout: true });
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

test("P5 editorial choices appear once in Revise report before settings and Next opens the exact row", async () => {
  const source = { kind: "phase_issue", phase: "P5", branch: "method.a", family: "attention_items", generation_id: "report.editorial", sha256: "a".repeat(64), run_id: "run.report", package_id: "package.report", object_id: "editorial.focus", entry_pointer: "/items/0" };
  const editorial = { issue_id: source.object_id, attention_id: source.object_id, phase: "P5", target_phase: "P5", branch: "method.a", kind: "researcher_decision", question: "Which report emphasis should lead the introduction?", disposition: "open", response_kind: "choice", decision_priority: "interpretation", scope: { kind: "model", branch: "method.a", model_ref: methodA.identity }, explanation_target: source, generation_ref: source };
  const oldModel = { ...editorial, issue_id: "editorial.old", attention_id: "editorial.old", scope: { ...editorial.scope, model_ref: { ...methodA.identity, version: 0 } } };
  await projectFixture("method.a", async ({ render, starts }) => {
    const previousStyle = globalThis.getComputedStyle;
    try {
      const tree = render(); const revision = find(tree, ui.FurtherWork);
      assert.ok(!find(tree, ui.Dialogue)); assert.ok(find(tree, ui.Report));
      const html = ui.renderToStaticMarkup(revision);
      assert.match(html, /<h2>Revise report<\/h2>/);
      assert.equal((html.match(/>Which report emphasis should lead the introduction\?</g) || []).length, 1);
      assert.equal((html.match(/class="issue-instruction-editor contribution-surface"/g) || []).length, 1);
      assert.ok(html.indexOf('data-reading-anchor="report-editorial-choices"') < html.indexOf('data-reading-anchor="further-work"'));
      assert.doesNotMatch(html, /Decisions to discuss|Other information you gave me|editorial\.old/);
      assert.match(ui.renderToStaticMarkup(findClass(tree, "project-next")), /1 unanswered question.*in this phase/);
      const effects = [];
      const target = { tagName: "DETAILS", open: false, isConnected: true, dataset: {}, closest: () => null, hasAttribute: () => true, getAttribute: key => key === "data-reading-anchor" ? phaseQuestionAnchor(editorial) : null, getBoundingClientRect: () => ({ top: 16 }), querySelector: () => ({ tagName: "SUMMARY", focus: () => effects.push("focus") }), addEventListener() {} };
      const root = { querySelectorAll: () => [target], querySelector: () => null }; target.parentElement = root; tree.ref.current = root;
      globalThis.getComputedStyle = () => ({ display: "block", visibility: "visible" });
      globalThis.setTimeout = () => 0; window.scrollY = 0;
      nextButton(tree).props.onClick();
      assert.equal(target.open, true); assert.deepEqual(effects, ["focus"]); assert.equal(target.dataset.arrival, "true");
      assert.equal(starts(), 0);
    } finally { if (previousStyle === undefined) delete globalThis.getComputedStyle; else globalThis.getComputedStyle = previousStyle; }
  }, { phase: "P5", attention: [editorial, oldModel], artifacts: { issues: [editorial] }, runs: [{ run_id: "run.report", phase: "P5", branch_id: "method.a", state: "published" }] });
});

test("P5 current pauses retain their one response editor without adding editorial counts", async () => {
  const source = { kind: "researcher_pause", project_id: "project.integration", branch: "method.a", phase: "P5", run_id: "run.pause.editorial", stage_id: "report.assembly", request_id: "request.editorial", object_id: "request.editorial", revision: 1, sha256: "a".repeat(64) };
  const request = { request_id: source.request_id, stage_id: source.stage_id, revision: 1, question: "Which authorized audience should the report address?", explanation_target: source };
  const paused = { project_id: source.project_id, run_id: source.run_id, phase: source.phase, branch_id: source.branch, state: "awaiting_user", researcher_pause: { pending_request: request } };
  const mirrored = { attention_id: source.request_id, phase: source.phase, branch: source.branch, kind: "researcher_decision", question: request.question, disposition: "open", explanation_target: source };
  await projectFixture("method.a", async ({ render, starts }) => {
    const tree = render(); const revision = find(tree, ui.FurtherWork);
    const html = ui.renderToStaticMarkup(revision);
    assert.ok(find(revision.props.children, ui.ResearcherPause));
    assert.match(html, /Which authorized audience should the report address/);
    assert.doesNotMatch(html, /Editorial choices for this report|data-reading-anchor="report-editorial-choices"|unanswered question/);
    assert.match(ui.renderToStaticMarkup(findClass(tree, "project-next")), /Work is paused in Phase 5/);
    assert.equal(starts(), 0);
  }, { phase: "P5", attention: [mirrored], runs: [paused] });
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
    const activations = []; const preparations = [];
    ui.api.activateMethod = async (...args) => { activations.push(args); return { branch_id: "branch.selected.b" }; };
    ui.api.phasePreparation = async (...args) => { preparations.push(args); return { instructions: `Saved ${phase} directions.`, input_ids: [] }; };
    await find(render(), ui.Methods).props.onContinue(methodB, phase, { prepareRun: true });
    const dialog = find(render(), ui.LaunchRun);
    assert.ok(dialog);
    assert.equal(dialog.props.request.branch, "branch.selected.b");
    assert.equal(dialog.props.request.phase, phase);
    assert.equal(dialog.props.request.instructions, `Saved ${phase} directions.`);
    assert.equal(dialog.props.request.methodLabel, "Selected model B \u00b7 Version 3");
    assert.deepEqual(activations, [["project.integration", "method.b", methodB.identity]]);
    assert.deepEqual(preparations, [["project.integration", "method.b", phase]]);
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

test("P2 supporting documents follow the exact read method while Phase 1 notes follow the actual preparation basis", async () => {
  const basis = { branch: "trunk", phase: "P1", generation_ref: { phase: "P1", branch: "trunk", family: "research_basis", generation_id: "basis.exact", sha256: "c".repeat(64) },
    phase2_preparation: { text: "Compare the literature's unresolved alternatives.", supplied_method: { title: "A shared literature idea", specification_markdown: "Retain the original shared starting point." } } };
  const proposal = { proposal_id: "proposal.b", method: methodB, role: "theorist", generation_ref: { phase: "P2", family: "theory_proposal", generation_id: "proposal.exact", sha256: "a".repeat(64) }, proposed_evaluation_markdown: "Check calibration under the original assumptions." };
  const reviewed = { comparison: { generation_ref: { phase: "P2", family: "catalog_assessment", generation_id: "comparison.exact", sha256: "b".repeat(64) }, modification_options: [] } };
  await projectFixture("trunk", async ({ render, starts }) => {
    const reader = find(render(), ui.Methods);
    const input = { selected: proposal, method: methodB, reviewed };
    const original = JSON.stringify(input);
    for (const scenario of [
      { catalogMethod: methodB, sharedPreparation: true, shared: true },
      { catalogMethod: methodB, sharedPreparation: false, shared: false },
      { catalogMethod: null, sharedPreparation: false, shared: true },
    ]) {
      const card = reader.props.furtherWork({ method: methodB, methodId: methodB.method_id, methodBranch: methodB.branch_id, proposal, ...scenario, preparationDocumentInput: input });
      assert.equal(card.props.hasSupportingDocuments, true);
      assert.equal(card.props.supportingDocuments.props.input.selected, proposal);
      assert.equal(card.props.supportingDocuments.props.input.reviewed, reviewed);
      assert.deepEqual(card.props.supportingDocuments.props.input.phaseOne, scenario.shared ? { preparation: basis.phase2_preparation, generation_ref: basis.generation_ref } : null);
      assert.equal(card.props.methodId, scenario.shared ? undefined : methodB.method_id);
      assert.equal(card.props.branch, scenario.shared ? "trunk" : methodB.branch_id);
      assert.equal(card.props.supportingDocuments.key, "project.integration");
      assert.doesNotMatch(ui.renderToStaticMarkup(card.props.children), /proposed steps|literature&#x27;s unresolved|Modification options and proposed next work/);
    }
    assert.equal(JSON.stringify(input), original);
    assert.equal(starts(), 0);
  }, { artifacts: { research_bases: [basis] } });
});

test("P2 preparation reading survives publication changing the keyed editor from method to shared preparation", async () => {
  const proposal = { branch: "trunk", phase: "P2", proposal_id: "proposal.b", method: methodB, role: "theorist", generation_ref: { phase: "P2", family: "theory_proposal", generation_id: "proposal.exact", sha256: "a".repeat(64) }, proposed_evaluation_markdown: "Preserve this proposed investigation through catalog replacement." };
  const artifacts = { method_proposals: [proposal] };
  await projectFixture("trunk", async ({ render, load, props, starts }) => {
    const selected = { method: methodB, methodId: methodB.method_id, methodBranch: methodB.branch_id, proposal, catalogMethod: methodB, sharedPreparation: false,
      preparationDocumentInput: { selected: proposal, method: methodB, reviewed: null } };
    let tree = render(), card = find(tree, ui.Methods).props.furtherWork(selected);
    const methodKey = ui.FurtherWork(card.props).key;
    const documents = hookHarness(), rail = card.props.supportingDocuments;
    const contents = documents.render(rail.props, rail.type);
    const button = findClass(contents, "p2-reading-links").props.children[0];
    assert.equal(button.props.title, "Proposed investigations");
    button.props.onClick({ currentTarget: { isConnected: false } });
    const window = tree => {
      const walk = node => Array.isArray(node) ? node.map(walk).find(Boolean) : !node?.props ? null : node.type?.name === "ReadingHost" && node.props.snapshot ? node : walk(node.props.children);
      return walk(tree);
    };
    tree = render(); const original = window(tree).props.snapshot;
    assert.match(ui.renderToStaticMarkup(original.body), /through catalog replacement/);
    proposal.proposed_evaluation_markdown = "Replacement work from a newer publication.";
    ui.api.methods = async () => ({ methods: [] });
    find(tree, ui.Methods).props.onResolved(); render(); await load();
    tree = render(); card = find(tree, ui.Methods).props.furtherWork({ ...selected, catalogMethod: null });
    assert.notEqual(ui.FurtherWork(card.props).key, methodKey, "The real preparation owner moves from a method draft to shared instructions.");
    assert.equal(window(tree).props.snapshot, original, "The frozen document owner is outside the remounted preparation editor.");
    assert.match(ui.renderToStaticMarkup(window(tree).props.snapshot.body), /through catalog replacement/);
    assert.doesNotMatch(ui.renderToStaticMarkup(window(tree).props.snapshot.body), /Replacement work/);
    assert.ok(!find(card, window(tree).type), "The reading window is not owned by the keyed preparation card.");
    props.context = { phase: "P1", branch: "trunk" }; render(); await load();
    assert.ok(!window(render()));
    props.context = { phase: "P2", branch: "trunk" }; render(); await load();
    assert.ok(!window(render()), "Returning to the phase does not revive the old source window.");
    assert.equal(starts(), 0);
  }, { artifacts });
});

test("P2 first publication preserves an open preparation reader while an explicit method choice closes it", async () => {
  const basis = { branch: "trunk", phase: "P1", generation_ref: { branch: "trunk", phase: "P1", family: "research_basis", generation_id: "basis.before-models", sha256: "f".repeat(64) },
    phase2_preparation: { text: "Read the original literature preparation through first publication." } };
  const artifacts = { research_bases: [basis], method_proposals: [] };
  const readerSnapshot = tree => {
    const walk = node => Array.isArray(node) ? node.map(walk).find(Boolean) : !node?.props ? null
      : node.type?.name === "ReadingHost" ? node.props.snapshot : walk(node.props.children);
    return walk(tree);
  };
  await projectFixture("trunk", async ({ render, load, starts }) => {
    const explore = hookHarness({ layout: true }), documents = hookHarness();
    try {
      let element = exploreElement(find(render(), ui.Methods));
      let contents = explore.render(element.props, element.type); explore.settleLayout(); await explore.load();
      const card = find(contents, ui.FurtherWork), rail = card.props.supportingDocuments;
      const documentList = documents.render(rail.props, rail.type);
      const button = findClass(documentList, "p2-reading-links").props.children[0];
      assert.equal(button.props.title, "Notes from Phase 1");
      button.props.onClick({ currentTarget: { isConnected: false } });
      const original = readerSnapshot(render()); assert.ok(original);
      artifacts.method_proposals = [methodB, methodA].map((method, index) => ({ branch: "trunk", phase: "P2", proposal_id: `proposal.first.${index}`, role: "theorist",
        generation_ref: { branch: "trunk", phase: "P2", family: "theory_proposal", generation_id: `proposal.first.${index}`, run_id: "run.first", sha256: "a".repeat(64) }, method }));
      ui.api.methods = async () => ({ methods: [methodA, methodB], diagnostics: [] });
      find(render(), ui.Methods).props.onResolved(); render(); await load();
      element = exploreElement(find(render(), ui.Methods));
      explore.render(element.props, element.type); explore.settleLayout(); await explore.load();
      contents = explore.render(element.props, element.type);
      assert.equal(readerSnapshot(render()), original, "Automatic selection synchronization must retain the open exact document.");
      const findPicker = node => Array.isArray(node) ? node.map(findPicker).find(Boolean) : !node?.props ? null
        : node.type?.name === "MethodPicker" ? node : findPicker(node.props.children);
      const picker = findPicker(contents);
      const different = picker.props.proposals.find(proposal => proposalKey(proposal) !== picker.props.value);
      picker.props.onSelect(proposalKey(different));
      assert.equal(readerSnapshot(render()), null, "A deliberate model change closes the previous supporting reader.");
      assert.equal(starts(), 0);
    } finally { explore.close(); documents.close(); }
  }, { artifacts, methods: [] });
});

test("an explicit saved-answer visit crosses phases and returns to the same method, open item and keyboard control", async () => {
  const source = { ...target, phase: "P2", object_id: "question.earlier", family: "attention_items" };
  const question = { attention_id: "question.earlier", phase: "P2", target_phase: "P1", branch: "trunk", kind: "researcher_decision", disposition: "open", question: "Which population is intended?", explanation_target: source, scope: { kind: "project" } };
  const answer = { attention_id: question.attention_id, revision: 2, note: "This remains unknown.", origin: "unknown", question_ref: source, attention: question };
  const findText = (node, text) => Array.isArray(node) ? node.map(child => findText(child, text)).find(Boolean)
    : !node?.props ? null : node.props.children === text ? node : findText(node.props.children, text);
  await projectFixture("method.b", async ({ render, props, navigations, load, settleLayout, starts, afterClose }) => {
    const dom = navigationDom();
    afterClose(() => dom.cleanup());
      props.context = { ...props.context, p2ProposalKey: "run.origin:proposal.origin", p2SharedPreparation: true };
      props.reading = { tab: "comparisons", dataView: "synthetic" };
      const tree = render(); tree.ref.current = dom.root;
      const original = dom.saved(); settleLayout(); dom.flush(); window.scrollY = 800;
      const dialogue = find(tree, ui.Dialogue);
      assert.equal(dialogue.props.onNavigate("P2", source, undefined, { origin: original.origin, savedInput: true }), true);
      assert.deepEqual(navigations.at(-1), { phase: "P1" }, "The question's answer owner, rather than its publishing phase, is selected.");
      props.context = { ...props.context, ...navigations.at(-1) }; render(); await load();
      dom.root.children = [];
      const editor = dom.root.append(new dom.Element("details", { "data-reading-anchor": phaseQuestionAnchor(question) }, 1200));
      const destination = render(); destination.ref.current = dom.root; settleLayout(); dom.flush();
      assert.equal(editor.open, true); assert.equal(dom.focused.at(-1).element, editor);
      const back = findText(render(), "Back to saved input"); assert.ok(back);
      back.props.onClick();
      assert.equal(navigations.at(-1).phase, "P4"); assert.equal(navigations.at(-1).branch, "method.b");
      assert.equal(navigations.at(-1).p2ProposalKey, "run.origin:proposal.origin");
      assert.equal(navigations.at(-1).p2SharedPreparation, true);
      assert.equal(navigations.at(-1).readers["P4:method.b"].dataView, "synthetic");
      props.context = { ...props.context, ...navigations.at(-1) }; render(); await load();
      const returned = dom.saved(); returned.badge.open = false; returned.item.open = false;
      dom.scrolls.length = 0; dom.focused.length = 0;
      const restored = render(); restored.ref.current = dom.root; settleLayout(); dom.flush();
      assert.ok(returned.badge.open && returned.item.open);
      assert.deepEqual(dom.scrolls, [{ top: 800, behavior: "instant" }]);
      assert.deepEqual(dom.focused, [{ element: returned.origin, options: { preventScroll: true } }]);
      assert.equal(findText(render(), "Back to saved input"), undefined);
      find(render(), ui.Dialogue).props.onSaved(); render(); await load(); settleLayout(); dom.flush();
      assert.equal(dom.focused.length, 1, "A refresh never replays the completed navigation.");
      assert.equal(starts(), 0);
  }, { phase: "P4", answers: [answer], artifacts: { issues: [question], load_errors: [] }, layout: true });
});

test("decision summaries distinguish unselected method scopes, complete data and a failed refresh", async () => {
  for (const phase of ["P3", "P4"]) await projectFixture("trunk", async ({ render }) => {
    const card = find(render(), ui.Dialogue);
    assert.equal(card.props.decisionScope, "unselected-method");
    assert.equal(card.props.decisionDataState, "unavailable");
  }, { phase, artifacts: { issues: [], load_errors: [] } });
  await projectFixture("trunk", async ({ render, load }) => {
    const reader = find(render(), ui.Methods);
    assert.equal(reader.props.issues().props.decisionScope, "shared-overview");
    const selected = { method: methodB, methodId: methodB.method_id, methodBranch: methodB.branch_id, catalogMethod: methodB };
    assert.equal(reader.props.issues(selected).props.decisionScope, "selected");
    assert.equal(reader.props.issues(selected).props.decisionDataState, "ready");
    ui.api.decisionsPending = async () => { throw new Error("Decision refresh failed."); };
    reader.props.onResolved(); render(); await load();
    const retained = find(render(), ui.Methods).props.issues(selected);
    assert.equal(retained.props.decisionDataState, "refresh-failed");
    assert.equal(retained.props.decisionScope, "selected");
  }, { artifacts: { issues: [], load_errors: [] } });
});
