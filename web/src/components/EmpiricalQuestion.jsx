import React, { useId, useState } from "react";
import { fmt, humanLabel, OUTCOMES } from "../research";
import { coverageForTab, evidenceTab, hasEmpiricalFollowup, theoryClaimSource } from "../empirical";
import { Dialog, Outcome, RunState, SourceRef } from "./Shared";
import ResearchDocument from "./EmpiricalDocument";
import { ActionButton, ActionIcon } from "./Visuals";
import ArtifactTable from "./ArtifactTable";

export const EVIDENCE_TABS = [["setup", "Synthetic example"], ["comparisons", "Performance"], ["computation", "Computation"], ["tuning", "Tuning"], ["sensitivity", "Robustness"]];
const TABS = EVIDENCE_TABS;
export { evidenceTab };
export const evidenceFamily = (category) => ({ implementation: "Implementation correctness", implementation_fidelity: "Implementation correctness", performance: "Performance against existing methods", cost: "Computation and practical cost", tuning: "Tuning choices and sensitivity", sensitivity: "Sensitivity and operating conditions", assumptions: "Sensitivity and operating conditions", failures: "Failures and limitations" }[category] || humanLabel(category || "Evaluation question"));

export function EmpiricalQuestionTabs({ id, selected, onSelect, coverage = [], questions = [] }) {
  const move = (event, index) => {
    const next = event.key === "ArrowRight" ? (index + 1) % TABS.length : event.key === "ArrowLeft" ? (index + TABS.length - 1) % TABS.length : event.key === "Home" ? 0 : event.key === "End" ? TABS.length - 1 : null;
    if (next === null) return;
    event.preventDefault(); onSelect(TABS[next][0]); event.currentTarget.parentElement.querySelectorAll('[role="tab"]')[next]?.focus();
  };
  return <div className="empirical-tabs" role="tablist" aria-label="Experimental evidence">{TABS.map(([key, label], index) => {
    const entries = coverageForTab(coverage, key, questions);
    const description = entries.length ? entries.map((item) => `${humanLabel(item.dimension)}: ${humanLabel(item.status)}`).join(" · ") : "Coverage not recorded";
    const statuses = entries.length ? [...new Set(entries.map((item) => humanLabel(item.status)))].join(" · ") : "Coverage not recorded";
    return <button key={key} type="button" role="tab" id={`${id}-${key}`} aria-controls={`${id}-panel`} aria-selected={selected === key} tabIndex={selected === key ? 0 : -1} title={description} aria-description={description} onClick={() => onSelect(key)} onKeyDown={(event) => move(event, index)}><span>{label}</span><span className="empirical-tab-coverage">{statuses}</span></button>;
  })}</div>;
}

