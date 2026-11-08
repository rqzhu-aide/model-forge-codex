import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { researchReadingSize } from "../src/readingSize.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-p2-preparation-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `export {default as React} from 'react'; export {renderToStaticMarkup} from 'react-dom/server';
  export {default as Preparation, preparationReadingDocuments as documents, preparationReadingKey as key, preparationReadingSnapshot as snapshot} from '${src}/components/PreparationDocuments.jsx';
  export {MethodReadingWindow as Window, ReadingDocumentButton as Button} from '${src}/components/MethodReadingWindow.jsx';
  export {SourceRef} from '${src}/components/Shared.jsx';
  export {empiricalSource} from '${src}/components/EmpiricalDocument.jsx';
  export {default as ProjectView} from '${src}/components/ProjectView.jsx';
  export {default as FurtherWork} from '${src}/components/FurtherWorkCard.jsx';
  export {api} from '${src}/api.js';`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);

function all(node, predicate) {
  if (Array.isArray(node)) return node.flatMap(item => all(item, predicate));
  if (!ui.React.isValidElement(node)) return [];
  return [...(predicate(node) ? [node] : []), ...all(node.props.children, predicate)];
}
const source = (family, generation_id, byte) => ({ branch: "trunk", phase: family === "research_basis" ? "P1" : "P2", family, generation_id,
  sha256: byte.repeat(64), run_id: "run.original", package_id: "package.original" });
const fixture = () => {
  const method = { title: "A method with a long exact title", identity: { stable_id: "method.a", version: 2, definition_sha256: "d".repeat(64) } };
  const selected = { proposal_id: "proposal.a", role: "theorist", method, generation_ref: source("theory_proposal", "proposal.exact", "a"), proposed_evaluation_markdown: "Establish calibration only under the stated conditions.\n\n$$\\operatorname{Var}(T) \\leq C/n.$$" };
  const option = { option_id: "change.a", applies_to: "proposal.a", title: "Change the estimating equation", what_changes_markdown: "Replace the original score.\n\n$$g(\\theta)=0.$$", when_preferable_markdown: "Prefer this only when the observations support the additional assumption." };
  const comparison = { generation_ref: source("catalog_assessment", "assessment.exact", "b"), modification_options: [option, { ...option, applies_to: "proposal.b", title: "Another method's modification" }] };
  return { selected, method, reviewed: { comparison }, phaseOne: { preparation: { text: "The literature leaves this comparison unresolved." }, generation_ref: source("research_basis", "basis.exact", "c") } };
};

test("preparation documents preserve exact applicable content, authorship and reading size", () => {
  const input = fixture(), before = structuredClone(input);
  const { documents, notes } = ui.documents(input, () => {});
  assert.equal(documents.length, 3); assert.deepEqual(notes, []);
  const modifications = documents.find(item => item.name === "suggested-modifications");
  const work = documents.find(item => item.name === "proposed-investigations");
  const phaseOne = documents.find(item => item.name === "phase-one-notes");
  const option = input.reviewed.comparison.modification_options[0];
  assert.deepEqual(modifications.size, researchReadingSize({ title: option.title, text: [option.what_changes_markdown, option.when_preferable_markdown] }));
  assert.match(ui.renderToStaticMarkup(modifications.body), /additional assumption|katex-display/);
  assert.doesNotMatch(ui.renderToStaticMarkup(modifications.body), /Another method/);
  assert.match(modifications.subtitle, /Version 2.*Research Lead/);
  assert.match(work.subtitle, /Version 2.*Theorist/);
  assert.doesNotMatch(work.subtitle, /Research Lead/);
  assert.match(ui.renderToStaticMarkup(work.body), /proposed steps, not completed proofs or simulations/);
  assert.deepEqual(work.size, researchReadingSize(input.selected.proposed_evaluation_markdown));
  for (const [document, expected] of [[modifications, input.reviewed.comparison.generation_ref], [work, input.selected.generation_ref], [phaseOne, input.phaseOne.generation_ref]]) {
    assert.deepEqual(all(document.body, node => node.type === ui.SourceRef).map(node => node.props.reference), [expected]);
  }
  assert.deepEqual(input, before);
});

test("missing supporting records remain distinguishable from recorded absence without empty buttons", () => {
  const input = fixture(); input.phaseOne = null; input.selected.proposed_evaluation_markdown = "";
  delete input.reviewed;
  assert.deepEqual(ui.documents(input).documents, []);
  assert.match(ui.documents(input).notes.join(" "), /No Lead assessment is linked.*investigations were not recorded/);
  input.reviewed = { comparison: {} };
  assert.match(ui.documents(input).notes[0], /did not record separate modification options/);
  input.reviewed.comparison.modification_options = [];
  assert.match(ui.documents(input).notes[0], /recorded no modification options for this proposal/);
  const html = ui.renderToStaticMarkup(ui.React.createElement(ui.Preparation, { projectId: "p", input }));
  assert.doesNotMatch(html, /p2-reading-button|p2-preparation-resources|Supporting reading|Supporting documents/);
  assert.match(html, /recorded no modification options/);
  assert.equal(ui.documents({}).documents.length, 0);
});

test("reading keys follow only the contributing exact sources and isolate legacy replacements", () => {
  const input = fixture(), documents = ui.documents(input).documents;
  const keys = docs => docs.map(document => ui.key("p", document));
  assert.deepEqual(keys(documents), keys(ui.documents(structuredClone(input)).documents));
  const updated = structuredClone(input); updated.reviewed.comparison.generation_ref.sha256 = "f".repeat(64);
  const newer = keys(ui.documents(updated).documents), original = keys(documents);
  assert.notEqual(newer[0], original[0]); assert.equal(newer[1], original[1]); assert.equal(newer[2], original[2]);
  assert.notEqual(ui.key("another-project", documents[1]), original[1]);
  input.selected.generation_ref = undefined; input.phaseOne.generation_ref = undefined;
  const legacy = keys(ui.documents(input).documents);
  input.selected.proposed_evaluation_markdown = "A replacement investigation."; input.phaseOne.preparation.text = "Replacement literature notes.";
  const replacement = keys(ui.documents(input).documents);
  assert.notEqual(legacy[1], replacement[1]); assert.notEqual(legacy[2], replacement[2]);
});

function harness(sources) {
  const slots = []; let cursor;
  const internals = ui.React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED;
  const dispatcher = {
    useState(initial) { const at = cursor++; if (!(at in slots)) slots[at] = typeof initial === "function" ? initial() : initial; return [slots[at], value => { slots[at] = typeof value === "function" ? value(slots[at]) : value; }]; },
    useRef(initial) { return slots[cursor++] ||= { current: initial }; },
    useId() { return `fixture-${cursor++}`; },
    useContext(context) { return sources ?? context._currentValue; },
  };
  return props => { cursor = 0; const previous = internals.ReactCurrentDispatcher.current; internals.ReactCurrentDispatcher.current = dispatcher;
    try { return ui.Preparation(props); } finally { internals.ReactCurrentDispatcher.current = previous; } };
}

test("opening supporting reading freezes the source through polling without saving, attaching or starting work", () => {
  const render = harness(), input = fixture(); let mutations = 0; const originals = { ...ui.api };
  for (const name of ["startRun", "savePhasePreparation", "activateMethod"]) ui.api[name] = () => { mutations++; };
  try {
    let opened;
    const props = { projectId: "p", input, onSource: () => { mutations++; }, onReadDocument: document => { opened = document; } };
    let tree = render(props);
    const trigger = { isConnected: true };
    all(tree, node => node.type === ui.Button)[1].props.onClick({ currentTarget: trigger });
    tree = render(props);
    const original = opened, html = ui.renderToStaticMarkup(original.body);
    assert.match(html, /Establish calibration only under the stated conditions/);
    assert.equal(opened.trigger, trigger);
    const updated = fixture(); updated.selected.proposed_evaluation_markdown = "A newer investigation."; updated.selected.generation_ref.sha256 = "f".repeat(64);
    render({ ...props, input: updated });
    assert.equal(opened, original);
    assert.equal(ui.renderToStaticMarkup(opened.body), html);
    render({ ...props, input: {} });
    assert.equal(opened, original);
    assert.equal(mutations, 0);
    all(render({ ...props, input: updated }), node => node.type === ui.Button)[1].props.onClick({ currentTarget: trigger });
    assert.notEqual(opened.key, original.key);
    assert.equal(mutations, 0);
  } finally { Object.assign(ui.api, originals); }
});

test("P2 preparation uses the shared reading layout and preserves no-document notes below the editor", () => {
  const props = { projectId: "p", branch: "trunk", phase: "P2", hasRun: true, supportingDocuments: ui.React.createElement("p", null, "Reference document"), hasSupportingDocuments: true };
  const render = props => ui.renderToStaticMarkup(ui.React.createElement(ui.FurtherWork, props));
  const populated = render(props);
  assert.match(populated, /research-card-layout has-rail/);
  assert.match(populated, /aria-label="Run preparation supporting reading"/);
  assert.match(populated, /Shared proposal and comparison instructions/);
  assert.ok(populated.indexOf('class="research-card-account"') < populated.indexOf('class="research-card-resources"'));
  assert.equal((populated.match(/Reference document/g) || []).length, 1);
  assert.doesNotMatch(populated, /research-card-actions|p2-preparation-layout|p2-preparation-editor|p2-preparation-resources/);
  const noDocuments = render({ ...props, hasSupportingDocuments: false, supportingDocuments: ui.React.createElement("p", null, "No recorded investigations") });
  assert.match(noDocuments, /class="research-card-layout"/);
  assert.doesNotMatch(noDocuments, /research-card-resources|research-card-actions|has-rail/);
  assert.match(noDocuments, /Loading your saved instructions…<\/p><\/div><\/div><\/div><p>No recorded investigations<\/p>/);
  assert.equal((noDocuments.match(/No recorded investigations/g) || []).length, 1);
  assert.doesNotMatch(render({ ...props, phase: "P1" }), /research-card-columns|p2-preparation|Reference document/);
});

test("preparation supporting reading has one heading and keeps all three document controls", () => {
  const html = ui.renderToStaticMarkup(ui.React.createElement(ui.Preparation, { projectId: "p", input: fixture() }));
  assert.match(html, /^<section aria-labelledby=/);
  assert.match(html, />Supporting reading<\/h3>/);
  assert.doesNotMatch(html, /Supporting documents|p2-preparation-resources|p2-resource-group/);
  for (const title of ["Suggested modifications", "Proposed investigations", "Notes from Phase 1"]) assert.equal((html.match(new RegExp(title, "g")) || []).length, 1);
});

test("P3 preparation reading carries the Lead's recommended actions with phase and method scope", () => {
  const generation_ref = source("decision", "decision.exact", "e");
  const available_actions = [
    { action_id: "run_p4", action_type: "run_phase", label: "Run Phase 4 with this method", consequence: "Starts the empirical evaluation of the retained theory.", launches_run: true, requires_user_action: false },
    { action_id: "revise", action_type: "rerun_phase", label: "Revise the theory", consequence: "Reruns Phase 3 with revised instructions.", launches_run: true, requires_user_action: true },
  ];
  const input = { phase: "P3", branch: "method.a", methodLabel: "Method A", decision: { available_actions, generation_ref } };
  const before = structuredClone(input);
  const { documents, notes } = ui.documents(input, () => {});
  assert.deepEqual(notes, []);
  assert.equal(documents.length, 1);
  const [document] = documents;
  assert.deepEqual([document.name, document.title, document.subtitle, document.phase], ["lead-recommended-actions", "Lead's recommended actions", "Method A · Research Lead", "P3"]);
  assert.deepEqual(document.scope, ["P3", "method.a"]);
  const html = ui.renderToStaticMarkup(document.body);
  assert.match(html, /<section class="modification-option"><h3>Run Phase 4 with this method<\/h3>[\s\S]*?Starts the empirical evaluation[\s\S]*?<h3>Revise the theory<\/h3>[\s\S]*?Reruns Phase 3/);
  assert.deepEqual(all(document.body, node => node.type === ui.SourceRef).map(node => [node.props.reference, node.props.label]), [[generation_ref, "Lead assessment source"]]);
  assert.deepEqual(document.size, researchReadingSize(available_actions.map(action => ({ title: action.label, text: action.consequence }))));
  const key = ui.key("project.a", document);
  assert.match(key, /"P3"/); assert.match(key, /method\.a/); assert.match(key, /decision\.exact/);
  assert.notEqual(ui.key("project.a", ui.documents({ ...input, branch: "method.b" }).documents[0]), key);
  const snapshot = ui.snapshot("project.a", input, "lead-recommended-actions", () => {});
  assert.equal(snapshot.phase, "P3"); assert.equal(snapshot.key, key); assert.equal(snapshot.projectId, "project.a");
  assert.deepEqual(input, before);
  assert.equal(ui.documents({ phase: "P3", branch: "method.a" }).documents.length, 0);
  assert.equal(ui.documents({ ...input, decision: { available_actions: [], generation_ref } }).documents.length, 0);
  const rendered = ui.renderToStaticMarkup(ui.React.createElement(ui.Preparation, { projectId: "project.a", input }));
  assert.match(rendered, /Supporting reading/);
  assert.match(rendered, /Lead&#x27;s recommended actions/);
  assert.match(rendered, /does not add them to your instructions or selected sources/);
  assert.doesNotMatch(rendered, /The team recommends/);
});

test("P4 preparation reading separates the Lead's recommendation from each question's attributed next steps", () => {
  const summaryRef = source("empirical_summary", "summary.exact", "a");
  const review = source("question_review", "review.exact", "b"), result = source("question_result", "result.exact", "c");
  const summary = { generation_ref: summaryRef, decision_summary: { recommendation_markdown: "Keep the audited rational mixing and rerun the partial-moment search with the complete data." } };
  const questions = [
    { question_id: "q.1", title: "Does mixing help reward?", branch: "method.a", generation_ref: source("question", "question.exact", "d"),
      review: { next_steps_markdown: "Repeat the comparison with the audited data before changing the estimator.", generation_ref: review },
      result: { next_steps_markdown: "Add the partial-moment search to the next run.", generation_ref: result } },
    { question_id: "q.2", title: "Unanswered question", branch: "method.a", review: {}, result: null },
  ];
  const input = { phase: "P4", branch: "method.a", methodLabel: "Method A", summary, questions };
  const before = structuredClone(input);
  const { documents, notes } = ui.documents(input, () => {});
  assert.deepEqual(notes, []);
  assert.deepEqual(documents.map(item => [item.name, item.title, item.subtitle, item.phase]), [
    ["lead-recommendation", "Lead's recommendation", "Method A · Research Lead", "P4"],
    ["question-next-steps", "Question next steps", "Method A · Research Lead and Data Analyst", "P4"]]);
  const [recommendation, steps] = documents;
  assert.match(ui.renderToStaticMarkup(recommendation.body), /Keep the audited rational mixing/);
  assert.deepEqual(all(recommendation.body, node => node.type === ui.SourceRef).map(node => node.props.reference), [summaryRef]);
  const stepsHtml = ui.renderToStaticMarkup(steps.body);
  assert.match(stepsHtml, /<h3>Does mixing help reward\?<\/h3><h4>Research Lead<\/h4>[\s\S]*?Repeat the comparison with the audited data[\s\S]*?<h4>Data Analyst<\/h4>[\s\S]*?Add the partial-moment search/);
  assert.doesNotMatch(stepsHtml, /Unanswered question/);
  assert.deepEqual(all(steps.body, node => node.type === ui.SourceRef).map(node => [node.props.reference, node.props.label]), [[review, "Lead review source"], [result, "Analyst result source"]]);
  assert.match(ui.key("project.a", steps), /"P4"[\s\S]*method\.a[\s\S]*q\.1/);
  assert.deepEqual(input, before);
  assert.deepEqual(ui.documents({ phase: "P4", branch: "method.a", summary: { decision_summary: {} }, questions: [questions[1]] }).documents, []);
  assert.deepEqual(ui.documents({ phase: "P4", branch: "method.a" }).documents, []);
});

test("P2 preparation documents keep their phase and scope when the input names neither", () => {
  const documents = ui.documents(fixture()).documents;
  assert.equal(documents.length, 3);
  for (const document of documents) { assert.equal(document.phase, "P2"); assert.deepEqual(document.scope, ["P2", null]); }
  assert.ok(ui.key("project.a", documents[0]).startsWith('["project.a","P2",["P2",null],"suggested-modifications"'));
  const scoped = ui.documents({ ...fixture(), phase: "P2", branch: "method.a" }).documents;
  assert.deepEqual(scoped[0].scope, ["P2", "method.a"]);
  assert.notEqual(ui.key("project.a", scoped[0]), ui.key("project.a", documents[0]));
});

test("P4 preparation captures verified file and record bindings outside the workbench provider", () => {
  const summaryRef = { ...source("empirical_summary", "summary.saved", "a"), branch: "method.a", phase: "P4", run_id: "run.saved" };
  const comparison = "run://run.saved/p4.exhibits/table_paired.csv", audit = "run://run.saved/p4.theory_audit/theory_audit.md";
  const recordUri = "run://run.saved/p4.summary/summary.json";
  const input = { phase: "P4", branch: "method.a", methodLabel: "Method A", summary: { generation_ref: summaryRef,
    decision_summary: { recommendation_markdown: `Keep the bounded comparison in the [paired table](${comparison}) and [audit](${audit}).` } },
    questions: [{ question_id: "question.saved", title: "What should be checked next?", review: { generation_ref: summaryRef,
      next_steps_markdown: `Recheck the [retained decision](${recordUri}#/decision_summary).` } }] };
  // This is the projected shape used by saved P4 summaries, including verified
  // run_sources files. It contains intentional fixture data only.
  const sources = { branch: "method.a", artifacts: [{ uri: recordUri, sha256: summaryRef.sha256 }], records: [undefined, input.summary],
    files: [{ uri: comparison, branch: "method.a", sha256: "b".repeat(64), source_verified: true, artifact_url: "/api/retained/paired.csv" },
      { uri: audit, branch: "method.a", sha256: "c".repeat(64), source_verified: true, artifact_url: "/api/retained/audit.md" }] };
  const before = structuredClone({ input, sources });
  const render = harness(sources), opened = [], calls = [];
  let currentAction = reference => calls.push(["initial", reference]);
  const onSource = reference => currentAction(reference);
  const props = { projectId: "project.fixture", input, onSource, onReadDocument: value => opened.push(value) };
  const trigger = { isConnected: true };
  for (const control of all(render(props), node => node.type === ui.Button)) control.props.onClick({ currentTarget: trigger });
  assert.equal(opened.length, 2);
  assert.deepEqual({ input, sources }, before, "Opening a reader does not modify research data.");
  const [recommendation, steps] = opened;
  const originalHtml = opened.map(value => ui.renderToStaticMarkup(value.body));
  assert.match(originalHtml[0], /href="\/api\/retained\/paired\.csv"/);
  assert.match(originalHtml[0], /href="\/api\/retained\/audit\.md"/);
  assert.match(originalHtml[1], /retained decision<\/button>/);
  for (const html of originalHtml) assert.doesNotMatch(html, /source unavailable|\]\(run:\/\//);
  assert.deepEqual(recommendation.size, researchReadingSize(before.input.summary.decision_summary.recommendation_markdown));
  assert.deepEqual([recommendation.projectId, recommendation.phase, recommendation.scope, recommendation.trigger], ["project.fixture", "P4", ["P4", "method.a"], trigger]);
  const same = ui.snapshot("project.fixture", input, "lead-recommendation", onSource, sources);
  assert.equal(same.key, recommendation.key);
  sources.branch = "method.replacement"; sources.artifacts[0].sha256 = "d".repeat(64);
  sources.files[0].artifact_url = "/api/replacement"; sources.files[1].source_verified = false;
  input.summary.generation_ref.generation_id = "summary.replacement";
  input.summary.decision_summary.recommendation_markdown = "A replacement recommendation.";
  input.questions[0].review.next_steps_markdown = "Replacement next steps.";
  render({ ...props, input });
  assert.equal(opened.length, 2, "Polling does not replace an already opened reader.");
  assert.deepEqual(opened.map(value => ui.renderToStaticMarkup(value.body)), originalHtml);
  assert.equal(recommendation.body.props.value.branch, "method.a");
  assert.equal(recommendation.body.props.value.records.length, 1);
  assert.equal(ui.empiricalSource(comparison, recommendation.body.props.value).artifact_url, "/api/retained/paired.csv");
  const target = ui.empiricalSource(`${recordUri}#/decision_summary`, steps.body.props.value);
  assert.deepEqual(target.reference, { ...before.input.summary.generation_ref, entry_pointer: "/decision_summary" });
  currentAction = reference => calls.push(["current", reference]);
  steps.body.props.value.onSource(target.reference);
  const sourceControl = all(recommendation.body, node => node.type === ui.SourceRef)[0];
  sourceControl.props.onOpen(sourceControl.props.reference);
  assert.deepEqual(calls, [["current", target.reference], ["current", before.input.summary.generation_ref]]);
  assert.notEqual(ui.snapshot("project.fixture", input, "lead-recommendation", onSource, sources).key, recommendation.key);
});

