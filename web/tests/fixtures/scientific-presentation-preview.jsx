import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "../../src/styles.css";
import { api } from "../../src/api";
import EmpiricalWorkbench from "../../src/components/EmpiricalWorkbench";
import IssuesCard from "../../src/components/IssuesCard";
import AssumptionConversations from "../../src/components/AssumptionConversations";
import { Dialog, ResearchDocument } from "../../src/components/Shared";
import { ActionButton } from "../../src/components/Visuals";

// Simulated browser fixture only. No research service, model, or account is used.
const parameters = new URLSearchParams(location.search);
const projectId = `fixture.scientific-presentation.${parameters.get("session") || "default"}`;
const interactiveDiscussion = parameters.get("discussion") === "interactive";
const branch = "method.simulated";
const reference = { branch, phase: "P4", family: "empirical_synthesis", generation_id: "summary.simulated", run_id: "run.simulated", package_id: "package.simulated", sha256: "a".repeat(64) };
const protocolRef = { ...reference, family: "protocol", generation_id: "protocol.simulated", sha256: "b".repeat(64) };
const analystRef = { ...reference, family: "analyst_synthesis", generation_id: "analyst.simulated", sha256: "c".repeat(64) };
const exhibitRef = { ...reference, family: "exhibits", generation_id: "exhibits.simulated", sha256: "d".repeat(64) };
const tableId = "table.comparison";
const protocolUri = `run://${reference.run_id}/protocol.json`;
const summary = {
  branch, generation_ref: reference, source_artifacts: [{ uri: protocolUri, sha256: protocolRef.sha256 }],
  scientific_outcome: {
    conclusion: "The reported error criterion is undefined, so the simulated values do not establish a performance comparison.",
    scope: "The comparison uses 24 independent synthetic datasets per condition. It does not establish performance on actual data or a general error guarantee.",
  },
  actual_data_application: { status: "not_supplied", summary_markdown: "This simulated fixture contains no actual researcher data." },
  decision_summary: {
    method_recap_markdown: String.raw`The method estimates the population mean $\mu=\mathbb E[X]$ after learning a representation on a separate training sample. Its output is $\widehat\mu$; the held-out assessment sample is used only to evaluate error. One independent dataset includes the entire training and assessment procedure.`,
    method_formulation_markdown: String.raw`The complete formulation preserves the separation between fitting and assessment.

For dataset $D_r$, fit the representation $f_r$ using training observations and estimate the target from its held-out sample:

$$
\widehat\mu_r=\frac{1}{n_{\mathrm{assess}}}\sum_{i\in D_{r,\mathrm{assess}}}f_r(X_i).
$$

The population target is $\mu=\mathbb E[X]$. This illustration does not assert that an arbitrary representation preserves that target. The comparison is conditional on the specified generating laws, split rule and complete fitting procedure.

Each recorded error is evaluated against the known synthetic reference. The complete dataset, rather than an inner fit or an individual observation, is the repetition unit.`,
    notation_markdown: String.raw`| Symbol | Definition | Meaning and units |
| --- | --- | --- |
| $\mu$ | $\mathbb E[X]$ | Population mean in the synthetic distribution; the observation scale is arbitrary. |
| $D_r$ | Dataset $r$ with a training and assessment split | One independent repetition of the complete procedure. |
| $\widehat\mu_r$ | Estimate produced from $D_r$ | The output whose error is evaluated, distinct from the population target. |
| $n_{\mathrm{assess}}$ | Assessment-sample size | Number of held-out observations inside a dataset; it is not the number of independent datasets. |

The [protocol definition](${protocolUri}#/estimand) retains the source of the target and experimental unit.`,
    implementation_markdown: "A complete training and assessment procedure was implemented and compared with one reference procedure. The simulated investigation includes a reference condition and a shifted distribution.",
    method_fidelity_markdown: "The recorded checks preserve the separation between training and assessment. These simulated checks are for interface verification and do not establish scientific validity.",
    conclusion_markdown: "The reported error values differ between procedures and conditions, but the error criterion is not defined. The table retains the Monte Carlo standard error for each reported summary; no interval for a paired contrast is supplied.",
    tradeoff_markdown: "The proposed procedure took longer in both simulated conditions. A deployment decision would need measurements from the intended environment.",
    limitations_markdown: "Only two generating distributions and one sample size were studied. Tuning sensitivity and actual-data performance remain unassessed.",
    theory_relation: { status: "not_tested", explanation_markdown: "This fixture does not test a theoretical result. Observed numerical behavior is not a proof." },
    headline_exhibit_ids: [tableId],
    coverage: [
      { dimension: "synthetic_example", status: "addressed", summary: "Each synthetic dataset contains separate training and assessment observations from one of two specified distributions.", limitation_markdown: "The distributions are illustrative and do not represent a supplied study population.", question_ids: ["question.design"] },
      { dimension: "performance", status: "partial", summary: "Reported error was 0.31 versus 0.53 in the reference condition, then 0.64 versus 0.58 after the shift.", limitation_markdown: "The error definition and units are not supplied, so these values do not establish which procedure performs better. The table reports each summary's Monte Carlo standard error. A paired-difference interval is not available, so these marginal summaries do not supply uncertainty for the contrast.", question_ids: ["question.performance"], exhibit_ids: [tableId] },
      { dimension: "computation", status: "partial", summary: "The proposed procedure took about half a second per complete dataset, compared with about a fifth of a second for the comparator.", limitation_markdown: "These simulated timings cover training and assessment together. They do not establish runtime scaling.", question_ids: ["question.cost"], exhibit_ids: [tableId] },
      { dimension: "tuning", status: "not_assessed", summary: "Tuning sensitivity was not studied. The same fixed setting was used in all simulated datasets.", limitation_markdown: "A fixed setting does not show that nearby choices would behave similarly.", question_ids: [] },
      { dimension: "robustness", status: "partial", summary: "The reported error values changed under the specified distribution shift.", limitation_markdown: "The shift changes the observation law, but the undefined error criterion prevents interpreting the change as improved or degraded performance.", question_ids: ["question.performance"], exhibit_ids: [tableId] },
    ],
  },
};
const displayedSummary = parameters.get("legacy") === "1" ? { ...summary, decision_summary: { ...summary.decision_summary, method_recap_markdown: undefined, notation_markdown: undefined } } : summary;
const questions = [
  { question_id: "question.design", title: "What does an independent experiment include?", result: { category: "implementation", answer_markdown: "Each repetition generates a full dataset, trains the representation, and evaluates the held-out estimate.", conditions_markdown: "The same train-assessment split rule is applied to both procedures." } },
  { question_id: "question.performance", title: "What do the reported error values show across conditions?", result: { category: "performance", answer_markdown: "The simulated values differ across procedures and conditions, but the error criterion is not defined.", conditions_markdown: "Both procedures use the same generated dataset within a repetition.", uncertainty_markdown: "The saved values contain marginal Monte Carlo standard errors. A paired-difference uncertainty calculation was not supplied.", exhibit_ids: [tableId], outcome: "inconclusive" }, review: { review_markdown: "The Lead retains both conditions and the missing error definition beside the reported values.", theorist_findings_markdown: "Theorist qualification: the undefined error criterion prevents a performance interpretation. The numerical values do not establish a general guarantee." } },
  { question_id: "question.cost", title: "What time boundary was measured?", result: { category: "cost", answer_markdown: "The simulated timing covers the whole training and assessment procedure.", conditions_markdown: "Initialization and fitting are included in the recorded procedure time.", limitations_markdown: "Scaling and environment variation were not studied.", exhibit_ids: [tableId], outcome: "inconclusive" } },
].map((question) => ({ ...question, branch, phase: "P4", generation_ref: protocolRef, result: { ...question.result, generation_ref: analystRef }, ...(question.review ? { review: { ...question.review, generation_ref: reference } } : {}) }));
const protocol = {
  branch, generation_ref: protocolRef, title: "Simulated study protocol",
  data_sources: [{ data_source_id: "source.synthetic", label: "Illustrative synthetic datasets", origin: "synthetic" }],
  data_or_simulation_unit: { source_type: "synthetic", sampling_or_generation_process: "Generate a full dataset under the reference distribution or a prespecified shifted distribution.", unit_definition: "One independent generated dataset including its complete learning and assessment procedure.", sample_sizes: [200], independence_structure: "Datasets are independent. Both procedures share each generated dataset for a paired comparison.", splits: "Use disjoint training and assessment observations." },
  baselines: [{ baseline_id: "comparator", name: "Reference procedure", rationale: "Provides an interpretable comparison under the same data and splits." }],
  estimand: { name: "Population mean", mathematical_definition: String.raw`$\mu=\mathbb E[X]$`, analysis_unit: "An observation in the named synthetic population." },
  repetitions_and_uncertainty: { repetitions: 24, paired_design: true, interval_or_error_method: "Report saved marginal Monte Carlo standard errors; no paired-difference interval is supplied." },
  tuning_budget: { selection_data: "Training observations only.", search_space: "One fixed prespecified setting.", maximum_trials: 1 },
};
const exhibits = [{ exhibit_id: tableId, branch, phase: "P4", title: "Reported error and elapsed time", caption: "Simulated values from 24 independent datasets per condition. The error definition and units are not supplied, so the values cannot establish which procedure performs better. Each Monte Carlo standard error describes uncertainty in one reported error summary across independent datasets. No paired-difference interval is supplied. Elapsed time includes training and assessment and is reported in seconds.", kind: "table", media_type: "text/csv", source_verified: true, artifact_url: "./scientific-presentation-values.csv", generation_ref: exhibitRef, table: { columns: [{ key: "condition", label: "Condition" }, { key: "method", label: "Method" }, { key: "datasets", label: "Independent datasets" }, { key: "error", label: "Reported error" }, { key: "mcse", label: "Monte Carlo standard error" }, { key: "time", label: "Elapsed time", unit: "seconds" }], rows: [{ condition: "Reference distribution", method: "Proposed", datasets: 24, error: 0.31, mcse: 0.02, time: 0.48 }, { condition: "Reference distribution", method: "Comparator", datasets: 24, error: 0.53, mcse: 0.03, time: 0.19 }, { condition: "Shifted distribution", method: "Proposed", datasets: 24, error: 0.64, mcse: 0.04, time: 0.51 }, { condition: "Shifted distribution", method: "Comparator", datasets: 24, error: 0.58, mcse: 0.03, time: 0.20 }], total_rows: 4 } }];
const implementations = [{ branch, producer_role: "data_analyst", generation_ref: { ...reference, family: "implementation_record", generation_id: "implementation.simulated", sha256: "e".repeat(64) }, sections: [{ key: "rule", title: "Implemented rule", body_md: "The implementation keeps fitting and assessment separate and retains the full procedure as the experimental unit." }, { key: "verification", title: "Recorded checks", body_md: "The simulated record contains split-separation, deterministic-seed and output-shape checks. They are display fixtures and do not represent executed scientific checks." }, { key: "limitations", title: "Execution limits", body_md: "No actual data or deployment environment is supplied. The fixture cannot establish reusable numerical correctness." }], reproduction: { status: "unavailable" }, theorist_review: { body_md: "The stated target and experimental unit are distinct. The performance account retains the absence of paired uncertainty.", generation_ref: { ...reference, family: "theory_audit", generation_id: "audit.simulated", sha256: "f".repeat(64) } } }];
const issueTarget = { ...reference, kind: "phase_issue", family: "attention_items", generation_id: "attention.simulated", object_id: "decision.comparison", entry_pointer: "/attention_items/0" };
const issue = { attention_id: issueTarget.object_id, phase: "P4", target_phase: "P4", branch, kind: "researcher_decision", response_kind: "choice", decision_priority: "resources", disposition: "open", severity: "major", responsible_role: "research_lead", scope: { kind: "project" }, generation_ref: issueTarget, explanation_target: issueTarget,
  question: "Which next comparison best serves your intended use?",
  context_markdown: "The reported error values differ between conditions, but their definition is not supplied. Further work could examine the shift after defining the error criterion or measure runtime across sample sizes.",
  likely_consequence: "This chooses the next investigation. It does not change the current target or turn the present results into a guarantee.",
  recommended_option_id: "shift", recommendation: "Investigate the shift after defining the error criterion, because the reported values differ between conditions.",
  options: [{ id: "shift", label: "Investigate the distribution shift", consequence: "Define the error criterion, then examine how the changed observation law affects the comparison. Runtime scaling stays unassessed." }, { id: "runtime", label: "Measure runtime scaling", consequence: "Assess feasibility at larger sample sizes. The error definition and shifted comparison stay unresolved." }],
};
let savedAnswers = []; const saves = []; const discussionRequests = []; const simulatedConversations = []; let discussionSequence = 0;
api.resolveAttention = async (pid, id, note, options) => {
  if (pid !== projectId || id !== issue.attention_id) throw new Error("This fixture saves only its simulated question.");
  const previous = savedAnswers.find((answer) => answer.attention_id === id);
  if (!options.expected_source || Object.keys(issueTarget).some((key) => options.expected_source[key] !== issueTarget[key])) throw new Error("The simulated question source changed. Reload this preview.");
  if (options.expected_revision !== (previous?.revision || 0)) throw new Error("The simulated saved revision changed. Reload this preview.");
  const selected = options.selection && issue.options.find((option) => option.id === options.selection.option_id);
  const selection = selected && { option_id: selected.id, label: selected.label, consequence: selected.consequence, note: options.selection.note || "" };
  const canonicalNote = selection ? `Selected option: ${selection.label}\n\n${selection.consequence}${selection.note ? `\n\nYour note: ${selection.note}` : ""}` : note;
  const answer = { attention_id: id, attention: issue, question_ref: issueTarget, scope: issue.scope, note: canonicalNote, origin: options.origin, revision: (previous?.revision || 0) + 1, ...(selection ? { selection } : {}) };
  savedAnswers = [answer]; saves.push({ note, options, answer });
  return { answer };
};
api.startRun = async (pid, body) => {
  if (pid !== projectId || body.target?.object_id !== issueTarget.object_id) throw new Error("This fixture discusses only its simulated question.");
  const submitted = body.researcher_response_draft;
  const option = submitted?.kind === "choice" && issue.options.find((item) => item.id === submitted.option_id);
  if (submitted?.kind === "choice" && !option) throw new Error("The selected option is absent from this simulated question.");
  const responseDraft = submitted ? option ? { kind: "choice", option_id: option.id, label: option.label, consequence: option.consequence, note: submitted.note || "" } : { ...submitted } : undefined;
  const id = `discussion.simulated.${++discussionSequence}`;
  const created_at = new Date().toISOString();
  const run = { run_id: id, assessment_id: id, state: "assessed", created_at, responsible_role: "research_lead", ...(responseDraft ? { researcher_response_draft: responseDraft } : {}) };
  simulatedConversations.unshift({ assessment_id: id, assessment_purpose: body.assessment_purpose, target: body.target, target_label: issue.question, responsible_role: "research_lead", researcher_answer: savedAnswers[0] ? structuredClone(savedAnswers[0]) : undefined, researcher_response_draft: responseDraft, researcher_note_draft: body.researcher_note_draft, created_at, turns: [{ ...run, instructions: body.instructions, assessment_markdown: "This is a scripted reply for browser verification. Investigating the shift and measuring runtime answer different questions; the current scientific result stays unchanged.\n\nAny unsaved choice shown in the context panel remains provisional. The saved response, if present, is shown separately with its revision. Opening this discussion or receiving this reply does not save an answer.\n\nUse a follow-up to inspect the actual conversation controls. The fixture keeps the original source and initial answer snapshot for this discussion and contacts no model or research service." }] });
  discussionRequests.push(structuredClone({ type: "start", body, normalized_draft: responseDraft }));
  return run;
};
api.assessmentMessage = async (pid, assessmentId, body) => {
  const conversation = simulatedConversations.find((item) => item.assessment_id === assessmentId);
  if (pid !== projectId || !conversation) throw new Error("This fixture accepts follow-ups only for its simulated conversations.");
  const run = { run_id: `discussion.simulated.${++discussionSequence}`, assessment_id: assessmentId, state: "assessed", created_at: new Date().toISOString(), responsible_role: "research_lead" };
  conversation.turns.push({ ...run, instructions: body.instructions, assessment_markdown: "This scripted follow-up retains the source and response snapshot from the start of this simulated discussion. New edits at the answer editor do not rewrite this conversation's initial context.\n\nNo answer has been saved by this reply, no scientific record has changed, and no model or research service was contacted." });
  discussionRequests.push(structuredClone({ type: "follow-up", assessment_id: assessmentId, body }));
  return run;
};