// The table is projected from the verified saved artifact. Never parse prose or
// estimate missing values in the browser, and preserve zero distinctly from null.
export function EmpiricalExhibit({ exhibit, onSource, anchorId, readingAnchor }) {
  const [enlarged, setEnlarged] = useState(false); const [zoom, setZoom] = useState(1);
  const captionId = useId();
  const table = exhibit.table;
  const image = exhibit.artifact_url && (exhibit.media_type || "").startsWith("image/");
  return <figure id={anchorId} tabIndex={anchorId ? -1 : undefined} data-reading-anchor={readingAnchor} className="research-exhibit empirical-exhibit">
    {exhibit.title && <h4>{exhibit.title}</h4>}
    {image && <><button type="button" className="empirical-figure-button" onClick={() => { setZoom(1); setEnlarged(true); }} aria-label={`Enlarge figure: ${exhibit.title || "Experimental result"}`}><img src={exhibit.artifact_url} alt={exhibit.caption || exhibit.title || "Experimental result"} loading="lazy" /><span className="source-link">Enlarge figure</span></button>{enlarged && <Dialog title={exhibit.title || "Experimental result"} className="empirical-figure-viewer" onClose={() => setEnlarged(false)}><div className="btnrow"><ActionButton action="details" disabled={zoom <= 1} onClick={() => setZoom((value) => Math.max(1, value - 0.5))}>Zoom out</ActionButton><span className="note" role="status">{Math.round(zoom * 100)}%</span><ActionButton action="details" disabled={zoom >= 3} onClick={() => setZoom((value) => Math.min(3, value + 0.5))}>Zoom in</ActionButton></div><div className="empirical-figure-scroll" tabIndex={0} role="region" aria-label="Enlarged figure; use arrow keys to scroll"><img src={exhibit.artifact_url} alt={exhibit.caption || exhibit.title || "Experimental result"} style={{ width: `${zoom * 100}%`, maxWidth: "none", maxHeight: "none" }} /></div>{exhibit.caption && <ResearchDocument text={exhibit.caption} />}</Dialog>}</>}
    {table && exhibit.caption && <figcaption id={captionId}><ResearchDocument text={exhibit.caption} /></figcaption>}
    {table?.columns?.length > 0 && <ArtifactTable table={table} title={exhibit.title || "Result table"} describedBy={exhibit.caption ? captionId : undefined} />}
    {!table && exhibit.caption && <figcaption><ResearchDocument text={exhibit.caption} /></figcaption>}
    {(exhibit.data_sources || []).length > 0 && <div className="exhibit-data-sources"><h5>Data behind this exhibit</h5>{exhibit.data_sources.map((source, index) => <div key={source.path || index}>{source.artifact_url && source.source_verified !== false ? <a className="source-link ui-action" data-action="source" data-ui-role="system" href={source.artifact_url} target="_blank" rel="noreferrer"><ActionIcon name="source" />{source.label || source.title || "Open recorded data"}</a> : <p className="note warn">{source.label || source.title || "Declared data source"}: {source.source_error || "The declared data link could not be verified."}</p>}</div>)}</div>}
    {image && !exhibit.data_sources?.length && <p className="note">No explicit data-artifact link is recorded for this figure. Any question-specific values shown separately retain their own source.</p>}
    {exhibit.detail_md && <ResearchDocument text={exhibit.detail_md} />}
    {exhibit.source_error && <p className="note warn" role="alert">{exhibit.source_error}</p>}
    {!image && !table && !exhibit.source_error && <p className="note">No inline numerical exhibit is available in this record.</p>}
    <div className="btnrow">{exhibit.artifact_url && <a className="source-link ui-action" data-action="source" data-ui-role="system" href={exhibit.artifact_url} target="_blank" rel="noreferrer"><ActionIcon name="source" />Open original {image ? "figure" : table ? "table" : "exhibit"}</a>}<SourceRef reference={exhibit.generation_ref} onOpen={onSource} /></div>
  </figure>;
}

function Passage({ title, text, warning = false, level = 4 }) {
  const Heading = level === 3 ? "h3" : "h4";
  return text ? <section className={warning ? "empirical-passage context-note" : "empirical-passage"}><Heading>{title}</Heading><ResearchDocument text={text} /></section> : null;
}

function RecordedQuestionTable({ diagnostic, cases, protocol, onSource }) {
  const metrics = Object.fromEntries((protocol?.metrics || []).map((item) => [item.metric_id, item]));
  const baselines = Object.fromEntries((protocol?.baselines || []).map((item) => [item.baseline_id, item.name]));
  const rows = diagnostic.headline_numbers.map((row) => {
    const item = cases.find((item) => item.case_id === row.case_id); const metricId = row.metric_id || row.metric; const metric = metrics[metricId];
    return { case: item?.label || item?.title || humanLabel(row.case_id), method: item?.comparator_id === "selected_method" ? "Proposed method" : item?.baseline_label || baselines[item?.comparator_id] || humanLabel(item?.comparator_id || "Not recorded"), metric: metric?.name || diagnostic.metric_labels?.[metricId] || humanLabel(metricId), unit: row.unit || metric?.unit || metric?.units || "Not recorded", estimate: Number.isFinite(row.estimate) ? fmt(row.estimate, { uncertainty: row.mcse }) : null, uncertainty: row.uncertainty_kind === "not_applicable" ? "Not applicable" : row.uncertainty_kind === "custom" ? "See protocol" : Number.isFinite(row.mcse) ? `MCSE ${fmt(row.mcse)}` : "Not assessed", repetitions: fmt(row.n_replicates, { kind: "count" }), interval: Number.isFinite(row.ci_lo) && Number.isFinite(row.ci_hi) ? `[${fmt(row.ci_lo, { uncertainty: row.mcse })}, ${fmt(row.ci_hi, { uncertainty: row.mcse })}]` : null, interval_level: row.confidence_level != null ? `${fmt(row.confidence_level * 100)}%` : "Not recorded" };
  });
  const columns = [{ key: "case", label: "Case" }, { key: "method", label: "Method" }, { key: "metric", label: "Metric" }, { key: "unit", label: "Unit" }, { key: "estimate", label: "Estimate" }, { key: "uncertainty", label: "Uncertainty" }, { key: "repetitions", label: "Usable repetitions" }];
  if (rows.some((row) => row.interval !== null)) columns.push({ key: "interval", label: "Recorded interval" }, { key: "interval_level", label: "Interval level" });
  return <EmpiricalExhibit onSource={onSource} exhibit={{ title: "Recorded results for this question", caption: "These summaries were recomputed from eligible saved observations. No new experiment is needed. Monte Carlo standard error (MCSE) describes uncertainty for each estimate, not uncertainty in the difference between methods. Counts of failed, excluded and unrun repetitions remain in the saved sources where recorded.", generation_ref: diagnostic.generation_ref, table: { columns, rows } }} />;
}