// Exercise the shipped ProjectView hooks, effects and handlers. Children remain
// React elements; browser focus and layout are checked separately.
function mountProject(initialProps) {
  const slots = [], internals = ui.React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED;
  let cursor = 0, pending = [], dirty = true, props = initialProps, tree;
  const effect = (run, deps) => {
    const at = cursor++, old = slots[at];
    if (!old || !deps || deps.some((value, index) => !Object.is(value, old.deps?.[index]))) {
      slots[at] = { deps, cleanup: old?.cleanup }; pending.push({ at, run });
    }
  };
  const hooks = {
    useState(initial) {
      const at = cursor++;
      if (!slots[at]) slots[at] = { value: typeof initial === "function" ? initial() : initial };
      return [slots[at].value, update => {
        const next = typeof update === "function" ? update(slots[at].value) : update;
        if (!Object.is(next, slots[at].value)) { slots[at].value = next; dirty = true; }
      }];
    },
    useRef(initial) { const at = cursor++; return (slots[at] ||= { value: { current: initial } }).value; },
    useId() { return `fixture-${cursor++}`; }, useEffect: effect, useLayoutEffect: effect,
  };
  const draw = () => {
    cursor = 0; pending = []; dirty = false;
    const previous = internals.ReactCurrentDispatcher.current;
    try { internals.ReactCurrentDispatcher.current = hooks; tree = ui.ProjectView(props); }
    finally { internals.ReactCurrentDispatcher.current = previous; }
    for (const { at, run } of pending) { slots[at].cleanup?.(); slots[at].cleanup = run(); }
  };
  return { get tree() { return tree; }, update(changes) { props = { ...props, ...changes }; dirty = true; },
    async settle() {
      for (let attempt = 0; attempt < 25; attempt++) {
        if (dirty) draw();
        await new Promise(setImmediate);
        if (!dirty) return tree;
      }
      throw new Error("ProjectView did not settle");
    },
    unmount() { for (const slot of slots) slot?.cleanup?.(); } };
}

