import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { correctionDispositions, hasSharedNotation, notationCorrectionApplies, notationEntrySources, notationEntryTarget, notationGroups, notationReference } from "../src/sharedNotation.js";
import { phaseInputSummary } from "../src/phaseInputSummary.js";
import { changedStudy, createCorrectionFixture, methodIdentity, records, refs, snapshots } from "./fixtures/shared-notation.mjs";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-notation-"));
const bundle = path.join(directory, "test.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; export {NotationLookup,NotationContent,NotationDialog,NotationCorrection,NotationSource} from '${src}/components/SharedNotation.jsx'; export {TechnicalReportDocument,ReportMaterialLink} from '${src}/components/TechnicalReportReading.jsx'; export {default as EmpiricalWorkbench} from '${src}/components/EmpiricalWorkbench.jsx'; export {default as ResearcherDialogue} from '${src}/components/ResearcherDialogue.jsx'; export {default as MethodProposals} from '${src}/components/MethodProposals.jsx'; export {Dialog,ResearchDocument} from '${src}/components/Shared.jsx'; export const render=(Component,props)=>renderToStaticMarkup(React.createElement(Component,props)); export const dispatcher=React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher;`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const nodes = (tree) => Array.isArray(tree) ? tree.flatMap(nodes) : tree && typeof tree === "object" && tree.props ? [tree, ...nodes(tree.props.children)] : [];
const find = (tree, predicate) => nodes(tree).find(predicate);
const noop = () => {};
const json = (data, status = 200) => ({ ok: status < 400, status, json: async () => data });
function mount(Component, props, context = {}) {
  const slots = []; let cursor = 0; let pending = []; let dirty = true; let tree;
  const state = (initial) => { const index = cursor++; if (!slots[index]) slots[index] = { value: typeof initial === "function" ? initial() : initial }; return [slots[index].value, (update) => { const next = typeof update === "function" ? update(slots[index].value) : update; if (!Object.is(next, slots[index].value)) { slots[index].value = next; dirty = true; } }]; };
  const effect = (run, dependencies) => { const index = cursor++; const old = slots[index]; if (!old || dependencies.some((value, offset) => !Object.is(value, old.dependencies?.[offset]))) { slots[index] = { dependencies, cleanup: old?.cleanup }; pending.push({ index, run }); } };
  const hooks = { useState: state, useEffect: effect, useLayoutEffect: effect, useContext: () => context, useRef: (initial) => { const index = cursor++; return (slots[index] ||= { value: { current: initial } }).value; }, useId: () => { const index = cursor++; return (slots[index] ||= { value: "notation:fixture" }).value; } };
  const draw = () => { cursor = 0; pending = []; dirty = false; const previous = ui.dispatcher.current; try { ui.dispatcher.current = hooks; tree = Component(props); } finally { ui.dispatcher.current = previous; } for (const { index, run } of pending) { slots[index].cleanup?.(); slots[index].cleanup = run(); } };
  return { get tree() { return tree; }, update(changes) { props = { ...props, ...changes }; dirty = true; }, async settle() { for (let i = 0; i < 25; i++) { if (dirty) draw(); await new Promise((resolve) => setImmediate(resolve)); if (!dirty) return tree; } throw new Error("Notation reader did not settle."); }, unmount() { for (const slot of slots) slot?.cleanup?.(); } };
}

test("complete views keep same-letter quantities distinct, with account then method then study and collapsed inherited scopes", () => {
  const before = structuredClone(snapshots.P5);
  const groups = notationGroups(snapshots.P5);
  assert.deepEqual(groups.map((group) => group.rank), [0, 1, 2, 3, 3]);
  assert.equal(groups[0].entries[0].symbol_latex, "h");
  assert.equal(groups.filter((group) => group.collapsed).flatMap((group) => group.entries).filter((entry) => entry.symbol_latex === "\\kappa").length, 2);
  assert.equal(notationGroups(snapshots.P5, { section: "problem" }).find((group) => group.entries.some((entry) => entry.entry_id === "report_bandwidth")).collapsed, true);
  assert.equal(notationGroups(snapshots.P3, { section: "proof" })[0].entries[0].entry_id, "moment_bound");
  assert.deepEqual(snapshots.P5, before);
});

test("an explicit selected-method view preserves shared definitions and the exact catalog source", () => {
  const original = snapshots.P2.entries.at(-1);
  const otherIdentity = { stable_id: "method.other", version: 1, definition_sha256: "f".repeat(64) };
  const other = { ...original, entry_id: "other_penalty", meaning_markdown: "OTHER_METHOD_MEANING", scope: { kind: "method", method_identity: otherIdentity } };
  const changedDefinition = { ...other, entry_id: "other_version", scope: { kind: "method", method_identity: { ...methodIdentity, definition_sha256: "e".repeat(64) } } };
  const snapshot = { ...snapshots.P2, account: { ...snapshots.P2.account, method_identity: undefined }, entries: [...snapshots.P2.entries, other, changedDefinition] };
  const record = { ...records.P2, _notation: snapshot };
  const before = structuredClone(record);
  const groups = notationGroups(snapshot, { methodScope: methodIdentity });
  assert.deepEqual(groups.map(group => group.label), ["Method notation", "Shared study"]);
  assert.deepEqual(groups.flatMap(group => group.entries).map(entry => entry.entry_id).sort(), snapshots.P2.entries.map(entry => entry.entry_id).sort());
  assert.equal(notationGroups(snapshot).flatMap(group => group.entries).length, snapshot.entries.length);
  const html = ui.render(ui.NotationContent, { record, methodScope: methodIdentity, onSource: noop });
  assert.equal((html.match(/data-notation-entry=/g) || []).length, snapshots.P2.entries.length);
  assert.match(html, /Definitions for this method and the shared study/);
  assert.doesNotMatch(html, /OTHER_METHOD_MEANING|data-notation-entry="other_/);
  assert.deepEqual(notationReference(record), refs.P2);
  assert.deepEqual(notationEntryTarget(snapshot, original, notationReference(record)).snapshot_sha256, snapshot.snapshot_sha256);
  assert.deepEqual(record, before);
});

test("the selected P2 accounts pass their exact method scope while comparison notation remains explicit", async () => {
  const proposal = { proposal_id: "proposal.exact", role: "research_lead", generation_ref: refs.proposal, method: { title: "Conditional method", identity: methodIdentity, summary: "An original conditional proposal." } };
  const comparison = { ...records.P2, catalog_pin: { catalog_version: "1.24.0", catalog_manifest_sha256: "a".repeat(64) }, overview_markdown: "Compare the conditional candidates.", method_dispositions: [{ proposal_id: proposal.proposal_id, status: "retain", method_summary_markdown: "This candidate supports the stated conditional analysis." }] };
  const direct = ui.MethodProposals({ proposals: [proposal], comparisons: [comparison] });
  const explore = direct.type(direct.props).props.children;
  const fixture = mount(explore.type, explore.props); await fixture.settle();
  const lookups = nodes(fixture.tree).filter(node => node.type === ui.NotationLookup);
  assert.equal(lookups.length, 2);
  assert.ok(lookups.every(node => node.props.methodScope === methodIdentity));
  assert.equal(lookups[0].props.record, comparison, "Concise Lead account keeps the immutable catalog source.");
  const overview = find(fixture.tree, node => node.type?.name === "MethodComparison");
  const overviewLookup = find(overview.type(overview.props), node => node.type === ui.NotationLookup);
  assert.equal(overviewLookup.props.methodScope, undefined);
  assert.equal(overviewLookup.props.label, "Notation for all methods");
  fixture.unmount();
});

test("an open method lookup retains its original display scope with its source", async () => {
  const other = { ...methodIdentity, definition_sha256: "f".repeat(64) };
  const newerRef = { ...refs.P2, generation_id: "P2.catalog.changed" };
  const newerRecord = { ...records.P2, generation_ref: newerRef, _notation: { ...snapshots.P2, source_ref: newerRef } };
  const fixture = mount(ui.NotationLookup, { record: records.P2, methodScope: methodIdentity }); await fixture.settle();
  find(fixture.tree, node => node.props.children === "Notation").props.onClick(); await fixture.settle();
  fixture.update({ methodScope: other, record: newerRecord }); await fixture.settle();
  const dialog = find(fixture.tree, node => node.type === ui.NotationDialog);
  assert.equal(dialog.props.record, records.P2);
  assert.equal(dialog.props.methodScope, methodIdentity);
  const dialogFixture = mount(ui.NotationDialog, dialog.props); await dialogFixture.settle();
  assert.equal(find(dialogFixture.tree, node => node.type === ui.NotationContent).props.methodScope, methodIdentity);
  dialogFixture.unmount();
  dialog.props.onViewNewer(); await fixture.settle();
  assert.equal(find(fixture.tree, node => node.type === ui.NotationDialog).props.methodScope, other);
  fixture.unmount();
});

test("account-local groups follow their original scope source across reruns and clarifications", () => {
  const original = snapshots.P3.entries.at(-1);
  const scope = { ...original.scope }; delete scope.run_id;
  const source = { phase: "P3", branch: refs.P3.branch, family: refs.P3.family, output_id: "p3.complete_theory", stage_id: "p3.synthesis", run_id: "run.original" };
  const current = { ...source, run_id: "run.current" };
  const older = { ...original, scope, account_scope_ref: source, adoption_ref: current };
  const fresh = { ...original, scope, entry_id: "fresh", account_scope_ref: current, adoption_ref: current };
  const unrelated = { ...older, entry_id: "another-run", account_scope_ref: { ...source, run_id: "run.another" } };
  const snapshot = { ...snapshots.P3, account: { ...snapshots.P3.account, run_id: current.run_id, stage_id: current.stage_id }, entries: [older, fresh, unrelated] };
  const groups = notationGroups(snapshot);
  assert.deepEqual(groups.map(group => group.rank), [0, 3, 3]);
  assert.equal(groups[0].entries[0].entry_id, "fresh");
  assert.equal(groups[1].label, "Theory · Proof");
  assert.notEqual(groups[1].key, groups[2].key);
  const legacy = { ...older, adoption_ref: source }; delete legacy.account_scope_ref;
  assert.equal(notationGroups({ ...snapshot, entries: [legacy] })[0].rank, 3);
});

test("only an explicit account snapshot enables shared lookup; exact source and entry targets retain generation and hash", () => {
  assert.equal(hasSharedNotation({ generation_ref: refs.P1, research_setting: { component_interpretations: [{}] } }), false);
  assert.equal(hasSharedNotation({ generation_ref: refs.P1, notation_snapshot: { path: "notation.json" } }), true);
  assert.equal(hasSharedNotation({ notation_snapshot: { path: "notation.json" } }), false);
  assert.deepEqual(notationReference({ ...records.P3, generation_ref: { ...refs.P3, family: "claim_map" }, notation_source_ref: refs.P3 }), refs.P3);
  assert.deepEqual(notationReference({ ...records.P1, generation_ref: { ...refs.P1, entry_pointer: "/research_setting" } }), refs.P1);
  const target = notationEntryTarget(snapshots.P4, snapshots.P4.entries.at(-1), refs.P4);
  assert.equal(target.kind, "notation_entry"); assert.equal(target.snapshot_sha256, snapshots.P4.snapshot_sha256); assert.equal(target.entry_id, "bandwidth");
  assert.equal(target.generation_id, refs.P4.generation_id); assert.equal(target.sha256, refs.P4.sha256);
  assert.equal(notationEntryTarget({ ...snapshots.P4, snapshot_sha256: undefined }, snapshots.P4.entries.at(-1), refs.P4), null);
  assert.equal(notationEntrySources(snapshots.P4.entries.at(-1)).length, 2, "Definition pointer and adoption account remain separately reachable.");
  assert.deepEqual(notationEntrySources({ ui_source_refs: [{ generation_ref: refs.P3, pointer: "/statements/0" }], definition_ref: { output_id: "p3.complete_theory" } }), [{ ...refs.P3, entry_pointer: "/statements/0" }]);
});

test("an open lookup keeps the original account through publication polling", async () => {
  const fixture = mount(ui.NotationLookup, { record: records.P1 }); await fixture.settle();
  find(fixture.tree, (node) => node.props.children === "Notation").props.onClick(); await fixture.settle();
  fixture.update({ record: changedStudy }); await fixture.settle();
  const opened = find(fixture.tree, (node) => node.type === ui.NotationDialog);
  assert.equal(opened.props.record, records.P1);
  assert.equal(opened.props.newerRecord, changedStudy);
  assert.equal(opened.props.record._notation.entries.find((entry) => entry.entry_id === "target").symbol_latex, "\\mu_D");
  fixture.update({ record: { generation_ref: changedStudy.generation_ref } }); await fixture.settle();
  assert.equal(find(fixture.tree, (node) => node.type === ui.NotationDialog).props.record, records.P1);
  assert.equal(find(fixture.tree, (node) => node.type === ui.NotationDialog).props.newerRecord, null);
  fixture.update({ record: changedStudy }); await fixture.settle();
  find(fixture.tree, (node) => node.type === ui.NotationDialog).props.onViewNewer(); await fixture.settle();
  assert.equal(find(fixture.tree, (node) => node.type === ui.NotationDialog).props.record, changedStudy);
  assert.equal(find(fixture.tree, (node) => node.type === ui.NotationDialog).props.newerRecord, null);
});

test("explicitly viewing newer definitions announces availability and restores focus inside the retained dialog", async () => {
  const fixture = mount(ui.NotationDialog, { record: records.P1, newerRecord: changedStudy, onViewNewer: noop, onClose: noop }); await fixture.settle();
  assert.ok(find(fixture.tree, node => node.props.role === "status"));
  assert.ok(find(fixture.tree, node => node.props.children === "View newer definitions"));
  const region = find(fixture.tree, node => node.props["aria-label"] === "Notation definitions");
  let focused = 0; region.ref.current = { focus: () => { focused++; } };
  const previous = find(fixture.tree, node => node.type === ui.NotationContent);
  fixture.update({ record: changedStudy, newerRecord: null }); await fixture.settle();
  const current = find(fixture.tree, node => node.type === ui.NotationContent);
  assert.notEqual(current.key, previous.key);
  assert.equal(current.props.record, changedStudy);
  assert.equal(focused, 1);
  assert.equal(find(fixture.tree, node => node.props.role === "status"), undefined);
});

test("lazy lookup asks only for the selected exact account and never falls back after source failure", async () => {
  const originalFetch = globalThis.fetch; const requests = [];
  globalThis.fetch = async (url) => { requests.push(url); return json({ detail: "The retained notation is missing." }, 404); };
  try {
    const fixture = mount(ui.NotationContent, { record: { generation_ref: refs.P3, notation_snapshot: {} } }, { projectId: "synthetic" });
    await fixture.settle();
    assert.equal(requests.length, 1);
    assert.deepEqual(JSON.parse(new URL(requests[0], "http://fixture").searchParams.get("source")), refs.P3);
    assert.ok(find(fixture.tree, (node) => node.props.role === "alert"));
    assert.equal(requests.some((url) => /latest|current/.test(url)), false);
    fixture.unmount();
  } finally { globalThis.fetch = originalFetch; }
});

test("rendered lookup preserves mathematical definitions and scoped source correspondence without copying legacy glossaries", () => {
  const html = ui.render(ui.NotationContent, { record: records.P5 });
  assert.match(html, /Definitions used in this result/);
  assert.match(html, /Source symbol correspondence/);
  assert.match(html, /fourth-moment bound/); assert.match(html, /bandwidth/);
  assert.equal((html.match(/data-notation-entry=/g) || []).length, snapshots.P5.entries.length);
  assert.match(html, /<details class="research-details notation-scope"><summary>Theory · Proof/);
  assert.match(html, /<h3>Report · Numerical analysis<\/h3>/);
  assert.doesNotMatch(html, /This account|numerical_analysis<\/h3>|<summary>P3/);
  assert.match(html, /<dl class="notation-entries">/);
});

test("source labels follow explicit roles when one source is absent and several scientific sources remain", () => {
  const entry = { ...snapshots.P4.entries.at(-1), definition_ref: undefined, adoption_ref: undefined, source_refs: [], ui_source_refs: [
    { generation_ref: refs.P4, entry_pointer: "/adoption", source_role: "adoption" },
    { generation_ref: refs.P3, entry_pointer: "/proof", source_role: "scientific" },
    { generation_ref: refs.P1, entry_pointer: "/setting", source_role: "scientific" },
  ] };
  assert.deepEqual(notationEntrySources(entry).map(source => source.source_role), ["adoption", "scientific", "scientific"]);
  const html = ui.render(ui.NotationContent, { record: { ...records.P4, _notation: { ...snapshots.P4, entries: [entry] } } });
  assert.doesNotMatch(html, />Definition source<\/button>/);
  assert.equal((html.match(/>Adoption source<\/button>/g) || []).length, 1);
  assert.equal((html.match(/>Scientific source<\/button>/g) || []).length, 2);
});

test("correction saves one effective owner with exact target and context revision, then remains editable", async () => {
  const originalFetch = globalThis.fetch; const requests = [];
  const target = notationEntryTarget(snapshots.P4, snapshots.P4.entries.at(-1), refs.P4);
  const savedItem = { item_id: "context.notation.owner", revision: 2, statement: "Use a clearly identified bandwidth scale.", history: [{ revision: 1, statement: "Earlier correction." }] };
  globalThis.fetch = async (url, options) => { requests.push({ url, options }); return options.method === "PUT" ? json({ context_revision: 9, item: savedItem, disposition: null }) : json({ context_revision: 8, item: { ...savedItem, revision: 1, statement: "Earlier correction." }, disposition: null }); };
  try {
    const fixture = mount(ui.NotationCorrection, { target, entry: snapshots.P4.entries.at(-1), projectId: "synthetic", onClose: noop }); await fixture.settle();
    assert.ok(find(fixture.tree, (node) => node.props.children === "Your correction is saved for future work."));
    assert.equal(find(fixture.tree, (node) => node.props.children === "Save to use this update in future work. Work already started keeps its original inputs."), undefined);
    const textarea = find(fixture.tree, (node) => node.type === "textarea");
    textarea.props.onChange({ target: { value: savedItem.statement } }); await fixture.settle();
    assert.ok(find(fixture.tree, (node) => node.props.children === "Save to use this update in future work. Work already started keeps its original inputs."));
    await find(fixture.tree, (node) => node.type === "form").props.onSubmit({ preventDefault() {} }); await fixture.settle();
    assert.deepEqual(JSON.parse(requests[1].options.body), { target, statement: savedItem.statement, expected_revision: 8 });
    assert.ok(find(fixture.tree, (node) => node.props.role === "status" && node.props.children === "Correction saved for future work."));
    find(fixture.tree, (node) => node.type === "textarea").props.onChange({ target: { value: "Edited but unsaved." } }); await fixture.settle();
    assert.equal(find(fixture.tree, (node) => node.props.children === "Correction saved for future work."), undefined);
    assert.equal(requests.length, 2);
    fixture.unmount();
  } finally { globalThis.fetch = originalFetch; }
});

test("retrying a correction load clears the earlier error after a successful exact-source load", async () => {
  const originalFetch = globalThis.fetch; let reads = 0;
  globalThis.fetch = async () => { if (++reads === 1) throw new Error("Synthetic temporary read failure."); return json({ context_revision: 2, item: { statement: "The saved correction." } }); };
  try {
    const fixture = mount(ui.NotationCorrection, { target: notationEntryTarget(snapshots.P4, snapshots.P4.entries.at(-1), refs.P4), entry: snapshots.P4.entries.at(-1), projectId: "retry-fixture", onClose: noop }); await fixture.settle();
    assert.ok(find(fixture.tree, node => node.props.role === "alert"));
    find(fixture.tree, node => node.props.children === "Retry").props.onClick(); await fixture.settle();
    assert.equal(find(fixture.tree, node => node.props.role === "alert"), undefined);
    assert.equal(find(fixture.tree, node => node.type === "textarea").props.value, "The saved correction.");
    fixture.unmount();
  } finally { globalThis.fetch = originalFetch; }
});

test("inherited study and method corrections explain the phase binding without relabeling their saved source", async () => {
  const originalFetch = globalThis.fetch;
  const text = value => Array.isArray(value) ? value.map(text).join("") : value && typeof value === "object" ? text(value.props?.children) : String(value ?? "");
  try {
    for (const [phase, id, definitionPhase] of [["P4", "target", "P1"], ["P5", "ridge_penalty", "P2"], ["P1", "target", "P1"], ["P2", "ridge_penalty", "P2"], ["P4", "bandwidth", null]]) {
      const entry = snapshots[phase].entries.find(entry => entry.entry_id === id);
      const target = notationEntryTarget(snapshots[phase], entry, refs[phase]);
      const savedPhase = definitionPhase || phase;
      const savedSource = notationEntryTarget(snapshots[savedPhase], snapshots[savedPhase].entries.find(entry => entry.entry_id === id), refs[savedPhase]);
      globalThis.fetch = async () => json({ context_revision: 3, item: { statement: "The existing saved correction.", source_refs: [savedSource] } });
      const fixture = mount(ui.NotationCorrection, { target, entry, projectId: "phase-routing-fixture", onClose: noop }); await fixture.settle();
      const notice = find(fixture.tree, node => node.props.className === "note notation-correction-routing");
      if (definitionPhase && phase !== definitionPhase) {
        assert.match(text(notice), /Saving here links your correction to the Phase [45]/);
        assert.ok(text(notice).includes(`To include it in a Phase ${definitionPhase.slice(1)}`));
        assert.match(text(notice), /edit it from that phase’s notation view/);
      } else assert.equal(notice, undefined);
      assert.deepEqual(find(fixture.tree, node => node.props.label === "Source addressed by saved correction").props.reference, savedSource);
      assert.equal(find(fixture.tree, node => node.type === "textarea").props.value, "The existing saved correction.");
      fixture.unmount();
    }
  } finally { globalThis.fetch = originalFetch; }
});

test("adoption outcomes are tied to the exact correction revision and all applicable published outcomes remain visible", () => {
  const item = { revision: 3 };
  assert.deepEqual(correctionDispositions({ item, disposition: { correction_ref: { revision: 2 }, disposition: "adopted" } }), []);
  assert.deepEqual(correctionDispositions({ item, disposition: { disposition: "adopted" } }), []);
  const dispositions = ["adopted", "unchanged", "scientific_revision"].map((disposition) => ({ correction_ref: { revision: 3 }, disposition, reason_markdown: "Source-owned explanation.", source_ref: refs.P5 }));
  assert.deepEqual(correctionDispositions({ item, dispositions }).map((outcome) => outcome.label), ["Adopted in later work", "Definition retained", "Referred for scientific revision"]);
});

test("saved correction mirrors count once and respect source phase and method scope", () => {
  const item = { item_id: "context.notation.owner", revision: 1, status: "confirmed", scope: { kind: "project" }, topic: "notation_correction", statement: "Retain the bandwidth scale.", source_refs: [notationEntryTarget(snapshots.P4, snapshots.P4.entries.at(-1), refs.P4)] };
  const input = { projectId: "fixture", branch: refs.P4.branch, phase: "P4", problemContext: { items: [item] }, modelRef: methodIdentity };
  assert.equal(phaseInputSummary(input).understanding.saved, 1);
  assert.equal(phaseInputSummary({ ...input, phase: "P2" }).understanding.saved, 0);
  assert.equal(phaseInputSummary({ ...input, phase: "P3" }).understanding.saved, 1);
  assert.equal(notationCorrectionApplies({ ...item, notation_scope: { kind: "method", method_identity: { ...methodIdentity, definition_sha256: "changed" } } }, input), false);
  for (const kind of ["method", "account"]) {
    const scope = { kind, method_identity: methodIdentity, branch: input.branch };
    const scopedItem = { ...item, source_refs: [{ ...item.source_refs[0], notation_scope: scope }] };
    assert.equal(notationCorrectionApplies(scopedItem, input), true);
    assert.equal(notationCorrectionApplies(scopedItem, { ...input, modelRef: { ...methodIdentity, definition_sha256: "changed" } }), false);
  }
});

test("a newer P1 source without the original entry excludes its correction from the next run count and mirrors", () => {
  const correction = { item_id: "context.notation.study", revision: 1, status: "confirmed", scope: { kind: "project" }, topic: "notation_correction", statement: "Keep the original donor averaging unit.", source_refs: [{ ...notationEntryTarget(snapshots.P1, snapshots.P1.entries[2], refs.P1), notation_scope: { kind: "study" } }] };
  const ordinary = { item_id: "context.ordinary", revision: 1, status: "confirmed", scope: { kind: "project" }, statement: "The donor labels will arrive later." };
  const input = { projectId: "fixture", branch: "trunk", phase: "P2", problemContext: { items: [correction, ordinary] }, admittedRecords: [{ ...refs.P1, content_sha256: refs.P1.sha256 }] };
  assert.equal(phaseInputSummary(input).understanding.saved, 2);
  for (const field of ["phase", "branch", "family", "generation_id", "content_sha256"]) {
    const admittedRecords = [{ ...input.admittedRecords[0], [field]: "different" }];
    assert.equal(phaseInputSummary({ ...input, admittedRecords }).understanding.saved, 1, field);
  }
  const after = { ...input, admittedRecords: [changedStudy.generation_ref] };
  assert.deepEqual(phaseInputSummary(after).understanding.items.map(({ item }) => item.item_id), [ordinary.item_id]);
  const html = ui.render(ui.ResearcherDialogue, after);
  assert.doesNotMatch(html, /Keep the original donor averaging unit/);
  assert.match(html, /The donor labels will arrive later/);
  assert.equal(phaseInputSummary({ ...input, admittedRecords: [] }).understanding.saved, 1);
});

test("an admitted inherited entry carries its note without granting a later phase source upstream admission", () => {
  const correction = { item_id: "context.notation.inherited", revision: 1, status: "confirmed", scope: { kind: "project" }, topic: "notation_correction", statement: "Keep the donor target explicit.", source_refs: [{ ...notationEntryTarget(snapshots.P1, snapshots.P1.entries[2], refs.P1), notation_scope: { kind: "study" } }] };
  const input = { projectId: "fixture", phase: "P2", branch: "trunk", problemContext: { items: [correction] }, admittedRecords: [changedStudy.generation_ref], admittedNotation: { entries: [{ entry_id: "target", status: "retired" }] } };
  assert.equal(phaseInputSummary(input).understanding.saved, 1);
  assert.equal(phaseInputSummary({ ...input, admittedNotation: { entries: [{ entry_id: "different", quantity_key: "target" }] } }).understanding.saved, 0);
  const p4Origin = { ...correction, source_refs: [{ ...notationEntryTarget(snapshots.P4, snapshots.P4.entries.find(entry => entry.entry_id === "target"), refs.P4), notation_scope: { kind: "study" } }] };
  assert.equal(phaseInputSummary({ ...input, problemContext: { items: [p4Origin] } }).understanding.saved, 0);
  assert.equal(phaseInputSummary({ ...input, phase: "P4", branch: refs.P4.branch, problemContext: { items: [p4Origin] } }).understanding.saved, 1);
  assert.equal(phaseInputSummary({ ...input, phase: "P4", branch: "method.other", problemContext: { items: [p4Origin] } }).understanding.saved, 0);
});

test("synthetic corrections count owners and retain independent entries plus inherited history", () => {
  const fixture = createCorrectionFixture();
  const target = (phase, id) => notationEntryTarget(snapshots[phase], snapshots[phase].entries.find(entry => entry.entry_id === id), refs[phase]);
  const donor = target("P1", "target");
  const first = fixture.save({ target: donor, statement: "Keep donor weighting explicit.", expected_revision: fixture.load(donor).context_revision });
  assert.equal(fixture.count, 1);
  const inherited = target("P4", "target");
  assert.equal(fixture.load(inherited).item.item_id, first.item.item_id);
  const edited = fixture.save({ target: inherited, statement: "Each donor has equal weight.", expected_revision: first.context_revision });
  assert.equal(fixture.count, 1);
  assert.equal(edited.item.revision, 2);
  assert.equal(edited.item.history[0].statement, first.item.statement);
  assert.equal(edited.item.source_refs[0].phase, "P4");
  const bandwidth = target("P4", "bandwidth");
  assert.equal(fixture.load(bandwidth).item, null);
  fixture.save({ target: bandwidth, statement: "Clarify the smoothing scale.", expected_revision: edited.context_revision });
  assert.equal(fixture.count, 2);
  assert.equal(fixture.load(donor).item.statement, edited.item.statement);
  const cell = notationEntryTarget(changedStudy._notation, changedStudy._notation.entries.find(entry => entry.entry_id === "target_cell"), changedStudy.generation_ref);
  assert.equal(fixture.load(cell).item, null);
  assert.throws(() => fixture.save({ target: donor, statement: "Stale editor", expected_revision: first.context_revision }), error => error.status === 409);
});

test("report support lookup carries its exact retained report and can override it with canonical proof notation", () => {
  const material = { artifact_id: "proof", authored_path: "proof.md", artifact_url: "/api/fixture/proof", source_verified: true, media_type: "text/markdown", generation_ref: refs.P3, _notation: snapshots.P3 };
  const document = { ...records.P5, kind: "technical_report", body_md: "Read [proof](proof.md).", report_materials: [material] };
  const tree = ui.TechnicalReportDocument({ document });
  const body = find(tree, (node) => node.type === ui.ResearchDocument && node.props.renderFileLink);
  const link = body.props.renderFileLink("proof.md", "proof");
  assert.equal(link.type, ui.ReportMaterialLink); assert.equal(link.props.notationRecord, document);
  assert.equal(link.props.material._notation, snapshots.P3);
});