// One readable evidence block, without a second layer of scientific tabs.
export default function EmpiricalQuestion({ question, cases = [], diagnostics = [], protocol, onSource, onRequest, onTheory, hasMapping = true, headlineExhibits = [], onHeadline, showEvidence = true, onExhibit }) {
  const result = question.result || {}; const review = question.review || {};
  const hasHeadline = (question.exhibits || []).some((exhibit) => headlineExhibits.includes(exhibit));
  const recorded = hasHeadline ? [] : diagnostics.filter((item) => item.headline_numbers?.length);
  const hasVerifiedExhibit = (question.exhibits || []).some((exhibit) => exhibit.source_verified === true && exhibit.artifact_url && !exhibit.source_error);
  const answer = result.answer_markdown || question.conclusion;
  // Older questions sometimes store a scientific outcome in status. Only known
  // outcomes belong here; successful execution never establishes support.
  const scientificOutcome = result.outcome || (OUTCOMES[question.status] ? question.status : "not_assessed");
  const executionState = question.status && !OUTCOMES[question.status] && question.status !== result.outcome ? question.status : null;
  return <article className="empirical-result-block">
    <div className="section-heading"><p className="note">{evidenceFamily(result.category || question.category)} · Analyst</p><div className="btnrow empirical-result-status"><Outcome state={scientificOutcome} />{executionState && <span className="note">Execution: <RunState state={executionState} /></span>}</div></div>
    <section className="empirical-result-finding"><h4>Finding</h4><ResearchDocument text={answer || (scientificOutcome === "not_assessed" ? "No authored finding is recorded for this question. It remains unassessed; its planned design is in Setup." : "No separate authored finding is recorded for this question.")} />{result.relevance_markdown && <ResearchDocument text={result.relevance_markdown} />}{result.comparison_markdown && <ResearchDocument text={result.comparison_markdown} />}</section>
    {(question.exhibits || []).map((exhibit, index) => !showEvidence ? <p className="empirical-exhibit-link" key={exhibit.exhibit_id || index}><ActionButton action="details" variant="link" onClick={() => onExhibit?.(exhibit)}>View {exhibit.title || "recorded exhibit"} in Experiments and Results</ActionButton></p> : headlineExhibits.includes(exhibit) ? <p className="empirical-headline-link" key={exhibit.exhibit_id || index}><ActionButton action="details" variant="link" onClick={() => onHeadline?.(exhibit)}>View {exhibit.title || "recorded result"} in Experiments and Results</ActionButton></p> : <EmpiricalExhibit key={exhibit.exhibit_id || index} exhibit={exhibit} onSource={onSource} />)}
    {showEvidence && (recorded.length ? <details className="research-details empirical-recorded-values" open={!question.exhibits?.length}><summary>Recorded values, uncertainty and repetitions</summary>{recorded.map((diagnostic, index) => <RecordedQuestionTable key={diagnostic.diagnostics_id || index} diagnostic={diagnostic} cases={cases} protocol={protocol} onSource={onSource} />)}</details> : <p className="note">{hasHeadline ? "Quantitative results are shown in the linked experiment exhibit." : hasVerifiedExhibit ? "No additional aggregate numerical summary is linked to this question. Inspect the linked exhibits and original sources." : !hasMapping ? "This source does not identify which numerical rows answer this question. The complete numerical source remains in Experiments and Results." : ["not_evaluated", "inconclusive"].includes(result.outcome) ? "No completed numerical values are linked to this question. Its evidence gap remains open." : "No recorded numerical values are linked to this result. Inspect its sources before interpreting the answer."}</p>)}
    {!showEvidence && !question.exhibits?.length && <p className="note">{!hasMapping ? "This source does not identify which numerical rows answer this question. Complete numerical sources are retained in Experiments and Results." : "Recorded numerical values and sources are retained in the complete numerical results disclosure."}</p>}
    <section className="empirical-result-conditions"><h4>Conditions and caveats</h4>
      {[result.conditions_markdown || question.scope || question.conditions, result.reliability_markdown, result.uncertainty_markdown, result.limitations_markdown || question.caveat].filter(Boolean).map((text, index) => <ResearchDocument key={index} text={text} />)}
      {result.observed_counts && <p className="note">Recorded case outcomes: {fmt(result.observed_counts.completed, { kind: "count" })} completed, {fmt(result.observed_counts.failed, { kind: "count" })} failed and {fmt(result.observed_counts.not_run, { kind: "count" })} not run, from {fmt(result.observed_counts.planned, { kind: "count" })} planned.</p>}
      {result.observed_counts?.invalidated > 0 && <p className="note">Excluded earlier case outcomes: {result.observed_counts.invalidated}. These are retained in history and do not contribute to the reported results.</p>}
      {question.excluded_observations?.length > 0 && <details className="research-details empirical-excluded-observations"><summary>Why recorded observations were excluded</summary>{question.excluded_observations.map((excluded, index) => <section key={index}><h5>{cases.find((item) => item.case_id === excluded.case_id)?.label || humanLabel(excluded.case_id || "Recorded case")}</h5><ResearchDocument text={excluded.invalidation_reason || "The reason was not recorded."} /><p className="note">{fmt(excluded.count, { kind: "count" })} excluded observation rows.</p><SourceRef reference={excluded.generation_ref} onOpen={onSource} label="Excluded observations source" /></section>)}</details>}
      {!result.conditions_markdown && !question.scope && !question.conditions && !result.reliability_markdown && !result.uncertainty_markdown && !result.limitations_markdown && !question.caveat && <p className="note">No separate conditions or caveats account is recorded.</p>}
      {(review.review_markdown || review.theorist_findings_markdown) && <details className="research-details empirical-review-details"><summary>Scientific review and qualifications</summary>
        {review.review_markdown && <div className="empirical-review-note"><b>Research Lead</b><ResearchDocument text={review.review_markdown} /></div>}
        {review.theorist_findings_markdown && <div className="empirical-review-note"><b>Theorist</b><ResearchDocument text={review.theorist_findings_markdown} /></div>}
        <SourceRef reference={review.generation_ref} onOpen={onSource} label="Review source" />
      </details>}
    </section>
    <Passage title="Implication for the model" text={result.decision_implication_markdown} />
    <div className="btnrow"><SourceRef reference={result.generation_ref || question.generation_ref} onOpen={onSource} />{onRequest && hasEmpiricalFollowup(question) && <ActionButton action="check" uiRole="research" variant="link" onClick={() => onRequest(question)}>Request another check</ActionButton>}</div>
  </article>;
}