function Preview() {
  const [source, showSource] = useState(null); const [discussion, showDiscussion] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [answers, setAnswers] = useState([]); const [refreshes, setRefreshes] = useState(0);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [dark, setDark] = useState(parameters.get("theme") === "dark");
  useEffect(() => {
    if (!autoRefresh) return;
    const timer = setInterval(() => setRefreshes((count) => count + 1), 3000);
    return () => clearInterval(timer);
  }, [autoRefresh]);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  return <main style={{ maxWidth: 1120, margin: "0 auto", padding: 20 }}>
    <h1>Scientific presentation · simulated preview</h1>
    <p>All findings, values, questions and sources on this page are simulated for browser verification. Answers remain in memory; no model, account or research service is used.</p>
    {interactiveDiscussion && <p className="note">Interactive simulated discussion uses the actual conversation component with scripted API replies. Close an unsent discussion, change the answer choice, and reopen it to inspect the retained question and current response context.</p>}
    <div className="btnrow"><ActionButton action="details" onClick={() => setDark(!dark)}>Switch to {dark ? "light" : "dark"} theme</ActionButton><ActionButton action="refresh" onClick={() => setRefreshes((count) => count + 1)}>Simulate refresh</ActionButton><label className="check-label"><input type="checkbox" checked={autoRefresh} onChange={(event) => setAutoRefresh(event.target.checked)} />Auto refresh simulated view every 3 seconds</label><span className="note" role="status">{refreshes} simulated refreshes</span></div>
    <EmpiricalWorkbench branch={branch} summaries={[{ ...displayedSummary }]} questions={questions} protocols={[protocol]} exhibits={exhibits} implementations={implementations} initialTab="comparisons" onSource={showSource}
      issues={<IssuesCard title="Decisions to Discuss" projectId={projectId} phase="P4" branch={branch} issues={[issue]} answers={answers} questionsOnly onSaved={() => setAnswers([...savedAnswers])} onExplain={showDiscussion} onSource={showSource} />}
      furtherWork={<section className="card p4-further-work" data-card-role="action"><h2>Revise and Rerun</h2><div className="body"><p>This fixture previews the effective answer without starting research. A saved response appears only at its owning question above.</p><p>{answers.length ? "One simulated answer is saved for future work." : "No simulated answer has been saved."}</p><details className="research-details"><summary>Simulated save evidence</summary><pre className="record">{JSON.stringify(saves, null, 2)}</pre></details></div></section>} />
    <section className="card" data-card-role="history"><h2>History</h2><div className="body"><p>This display uses a single simulated evaluation. No scientific publication or earlier run has been changed.</p><p>Use the source controls, open details, move to another topic, then return to verify reading position. Simulate refresh while a table or details section is open to verify that the same mounted reader retains its state.</p>{interactiveDiscussion && <details className="research-details"><summary>Simulated discussion request evidence</summary><pre className="record">{JSON.stringify(discussionRequests, null, 2)}</pre></details>}</div></section>
    {source && <Dialog title="Simulated exact source" onClose={() => showSource(null)}><p>This source window shows the precise simulated generation and field requested by the reader. It does not load a real research record.</p><pre className="record">{JSON.stringify(source, null, 2)}</pre></Dialog>}
    {discussion && (interactiveDiscussion ? <AssumptionConversations key={JSON.stringify(discussion)} projectId={projectId} target={discussion} conversations={conversations} onClose={() => showDiscussion(null)} onSource={showSource} onStarted={() => setConversations([...simulatedConversations])} /> : <Dialog title="Simulated targeted discussion" onClose={() => showDiscussion(null)}><p>The unsaved response below is conversation context. Opening this preview does not save or adopt it.</p><pre className="record">{JSON.stringify(discussion, null, 2)}</pre><ResearchDocument text="An actual discussion would answer this exact question using its frozen sources and keep any advice separate from a saved researcher answer." /></Dialog>)}
  </main>;
}
const previewRoot = createRoot(document.getElementById("root"));
previewRoot.render(<Preview />);
if (import.meta.hot) import.meta.hot.dispose(() => previewRoot.unmount());
