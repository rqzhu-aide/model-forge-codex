import test from "node:test";
import assert from "node:assert/strict";

test("authored candidate scope overrides trunk and affected IDs with its exact model version", () => {
  const identity = { stable_id: "method.a", version: 1, definition_sha256: "a".repeat(64) };
  const item = { attention_id: "question.a", phase: "P2", branch: "trunk", affected_record_ids: [], scope: { kind: "model", branch: "branch.a", model_ref: identity } };
  assert.deepEqual(methodRequests([item], "method.b", "branch.b", { includeShared: true, modelRef: { ...identity, stable_id: "method.b" } }), []);
  assert.deepEqual(methodRequests([item], "method.a", "branch.a", { includeShared: true, modelRef: { ...identity, version: 2 } }), []);
  assert.deepEqual(methodRequests([item], "method.a", "branch.a", { modelRef: identity }), [item]);
});
import { catalogMethodForProposal, comparisonCandidates, comparisonForProposal, methodAnswers, methodRequests, modificationOptionsFor, orderedProposals, proposalSectionSource, recordedSelections, successorMethodForProposal, summaryForDisplay } from "../src/methodWorkspace.js";
import { sourceEntry } from "../src/researchContent.js";

test("exact P2 candidates authored on trunk remain visible only on their own model branch", () => {
  const exact = { stable_id: "method.trunk-candidate", version: 1, definition_sha256: "d".repeat(64) };
  const source = { phase: "P2", branch: "trunk", family: "attention_items", generation_id: "attention.exact", sha256: "f".repeat(64), run_id: "run.exact", package_id: "package.exact" };
  const item = { attention_id: "question.trunk-candidate", phase: "P2", branch: "trunk", target_phase: "P4", generation_ref: source, scope: { kind: "model", branch: "trunk", model_ref: exact } };
  const selected = (record = item, modelRef = exact, branch = exact.stable_id) => methodRequests([record], modelRef?.stable_id, branch, { includeShared: true, modelRef });
  assert.deepEqual(selected(), [item]);
  assert.deepEqual(selected(item, exact, "trunk"), [item]);
  assert.deepEqual(selected(item, exact, "branch.unrelated"), []);
  for (const change of [{ stable_id: "method.other" }, { version: 2 }, { definition_sha256: "e".repeat(64) }]) assert.deepEqual(selected(item, { ...exact, ...change }), []);
  for (const change of [{ phase: "P3", target_phase: "P2" }, { branch: "branch.unrelated" }, { generation_ref: { ...source, phase: "P3" } }, { generation_ref: { ...source, branch: "branch.unrelated" } }, { generation_ref: { ...source, family: "theory_review" } }, { generation_ref: { ...source, generation_id: undefined } }, { generation_ref: { ...source, sha256: undefined } }, { generation_ref: { ...source, run_id: undefined } }, { generation_ref: { ...source, package_id: undefined } }, { generation_ref: undefined }, { scope: { ...item.scope, model_ref: { stable_id: exact.stable_id, version: 1 } } }]) assert.deepEqual(selected({ ...item, ...change }), []);
  assert.deepEqual(selected({ ...item, branch: undefined, branch_id: "trunk" }), [], "A legacy branch_id alone does not verify a published P2 origin.");
  for (const change of [{ version: 0 }, { version: -1 }, { version: "1" }, { definition_sha256: "" }]) {
    const invalid = { ...exact, ...change };
    assert.deepEqual(selected({ ...item, scope: { ...item.scope, model_ref: invalid } }, invalid), []);
  }
  const generationOnly = { generation_id: "source.only", sha256: "f".repeat(64) };
  assert.deepEqual(selected({ ...item, scope: { ...item.scope, model_ref: generationOnly } }, generationOnly, exact.stable_id), []);
  const authoredBranch = { ...item, scope: { ...item.scope, branch: "branch.explicit" } };
  assert.deepEqual(selected(authoredBranch), []); assert.deepEqual(selected(authoredBranch, exact, "branch.explicit"), [authoredBranch]);
  assert.deepEqual(methodAnswers([{ attention: item }], exact.stable_id, exact.stable_id, { modelRef: exact }), [{ attention: item }]);
});