export function EmpiricalQuestionSetup({ question, cases = [], onSource, onTheory }) {
  const result = question.result || {};
  const settings = cases.filter((item) => question.case_ids?.includes(item.case_id));
  return <section className="empirical-question-setup"><h4>{question.title || question.question || question.hypothesis || "Study design"}</h4>
    <ResearchDocument text={result.design_markdown || question.caption || question.design || "A separate study-design account is not recorded for this question."} />
    {(result.conditions_markdown || question.scope || question.conditions) && <ResearchDocument text={result.conditions_markdown || question.scope || question.conditions} />}
    {question.falsification_rule && <div><b>What would count against the claim?</b><ResearchDocument text={question.falsification_rule} /></div>}
    {settings.length > 0 && <details className="research-details empirical-question-cases"><summary>Experiment settings ({settings.length})</summary><div className="table-scroll" tabIndex={0} role="region" aria-label={`Experiment settings for ${question.title || question.question || question.hypothesis || "this question"}`}><table className="empirical-case-table"><caption className="sr-only">Authored conditions and planned repetitions</caption><thead><tr><th scope="col">Setting</th><th scope="col">Conditions</th><th scope="col">Comparator</th><th scope="col">Planned repetitions</th></tr></thead><tbody>{settings.map((item) => <tr key={item.case_id}><th scope="row">{item.label || item.title || humanLabel(item.case_id)}</th><td><ResearchDocument text={item.conditions || item.regime || item.description || "No separate conditions are recorded."} /></td><td>{item.baseline_label || humanLabel(item.comparator_id || "Not recorded")}</td><td>{item.replicates?.length ?? "Not recorded"}</td></tr>)}</tbody></table></div></details>}
    {question.statement_ids?.length > 0 && <div><h4>Claims in the theory used for this evaluation</h4>{question.statement_ids.map((claim) => { const source = theoryClaimSource(question, claim); return <ActionButton action="details" key={claim} aria-label={`Inspect tested claim: ${humanLabel(claim)}`} disabled={!source || !onTheory} onClick={() => onTheory?.(...source)}>{humanLabel(claim)}</ActionButton>; })}{!question.theory_context?.tested_ref && <p className="note">The exact theory source is unavailable for these links.</p>}</div>}
    <SourceRef reference={question.generation_ref} onOpen={onSource} />
  </section>;
}

