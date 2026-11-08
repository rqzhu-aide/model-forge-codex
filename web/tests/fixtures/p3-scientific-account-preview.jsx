import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { api } from "../../src/api";
import { PhaseOverview, TheoryReading } from "../../src/components/PhaseReading";
import PhaseInputSummary from "../../src/components/PhaseInputSummary";
import ResearcherDialogue from "../../src/components/ResearcherDialogue";
import { IssueEntry } from "../../src/components/IssuesCard";
import { Dialog, ResearchDocument } from "../../src/components/Shared";
import "../../src/styles.css";

// Synthetic display only. No real-project mode, accepted API operation or run.
for (const name of Object.keys(api)) api[name] = async () => { throw new Error("Synthetic preview: research-service operations are disabled."); };
const fetchStatic = window.fetch.bind(window);
window.fetch = (input, options) => {
  const url = new URL(typeof input === "string" ? input : input.url, location.href);
  return url.pathname.startsWith("/api/")
    ? Promise.reject(new Error("Synthetic preview: research-service requests are disabled."))
    : fetchStatic(input, options);
};

const projectId = "fixture.p3-scientific-account";
const branch = "method.synthetic-weights";
const theoryRef = { branch, phase: "P3", family: "theory_record", generation_id: "theory.synthetic", sha256: "a".repeat(64), run_id: "run.synthetic", package_id: "package.synthetic" };
const decisionRef = { ...theoryRef, family: "decision_record", generation_id: "decision.synthetic", sha256: "b".repeat(64) };
const assumptions = [
  { assumption_id: "assumption.nonnegative", label: "Nonnegative weights", status: "unverified", text: String.raw`Each weight satisfies $w_i\geq0$.`, sensitivity: "Signed weights need not preserve the component range. This fixture does not claim that any study uses signed weights." },
  { assumption_id: "assumption.normalization", label: "Weights normalized across every retained component", status: "unverified", text: String.raw`The finite set of weights satisfies $\sum_{i=1}^{m}w_i=1$.`, sensitivity: String.raw`Without normalization, nonnegative weights can enlarge the range: $w_1=2$ and $x_1=1$ give a weighted sum of $2$.` },
  { assumption_id: "assumption.bounded_components", status: "unverified", text: String.raw`Every retained component satisfies $|x_i|\leq1$.`, sensitivity: "Without this bound, the recorded argument does not establish the interval [-1, 1]. No observed failure is asserted." },
];
const bounded = {
  statement_id: "statement.convex_bound", label: "Bounded weighted average", status: "conditional", proof_status: "full",
  text: "A nonnegative normalized weighted average of components in [-1, 1] remains in [-1, 1].",
  latex: String.raw`\left|\sum_{i=1}^{m}w_ix_i\right|\leq\sum_{i=1}^{m}w_i|x_i|\leq1`,
  regime: "For a finite positive number of components, under all three registered premises.",
  quantifiers: [String.raw`For every $m\geq1$ and all weights and components satisfying those premises.`],
  assumption_ids: assumptions.map(item => item.assumption_id), depends_on: assumptions.map(item => item.assumption_id),
  justification: { kind: "proof", summary: "The triangle inequality bounds the absolute weighted sum by the weighted absolute values. The component bound and weight normalization then give one." },
};
const submittedArgument = { kind: "proof", summary: "The submitted argument treated estimated weights as normalized without deriving that property." };
const incomplete = {
  statement_id: "statement.estimated_normalization", label: "Estimated-weight normalization", status: "incomplete", proof_status: "full",
  text: "The proposed estimated-weight rule produces weights that sum to one for every input.", latex: String.raw`\sum_{i=1}^{m}\widehat w_i=1`,
  depends_on: [], justification: submittedArgument, original_justification_retained: true,
  assessment_context: { origin: "lead_concern", reason: "Normalization of the estimated weights remains unproved. This Lead concern has not received independent Analyst review.", generation_ref: { ...decisionRef, entry_pointer: "/assessment_changes/0", object_id: "statement.estimated_normalization" } },
  theorist_account: { status: "established", proof_status: "full", justification: submittedArgument, generation_ref: { ...theoryRef, family: "theory_candidate", generation_id: "candidate.synthetic", sha256: "c".repeat(64), entry_pointer: "/statements/1", object_id: "statement.estimated_normalization" } },
};
const questionRef = { kind: "phase_issue", branch: "trunk", phase: "P1", family: "attention_items", generation_id: "questions.synthetic", sha256: "d".repeat(64), run_id: "run.synthetic.p1", package_id: "package.synthetic.p1", entry_pointer: "/items/0", object_id: "question.synthetic.population" };
const question = { attention_id: questionRef.object_id, phase: "P1", target_phase: "P1", branch: "trunk", kind: "researcher_decision", disposition: "open", scope: { kind: "project" }, responsible_role: "research_lead", response_kind: "study_fact", question: "Which population should the eventual estimate describe?", context_markdown: "The intended population determines which component values and weights a later analysis would need.", explanation_target: questionRef, generation_ref: questionRef };
const answer = { attention_id: question.attention_id, attention: question, question_ref: questionRef, scope: question.scope, revision: 1, origin: "researcher_reported", note: "Use the synthetic enrolled population for this example.", context_ref: { item_id: "context.answer.synthetic.population", revision: 1 } };
const initialData = {
  map: { branch, phase: "P3", authoritative: true, theory_generation_ref: theoryRef, claims: [bounded, incomplete], assumptions },
  documents: [{ kind: "theory_record", title: "Synthetic weighted-average account", generation_ref: theoryRef, structured: { overview_markdown: "This synthetic account separates a mathematical implication from unverified applicability premises and an unfinished normalization argument.", statements: [bounded, incomplete], assumptions } }],
  probes: [{ branch, phase: "P3", probes: [{ probe_id: "probe.synthetic.relaxed", target_statement: bounded.statement_id, method: "Drop weight normalization while retaining nonnegative weights and bounded components.", outcome: "fails_as_stated", detail: String.raw`The stronger claim fails: $w_1=2$ and $x_1=1$ give $\sum_iw_ix_i=2$. This probe does not refute the displayed claim, which requires normalized weights.` }] }],
  decision: { phase: "P3", generation_ref: decisionRef, conclusion: String.raw`A weighted average stays in $[-1,1]$ when its weights are nonnegative and sum to one and each component lies in that interval. The proof establishes this implication; this synthetic example does not verify those premises for a study. Normalization for a proposed estimated-weight rule remains unresolved.`, fundamental_contribution: "The triangle inequality connects the component bounds to the aggregate through the normalized weights.", principal_uncertainty: "The estimated-weight construction has not been shown to normalize its output, so the range result cannot yet be transferred to that construction.", principal_risk: "Dropping normalization can enlarge the aggregate range even if every component remains bounded.", smallest_decisive_result: "Check whether the proposed estimated-weight definition sums to one. This resolves the missing premise before applying the range argument to it." },
  context: { projectId, phase: "P3", branch, issues: [question], answers: [answer], problemContext: { revision: 1, items: [{ item_id: answer.context_ref.item_id, revision: 1, status: "confirmed", scope: { kind: "project" }, statement: answer.note, answer_refs: [{ kind: "researcher_answer", attention_id: question.attention_id, question_ref: questionRef, answer_revision: answer.revision }] }], proposals: [] } },
};