const identity = { stable_id: "method.a", version: 1, definition_sha256: "a".repeat(64) };
const proposal = { proposal_id: "proposal.a", generation_ref: { run_id: "run.a" }, method: { identity } };

test("legacy summary spacing does not change equations or ordinary TeX commands", () => {
  const text = String.raw`Mechanism.\n$$\nabla U(x)+\nu=0$$`;
  assert.equal(summaryForDisplay(text), "Mechanism.\n\n" + String.raw`$$\nabla U(x)+\nu=0$$`);
  assert.equal(summaryForDisplay(String.raw`$$\begin{aligned}a&=b\\n&=m\end{aligned}$$`), String.raw`$$\begin{aligned}a&=b\\n&=m\end{aligned}$$`);
  assert.equal(summaryForDisplay(String.raw`Mechanism.\n\[\nabla U(x)+\nu=0\]`), "Mechanism.\n\n" + String.raw`\[\nabla U(x)+\nu=0\]`);
  // Only a literal separator immediately before display math is recovered.
  // Real newlines, other literal separators, inline math and TeX stay authored.
  for (const unchanged of ["Mechanism.\n\n$$x=1$$", String.raw`First\nsecond`, String.raw`Use \nabla and \nu.`, String.raw`Inline.\n$x=1$`, "", null, { summary: "unchanged" }]) {
    assert.equal(summaryForDisplay(unchanged), unchanged);
  }
});

test("legacy summary recovery touches only prose before an opening display equation", () => {
  const protectedText = [
    String.raw`$$x = \\n$$`, // A TeX row break and variable n before a closing delimiter.
    String.raw`$$x=1\n$$`,
    String.raw`\[x = \\n\]`,
    String.raw`$$x + \n$$x=1$$`, // Unbalanced display delimiters stay authored.
    String.raw`\[x=1\n$$x=2$$`,
    String.raw`Literal \\n$$x=1$$`,
    String.raw`Literal \\n\[x=1\]`,
    String.raw`https://example.org/\n$$x=1$$`,
    String.raw`https://example.org/\n $$x=1$$`,
    "`" + String.raw`example\n$$x=1$$` + "`",
    "```text\n" + String.raw`example\n$$x=1$$` + "\n```",
  ];
  for (const text of protectedText) assert.equal(summaryForDisplay(text), text);
  const code = "`" + String.raw`example\n$$x=1$$` + "`";
  const summary = code + String.raw` then compute.\n $$x=1$$ Next.\n\[y=2\]`;
  assert.equal(summaryForDisplay(summary), code + " then compute.\n\n $$x=1$$ Next.\n\n" + String.raw`\[y=2\]`);
  assert.equal(summary, code + String.raw` then compute.\n $$x=1$$ Next.\n\[y=2\]`);
});

test("continuation uses the inspected exact method identity, not another version or matching title", () => {
  const old = { method_id: "method.a", identity: { ...identity, version: 2 }, title: "Same title" };
  const exact = { method_id: "method.a", identity, branch_id: "custom.branch" };
  assert.equal(catalogMethodForProposal(proposal, [old, exact]), exact);
  assert.equal(catalogMethodForProposal(proposal, [old]), undefined);
  assert.equal(catalogMethodForProposal({ method: {} }, [{ identity: {} }]), undefined);
});