export function EmpiricalDecisionSummary({ record, questions = [], dataSources = [], onSelect, onSource, awaitingDirection = false, hasProgress = false, progressState }) {
  const summary = record?.decision_summary; const method = record?.evaluated_method;
  const outcome = record?.scientific_outcome;
  const conciseOutcome = [outcome?.conclusion, outcome?.scope].every((text) => typeof text === "string" && text.trim());
  const anchor = `evaluation:${record?.generation_ref?.generation_id || record?.branch || "overview"}`;
  const source = (field) => <SourceRef reference={record?.generation_ref && { ...record.generation_ref, entry_pointer: `/decision_summary/${field}` }} onOpen={onSource} label="Summary source" />;
  const questionIds = [...new Set((summary?.coverage || []).flatMap((entry) => entry.question_ids || []))];
  const questionLinks = questionIds.map((id) => questions.find((question) => (question.id || question.question_id || question.test_id) === id)).filter(Boolean);
  return <section className="card empirical-decision" data-card-role="summary"><h2>Summary</h2><div className="body" data-overview-complete={Boolean(summary?.implementation_markdown && (summary?.method_formulation_markdown || method?.summary))}>
    {!summary ? <p className="note">{awaitingDirection ? "This evaluation is waiting for your direction. Inspect the latest attempt in Activity; any recorded questions appear below. No reviewed implementation or performance account has been published yet." : ["failed", "cancelled"].includes(progressState) ? "The evaluation stopped before publication. Inspect Activity for the interruption and available recovery actions. Saved experiments remain in the evaluation plan below." : hasProgress ? "The evaluation is in progress. Its implementation and performance account will appear after scientific review." : "No reviewed implementation or performance account has been published for this model yet."}</p> : <>
      <section className="empirical-overview-section empirical-method-formulation"><h3>{summary.method_formulation_markdown ? "Implemented method" : "Method evaluated"}</h3>{!summary.method_formulation_markdown && method?.summary && <p className="note">Definition recorded at the start of this evaluation</p>}
        {summary.method_formulation_markdown ? <><ResearchDocument text={summary.method_formulation_markdown} />{source("method_formulation_markdown")}</> : method?.summary ? <><ResearchDocument text={method.summary} /><SourceRef reference={method.source_ref} onOpen={onSource} label="Evaluated method source" />
          {(method.objective_markdown || method.target_markdown) && <details className="research-details empirical-method-definition" data-reading-anchor={`${anchor}:method-definition`}><summary>Model formulation and fitting criterion</summary>{method.objective_markdown && <ResearchDocument text={method.objective_markdown} />}{method.target_markdown && <ResearchDocument text={method.target_markdown} />}<SourceRef reference={method.source_ref} onOpen={onSource} label="Method formulation source" /></details>}</> : <p className="note">No mathematical formulation is available from the method frozen for this evaluation.</p>}
      </section>
      <section className="empirical-overview-section"><h3>What was developed and tested</h3>{summary.implementation_markdown ? <><ResearchDocument text={summary.implementation_markdown} />{source("implementation_markdown")}</> : <p className="note">This saved evaluation has no separate authored account of its implementation and completed experiments.</p>}
        {dataSources.length > 0 && <p className="note">Recorded data: {dataSources.map((entry) => `${entry.label || "Unnamed data source"} (${humanLabel(entry.origin)})`).join("; ")}</p>}
        {record.actual_data_application && <div className="empirical-actual-data"><h4>Actual data</h4><p className="note">{{ analyzed: "Analyzed", supplied_not_analyzed: "Supplied but not analyzed", not_supplied: "No actual data supplied" }[record.actual_data_application.status] || "Application status not recorded"}</p><ResearchDocument text={record.actual_data_application.summary_markdown} /></div>}
      </section>
      {conciseOutcome && <section className="empirical-overview-section"><h3>Current finding and scope</h3><ResearchDocument text={outcome.conclusion} /><SourceRef reference={record.generation_ref && { ...record.generation_ref, entry_pointer: "/scientific_outcome/conclusion" }} onOpen={onSource} label="Conclusion source" /><ResearchDocument text={outcome.scope} /><SourceRef reference={record.generation_ref && { ...record.generation_ref, entry_pointer: "/scientific_outcome/scope" }} onOpen={onSource} label="Scope source" /></section>}
      {questionIds.length > 0 && <details className="research-details empirical-question-links" data-reading-anchor={`${anchor}:questions`}><summary>Explore evaluation questions</summary><div className="btnrow empirical-support-links">{questionLinks.map((question) => <ActionButton action="details" variant="link" key={question.id || question.question_id || question.test_id} onClick={() => onSelect?.(question.id || question.question_id || question.test_id)}>{question.question || question.title || question.hypothesis || "Evaluation question"}</ActionButton>)}</div>{questionLinks.length < questionIds.length && <p className="note">Some linked evaluation questions are unavailable in this saved account.</p>}</details>}
    </>}
  </div></section>;
}