test("a retained preparation reader opens its original source after automatic proposal replacement", async () => {
  const noop = () => {}, globals = { window: globalThis.window, document: globalThis.document, setInterval: globalThis.setInterval, clearInterval: globalThis.clearInterval };
  const originalApi = { ...ui.api };
  globalThis.window = { addEventListener: noop, removeEventListener: noop };
  globalThis.document = { hidden: false, addEventListener: noop, removeEventListener: noop };
  globalThis.setInterval = () => 0; globalThis.clearInterval = noop;
  let view, mutations = 0;
  const find = name => all(view.tree, node => node.type?.name === name)[0];
  try {
    const input = fixture(), proposal = { ...input.selected, branch: "trunk", phase: "P2" };
    const responses = { project: { project: { name: "Preparation regression fixture" }, workflow_capabilities: {} }, branches: { branches: [] }, listRuns: { runs: [] },
      artifacts: { method_proposals: [proposal] }, decisionsPending: { attention: [], researcher_answers: [] }, readiness: {}, records: { records: [] }, assessments: { assessments: [] }, methods: { methods: [] } };
    for (const [name, result] of Object.entries(responses)) ui.api[name] = async () => structuredClone(result);
    for (const name of ["startRun", "savePhasePreparation", "activateMethod"]) ui.api[name] = () => { mutations++; };
    let context = { branch: "trunk", phase: "P2", p2ProposalKey: "run.original:proposal.a" };
    view = mountProject({ projectId: "project.fixture", context, onOpenRun: noop,
      onContextChange(change) { context = { ...context, ...change }; view.update({ context }); } });
    await view.settle();
    const methods = find("MethodProposals");
    const work = methods.props.furtherWork({ methodBranch: "method.a", methodId: "method.a", method: proposal.method, proposal,
      preparationDocumentInput: { selected: proposal, method: proposal.method } });
    const support = work.props.supportingDocuments;
    const snapshot = ui.snapshot("project.fixture", support.props.input, "proposed-investigations", support.props.onSource);
    const originalBody = ui.renderToStaticMarkup(snapshot.body);
    support.props.onReadDocument(snapshot); await view.settle();
    const sourceControl = all(snapshot.body, node => node.type === ui.SourceRef)[0];
    sourceControl.props.onOpen(sourceControl.props.reference); await view.settle();
    assert.deepEqual(find("ResearchSourceDialog").props.reference, proposal.generation_ref);
    methods.props.onPick("run.replacement:proposal.replacement"); await view.settle();
    assert.equal(find("ResearchSourceDialog"), undefined, "A source dialog closes when its current selection changes.");
    assert.equal(find("ReadingHost").props.snapshot, snapshot);
    sourceControl.props.onOpen(sourceControl.props.reference); await view.settle();
    assert.deepEqual(find("ResearchSourceDialog")?.props.reference, proposal.generation_ref, "The frozen callback uses the surviving ProjectView's current scope.");
    assert.equal(context.p2ProposalKey, "run.replacement:proposal.replacement");
    assert.equal(ui.renderToStaticMarkup(snapshot.body), originalBody);
    assert.equal(mutations, 0);
    find("MethodProposals").props.onPick("run.explicit:proposal.explicit", { explicit: true }); await view.settle();
    assert.equal(find("ReadingHost").props.snapshot, null, "Explicit proposal selection still closes the retained reader.");
  } finally { view?.unmount(); Object.assign(ui.api, originalApi); Object.assign(globalThis, globals); }
});