function Preview() {
  const [data, setData] = useState(initialData);
  const [selected, setSelected] = useState(bounded.statement_id);
  const [reading, setReading] = useState({ tab: "claims" });
  const [dialog, setDialog] = useState(null);
  const [refreshes, setRefreshes] = useState(0);
  const [dark, setDark] = useState(new URLSearchParams(location.search).get("theme") === "dark");
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  const source = target => setDialog({ title: "Exact synthetic source", target });
  const owner = (phase, target, issue) => { setDialog({ title: "Original synthetic question: P1", target: target || issue?.explanation_target || questionRef, owner: true }); return true; };
  const refresh = () => { setData(current => structuredClone(current)); setRefreshes(count => count + 1); };
  return <main data-reader-ready="true" style={{ maxWidth: 1180, margin: "auto", padding: 20 }}>
    <h1>P3 scientific account: synthetic preview</h1>
    <p className="note">Fictional display data. Sources preview exact synthetic identities. All research-service operations are disabled. Refresh replaces equivalent component data; use the reading-position fixture for full App polling.</p>
    <div className="btnrow"><button type="button" onClick={refresh}>Refresh equivalent data</button><button type="button" onClick={() => setTimeout(refresh, 1500)}>Refresh in 1.5 seconds</button><button type="button" onClick={() => setDark(value => !value)}>Switch to {dark ? "light" : "dark"} theme</button><span role="status">Equivalent refreshes: {refreshes}</span></div>
    <PhaseOverview decision={data.decision} methodLabel="Synthetic weighted average" onSource={source} onReadTheory={tab => setReading(current => ({ ...current, tab }))} />
    <TheoryReading branch={branch} claimMaps={[data.map]} documents={data.documents} falsificationLogs={data.probes} selected={selected} onSelect={setSelected} reading={reading} onReadingChange={changes => setReading(current => ({ ...current, ...changes }))} onSource={source}
      onRequest={(intent, target) => setDialog({ title: "Synthetic request preview", target, intent })} onAssumptionConversation={target => setDialog({ title: "Synthetic explanation target", target })} />
    <p className="note">The saved answer below belongs to P1. P3 has no local questions. Its answer-backed context copy must not count as separate additional information.</p>
    <PhaseInputSummary context={data.context} phase="P3" scope="fixture.p3-scientific-account" preparation={{ loaded: true, hasInstructions: false, instructionsChanged: false, inputCount: 0, inputsChanged: false }} preparationStatus={{ loading: false, selected: true, inputsReady: true }}>
      <details data-reading-anchor="further-work"><summary>Synthetic run settings</summary><p className="note">Run submission is disabled in this fixture.</p></details>
    </PhaseInputSummary>
    <ResearcherDialogue {...data.context} onSource={source} onNavigate={owner} />
    {dialog && <Dialog title={dialog.title} onClose={() => setDialog(null)}>
      <p className="note">Synthetic preview only. No source endpoint, model request, save or run is performed.</p>
      {dialog.owner && <IssueEntry issue={{ ...question, researcher_answer: answer }} projectId={projectId} phase="P1" branch="trunk" readOnly compact onSource={source} />}
      {dialog.intent && <ResearchDocument text={`Requested operation: ${dialog.intent}. This fixture only previews its target.`} />}
      <pre className="record">{JSON.stringify(dialog.target, null, 2)}</pre>
    </Dialog>}
  </main>;
}
createRoot(document.getElementById("root")).render(<Preview />);