test("an earlier proposal is superseded only when its stable id lives on under a different identity", () => {
  const retained = { method_id: "method.a", identity };
  const revised = { method_id: "method.a", identity: { ...identity, version: 2, definition_sha256: "b".repeat(64) } };
  // Exact catalog match: retained, never superseded, regardless of proposal age.
  assert.equal(successorMethodForProposal(proposal, [retained]), null);
  // Same stable id under a different version or definition: superseded history.
  assert.equal(successorMethodForProposal(proposal, [revised]), revised);
  // An exact match anywhere takes precedence: the proposal is the current definition.
  assert.equal(successorMethodForProposal(proposal, [retained, revised]), null);
  // No stable-id match: simply absent from the catalog, not superseded.
  assert.equal(successorMethodForProposal(proposal, [{ method_id: "method.b", identity: { stable_id: "method.b", version: 1, definition_sha256: "c".repeat(64) } }]), null);
  assert.equal(successorMethodForProposal({ method: {} }, [revised]), null);
});

test("lead assessment is joined to the producing run as well as proposal id", () => {
  const old = { generation_ref: { run_id: "run.old" }, method_dispositions: [{ proposal_id: "proposal.a", rationale: "Old claim" }] };
  const exact = { generation_ref: { run_id: "run.a" }, method_dispositions: [{ proposal_id: "proposal.a", rationale: "Reviewed claim" }] };
  assert.equal(comparisonForProposal(proposal, [old, exact]).disposition.rationale, "Reviewed claim");
  assert.equal(comparisonForProposal(proposal, [old]), null);
});

test("section sources resolve the selected model's exact paragraph without changing the original reference", () => {
  const reference = { run_id: "run.a", generation_id: "gen.exact", sha256: "c".repeat(64) };
  for (const [collection, field] of [["method_dispositions", "method_summary_markdown"], ["method_dispositions", "rationale"], ["assessments", "applicability_markdown"]]) {
    const record = { generation_ref: reference, [collection]: [
      { proposal_id: "proposal.other", [field]: "Other method" },
      { proposal_id: "proposal.a", [field]: "The selected model's authored paragraph." },
    ] };
    const ref = proposalSectionSource(record, "proposal.a", collection, field);
    assert.equal(ref.entry_pointer, `/${collection}/1/${field}`);
    assert.equal(ref.generation_id, reference.generation_id);
    assert.equal(sourceEntry(record, ref.entry_pointer), record[collection][1][field]);
    assert.equal(reference.entry_pointer, undefined);
    assert.equal(proposalSectionSource(record, "proposal.absent", collection, field), null);
    assert.equal(proposalSectionSource(record, "proposal.a", collection, "missing_field"), null);
  }
  assert.equal(proposalSectionSource(null, "proposal.a", "assessments", "applicability_markdown"), null);
});

test("legacy assessment text is not relabeled as an authored applicability paragraph", () => {
  const generation_ref = { run_id: "run.legacy", generation_id: "gen.legacy" };
  for (const applicability_markdown of [undefined, "", " \n\t"]) {
    const record = { generation_ref, assessments: [{ proposal_id: "proposal.a", applicability_markdown,
      assessment_markdown: "The original audit discusses applicability here." }] };
    assert.equal(proposalSectionSource(record, "proposal.a", "assessments", "applicability_markdown"), null);
    assert.deepEqual(proposalSectionSource(record, "proposal.a", "assessments", "assessment_markdown"),
      { ...generation_ref, entry_pointer: "/assessments/0/assessment_markdown" });
  }
});