test("opening report detail focuses its selected tab once, with sticky-header clearance and no polling focus", async () => {
  const names = ["window", "document", "getComputedStyle", "requestAnimationFrame", "cancelAnimationFrame", "setInterval", "clearInterval", "setTimeout", "clearTimeout"];
  const globals = Object.fromEntries(names.map(name => [name, globalThis[name]])), originalApi = { ...ui.api };
  const noop = () => {}, frames = [], focused = [], scrolled = [], style = new Map();
  let poll, view, selectedTab = "report";
  const element = (tagName, attributes = {}) => ({ tagName, isConnected: true, dataset: {}, parentElement: null,
    getAttribute(name) { return attributes[name] ?? null; }, hasAttribute(name) { return name in attributes; }, setAttribute(name, value) { attributes[name] = value; },
    closest() { return null; }, getClientRects() { return [{}]; }, getBoundingClientRect() { return { top: 680 - window.scrollY, bottom: 720 - window.scrollY, height: 40 }; },
    addEventListener: noop, removeEventListener: noop,
    focus() { focused.push(this); document.activeElement = this; } });
  const tab = element("BUTTON", { role: "tab", tabindex: "0" }), editor = element("TEXTAREA");
  const destination = element("SECTION", { "data-reading-anchor": "report-reading", tabindex: "-1" });
  destination.querySelector = selector => selector === '[role="tab"][aria-selected="true"]' && selectedTab === "changes" ? tab : null;
  const toolbar = { offsetHeight: 72, getBoundingClientRect: () => ({ height: 72 }) };
  const root = { isConnected: true, style: { getPropertyValue: name => style.get(name), setProperty: (name, value) => style.set(name, value) },
    querySelector: selector => selector === ".project-toolbar" ? toolbar : null,
    querySelectorAll: selector => selector === "[data-reading-anchor]" ? [destination] : [],
    contains: node => [destination, tab, editor].includes(node) };
  destination.parentElement = root; tab.parentElement = destination; editor.parentElement = root;
  globalThis.window = { scrollY: 80, innerHeight: 900, matchMedia: () => ({ matches: true }), addEventListener: noop, removeEventListener: noop,
    scrollTo(value) { scrolled.push(value); this.scrollY = value.top; } };
  globalThis.document = { hidden: false, activeElement: null, addEventListener: noop, removeEventListener: noop };
  globalThis.getComputedStyle = () => ({ top: "0px", display: "block", visibility: "visible" });
  globalThis.requestAnimationFrame = callback => frames.push(callback); globalThis.cancelAnimationFrame = noop;
  globalThis.setInterval = callback => { poll = callback; return 1; }; globalThis.clearInterval = noop;
  globalThis.setTimeout = () => 1; globalThis.clearTimeout = noop;
  const find = name => all(view.tree, node => node.type?.name === name)[0];
  try {
    const responses = { project: { project: { name: "Report navigation fixture" }, workflow_capabilities: {} }, branches: { branches: [] }, listRuns: { runs: [] },
      artifacts: {}, decisionsPending: { attention: [], researcher_answers: [] }, readiness: {}, records: { records: [] }, assessments: { assessments: [] }, methods: { methods: [] } };
    for (const [name, result] of Object.entries(responses)) ui.api[name] = async () => structuredClone(result);
    view = mountProject({ projectId: "project.fixture", context: { branch: "method.a", phase: "P5" }, reading: { tab: selectedTab }, onOpenRun: noop, onContextChange: noop,
      onReadingChange(change) { selectedTab = change.tab; view.update({ reading: { tab: selectedTab } }); } });
    await view.settle();
    view.tree.ref.current = root;
    find("ReportSummary").props.onReadReport("changes");
    await view.settle();
    assert.equal(find("TechnicalReportReading").props.selectedTab, "changes");
    for (const callback of frames.splice(0)) callback();
    assert.deepEqual(focused, [tab], "The selected keyboard tab receives focus without first focusing its section.");
    assert.deepEqual(scrolled, [{ top: 592, behavior: "instant" }]);
    assert.equal(destination.dataset.arrival, "true");
    document.activeElement = editor;
    poll(); await view.settle();
    for (const callback of frames.splice(0)) callback();
    assert.equal(document.activeElement, editor);
    assert.deepEqual(focused, [tab], "Polling does not repeat explicit report navigation.");
    assert.equal(scrolled.length, 1);
  } finally { view?.unmount(); Object.assign(ui.api, originalApi); Object.assign(globalThis, globals); }
});