export function EmpiricalFullInterpretation({ record, onSource }) {
  const summary = record?.decision_summary;
  if (!summary) return null;
  const theory = summary.theory_relation; const outcome = record.scientific_outcome;
  const conciseOutcome = [outcome?.conclusion, outcome?.scope].every((text) => typeof text === "string" && text.trim());
  const anchor = `evaluation:${record.generation_ref?.generation_id || record.branch || "overview"}`;
  const source = (field) => <SourceRef reference={record.generation_ref && { ...record.generation_ref, entry_pointer: `/decision_summary/${field}` }} onOpen={onSource} label="Interpretation source" />;
  return <details className="research-details empirical-full-interpretation" data-reading-anchor={`${anchor}:full-interpretation`}><summary>Full interpretation and evaluation purpose</summary><section className="empirical-overview-section"><h3>Numerical findings and limitations</h3>{["conclusion_markdown", "tradeoff_markdown", "limitations_markdown", "intent_markdown"].filter((field) => summary[field]).map((field) => <div key={field}><ResearchDocument text={summary[field]} />{source(field)}</div>)}</section>{outcome && !conciseOutcome && <><ResearchDocument text={outcome.conclusion} /><ResearchDocument text={outcome.scope} /></>}
    {theory ? <section><h3>Relationship to the theory</h3><p className="note">{{ unavailable: "No Phase 3 theory was available", not_tested: "Available theory was not tested", tested: "Evidence examines specific theory claims" }[theory.status] || "Theory relationship as recorded"}</p><ResearchDocument text={theory.explanation_markdown} />{source("theory_relation")}<p className="note">Numerical evidence is not a proof.</p></section> : <p className="note">This saved account does not state whether Phase 3 theory was available or tested.</p>}
  </details>;
}