test("questions and saved answers remain method local across P2, P3 and P4 destinations", () => {
  const own = { branch: "trunk", phase: "P2", target_phase: "P3", affected_record_ids: ["method.a"], attention_id: "own" };
  const other = { ...own, target_phase: "P4", affected_record_ids: ["method.b"], attention_id: "other" };
  const both = { ...own, affected_record_ids: ["method.a", "method.b"], attention_id: "both" };
  const shared = { ...own, affected_record_ids: [], attention_id: "shared" };
  const setting = { ...own, phase: "P1", affected_record_ids: ["setting.record"], attention_id: "setting" };
  const branch = { ...own, branch: "custom.branch", phase: "P3", affected_record_ids: ["theorem.1"], attention_id: "branch" };
  const items = [own, other, both, shared, setting, branch];
  assert.deepEqual(methodRequests(items, "method.a", "custom.branch").map((item) => item.attention_id), ["own", "both", "branch"]);
  assert.deepEqual(methodRequests(items, "method.a", "custom.branch", { includeShared: true }).map((item) => item.attention_id), ["own", "both", "shared", "setting", "branch"]);
  const answers = items.map((attention) => ({ note: `Answer ${attention.attention_id}`, attention }));
  assert.deepEqual(methodAnswers(answers, "method.b", "branch.b").map((answer) => answer.note), ["Answer other", "Answer both"]);
});

test("role ordering does not alter the author's proposal or source records", () => {
  const source = [{ role: "data_analyst" }, { role: "research_lead" }, { role: "theorist" }];
  const before = JSON.stringify(source);
  assert.deepEqual(orderedProposals(source).map((item) => item.role), ["research_lead", "theorist", "data_analyst"]);
  assert.equal(JSON.stringify(source), before);
});


test("selection rows join dispositions to proposals by id and producing run", () => {
  const current = { proposal_id: "proposal.a", generation_ref: { run_id: "run.new" } };
  const stale = { proposal_id: "proposal.a", generation_ref: { run_id: "run.old" } };
  const other = { proposal_id: "proposal.b", generation_ref: { run_id: "run.new" } };
  const comparison = { generation_ref: { run_id: "run.new" }, method_dispositions: [
    { proposal_id: "proposal.a", status: "retain", rationale: "Kept" },
    { proposal_id: "proposal.b", status: "exclude", rationale: "Dropped" },
    { proposal_id: "proposal.missing", status: "retain", rationale: "No proposal" },
  ] };
  assert.deepEqual(comparisonCandidates(comparison, [stale, current, other]), [{ disposition: comparison.method_dispositions[0], proposal: current }]);
  assert.deepEqual(comparisonCandidates(comparison, [stale, current, other], "exclude"), [{ disposition: comparison.method_dispositions[1], proposal: other }]);
  assert.deepEqual(comparisonCandidates(null, [current]), []);
  assert.deepEqual(comparisonCandidates({ method_dispositions: [{ proposal_id: "proposal.a", status: "retain" }] }, [stale]), [{ disposition: { proposal_id: "proposal.a", status: "retain" }, proposal: stale }]);
});

test("modification options name their exact proposal and stay absent for legacy assessments", () => {
  const options = [{ option_id: "mod.a.x", applies_to: "proposal.a" }, { option_id: "mod.b.x", applies_to: "proposal.b" }];
  assert.deepEqual(modificationOptionsFor({ modification_options: options }, "proposal.a"), [options[0]]);
  assert.deepEqual(modificationOptionsFor({ modification_options: options }, "proposal.missing"), []);
  assert.deepEqual(modificationOptionsFor({}, "proposal.a"), []);
  assert.deepEqual(modificationOptionsFor(undefined, "proposal.a"), []);
});

test("a recorded selection requires a registered catalog entry with the exact identity", () => {
  const proposalA = { proposal_id: "p.a", method: { identity } };
  const registered = { method_id: "method.a", identity, registered: true };
  const unregistered = { method_id: "method.a", identity, registered: false };
  const otherVersion = { method_id: "method.a", identity: { ...identity, version: 2 }, registered: true };
  assert.deepEqual(recordedSelections([proposalA], [registered]), [registered]);
  assert.deepEqual(recordedSelections([proposalA], [unregistered]), []);
  assert.deepEqual(recordedSelections([proposalA], [otherVersion]), []);
  assert.deepEqual(recordedSelections([proposalA, proposalA], [registered]), [registered]);
  assert.deepEqual(recordedSelections([], [registered]), []);
});
