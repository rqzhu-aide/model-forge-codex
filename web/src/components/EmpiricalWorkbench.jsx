import React, { useEffect, useId, useRef, useState } from "react";
import { diagnosticOverview, fmtMs, humanLabel, scoped } from "../research";
import { coverageForTab, coverageHomeTab, coverageTab, diagnosticsForQuestion, exhibitKey, exhibitsForQuestion, numericalSectionTopics, questionDataLabel, questionDataOrigins, questionHomeTab, questionOutcome, questionTopics, referencedCoverageExhibits, routeEmpiricalExhibits } from "../empirical";
import { DiagnosticsTables } from "./PhaseEvidence";
import { Outcome, ResearchInline, SourceRef } from "./Shared";
import ResearchDocument, { EmpiricalSourceProvider } from "./EmpiricalDocument";
import EmpiricalQuestion, { EmpiricalDecisionSummary, EmpiricalExhibit, EmpiricalFullInterpretation, EmpiricalNotation, EmpiricalQuestionSetup, EmpiricalQuestionTabs, EVIDENCE_TABS } from "./EmpiricalQuestion";
import { EmpiricalPlan } from "./EmpiricalProgress";
import ImplementationReading from "./ImplementationReading";
import { ActionButton } from "./Visuals";
import { hasSharedNotation } from "../sharedNotation";
import EmpiricalReadingButton, { empiricalReadingSize } from "./EmpiricalReading";
import CompactEmpiricalExhibit from "./CompactEmpiricalExhibit";
import { primaryEmpiricalExhibits } from "../compactEmpiricalResults";

const hasInlineResult = (exhibit) => exhibit.source_verified !== false && !exhibit.source_error && Boolean(
  exhibit.table?.columns?.length && exhibit.table?.rows?.length
  || exhibit.artifact_url && (exhibit.media_type || "").startsWith("image/"));

function evaluationSources({ branch, diagnostics = [], exhibits = [], questions = [], cases = [], protocols = [] }) {
  const diags = scoped(diagnostics, branch, "P4"); const figures = [...new Map(scoped(exhibits, branch, "P4").map((exhibit) => [exhibitKey(exhibit), exhibit])).values()];
  const protocolList = protocols.filter((item) => !item.branch || item.branch === branch);
  const caseList = [...new Map([...cases, ...protocolList.flatMap((p) => [...(p.cases || []), ...(p.amendments || []).flatMap((item) => item.added_cases || [])].map((item) => ({ ...item, branch: p.branch, generation_ref: p.generation_ref })))].filter((item) => !item.branch || item.branch === branch).map((item) => [JSON.stringify([item.generation_ref?.run_id, item.generation_ref?.package_id, item.case_id || item.id]), item])).values()];
  const authored = questions.filter((item) => (!item.branch || item.branch === branch) && (!item.phase || item.phase === "P4"));
  const declared = authored.length ? authored : protocolList.flatMap((p) => (p.claim_tests || []).map((item) => ({ ...item, question_id: item.test_id, title: item.hypothesis, caption: item.design, scope: p.scope, statement_ids: item.target_statement_ids, case_ids: caseList.filter((c) => c.test_ids?.includes(item.test_id)).map((c) => c.case_id), generation_ref: p.generation_ref })));
  const items = declared.map((item, index) => ({ ...item, id: item.question_id || item.test_id || item.id || `question-${index}`, title: item.question || item.title || item.hypothesis || item.label || "Evaluation question", exhibits: exhibitsForQuestion(item, figures) }));
  return { diags, figures, protocolList, caseList, items, ungrouped: figures.filter((exhibit) => !items.some((item) => item.exhibits.includes(exhibit))) };
}

const protocolFields = (record, fields) => fields.flatMap(([key, title]) => {
  const value = record?.[key];
  if (value == null || value === "" || (Array.isArray(value) && !value.length)) return [];
  const text = typeof value === "number" || typeof value === "boolean" ? String(value) : Array.isArray(value) && value.every((item) => ["string", "number", "boolean"].includes(typeof item)) ? value.map(String) : value;
  return [{ title, text }];
});

function ProtocolDetails({ entries, compact = false }) {
  return <dl className={compact ? "empirical-setup-fields empirical-setting-summary" : "empirical-setup-fields"}>{entries.map((entry, index) => <div key={index}><dt><ResearchInline text={entry.title} /></dt><dd>{entry.body ? <ProtocolDetails entries={entry.body} /> : <ResearchDocument text={entry.text} />}</dd></div>)}</dl>;
}

export function focusHeadlineExhibit(target) {
  if (!target) return;
  for (let parent = target.parentElement; parent; parent = parent.parentElement) if (parent.tagName === "DETAILS") parent.open = true;
  target.focus({ preventScroll: true });
  target.scrollIntoView({ block: "start" });
}

export function ProtocolSetup({ protocol, onSource }) {
  const applicability = protocol.comparison_applicability;
  const source = (entry_pointer) => protocol.generation_ref && { ...protocol.generation_ref, entry_pointer };
  const settings = [
    ...protocolFields(protocol.data_or_simulation_unit, [["source_type", "Data source"], ["sample_sizes", "Sample sizes"]]),
    ...protocolFields({ baselines: (protocol.baselines || []).map((item) => item.name).filter(Boolean), metrics: (protocol.metrics || []).map((item) => item.name).filter(Boolean) }, [["baselines", "Comparators"], ["metrics", "Measures"]]),
    ...protocolFields(protocol.repetitions_and_uncertainty, [["repetitions", "Repetitions"], ["paired_design", "Paired comparisons"]]),
  ];
  const sections = [
    ["Implementation and checks", protocolFields(protocol.implementation_strategy, [["route", "Implementation route"], ["route_rationale", "Reason for this route"], ["packages", "Packages and versions"], ["strategy", "Prior project lineage"], ["verification_checks", "Planned checks"], ["changes_from_prior", "Changes to previous code"]])],
    ["Declared data sources", [...(protocol.data_sources || []), ...(protocol.amendments || []).flatMap((item) => item.added_data_sources || [])].map((item) => ({ title: item.label || item.data_source_id, body: protocolFields({ ...item, origin: humanLabel(item.origin) }, [["origin", "Origin"], ["description_markdown", "Description"], ["mapping_markdown", "Variable mapping"]]) }))],
    ["Data and simulation setting", protocolFields(protocol.data_or_simulation_unit, [["source_type", "Data source"], ["unit_definition", "Observation unit"], ["sampling_or_generation_process", "Sampling or generation"], ["sample_sizes", "Sample sizes"], ["independence_structure", "Dependence and pairing"], ["splits", "Data splits"], ["preprocessing", "Preprocessing"]])],
    ["Target", protocolFields(protocol.estimand, [["name", "Quantity estimated"], ["mathematical_definition", "Definition"], ["target_population_or_distribution", "Target population"], ["analysis_unit", "Analysis unit"], ["aggregation", "Summary across repetitions"], ["conditions", "Conditions"]])],
    ["Baselines and fairness", (protocol.baselines || []).map((item) => ({ title: item.name, body: protocolFields(item, [["rationale", "Why this baseline"], ["implementation_identity", "Implementation"], ["tuning_policy", "Tuning rule"], ["compute_budget", "Computation budget"]]) }))],
    ["Metrics", (protocol.metrics || []).map((item) => ({ title: item.name, body: protocolFields(item, [["definition", "Definition"], ["direction", "Preferred direction"], ["aggregation", "Summary across repetitions"], ["uncertainty_method", "Uncertainty"]]) }))],
    ["Tuning rule", protocolFields(protocol.tuning_budget, [["selection_data", "Data used for selection"], ["search_space", "Settings considered"], ["optimization_rule", "Selection rule"], ["maximum_trials", "Maximum trials"], ["compute_limit", "Computation limit"], ["fairness_rule", "Fairness across models"]])],
    ["Repetitions and uncertainty", protocolFields(protocol.repetitions_and_uncertainty, [["repetitions", "Repetitions"], ["random_seed_policy", "Random seeds"], ["paired_design", "Paired comparisons"], ["interval_or_error_method", "Uncertainty calculation"], ["target_precision", "Precision target"]])],
    ["Multiple comparisons", protocolFields(protocol.multiplicity, [["family_definition", "Comparisons considered together"], ["correction_method", "Adjustment"], ["decision_rule", "Interpretation rule"]])],
    ["Stopping rules", (protocol.stopping_rules || []).map((item) => ({ body: protocolFields(item, [["condition", "When to stop"], ["action", "What happens next"]]) }))],
    ["Checks against information leakage", (protocol.leakage_checks || []).map((item) => ({ body: protocolFields(item, [["risk", "Concern"], ["procedure", "Check"], ["failure_action", "Response to a failed check"]]) }))],
    ["Decision thresholds", (protocol.decision_thresholds || []).map((item) => ({ body: protocolFields(item, [["criterion", "Criterion"], ["interpretation", "Interpretation"]]) }))],
  ];
  return <section className="empirical-protocol-setup"><h3>{protocol.title || "Study setup"}</h3>{[protocol.research_question, protocol.scope, protocol.scope_justification, protocol.body_md || protocol.body || protocol.summary].filter(Boolean).map((text, index) => <ResearchDocument key={index} text={text} />)}{settings.length > 0 && <ProtocolDetails entries={settings} compact />}
    {applicability && <section className="empirical-comparison-scope"><h4>Comparison scope</h4><p>{applicability.required === true ? "Comparison is required for this evaluation." : applicability.required === false ? "Comparison is not required for this evaluation." : "The comparison requirement is not recorded."}</p><ResearchDocument text={applicability.reason} /><SourceRef reference={source("/comparison_applicability")} onOpen={onSource} label="Comparison scope source" /></section>}
    {protocol.deviations?.length > 0 && <details className="research-details empirical-protocol-deviations"><summary>Protocol departures ({protocol.deviations.length})</summary>{protocol.deviations.map((departure, index) => <section key={departure.deviation_id || index}><ProtocolDetails entries={protocolFields({ ...departure, disposition: departure.disposition && humanLabel(departure.disposition), affected_questions: departure.affected_test_ids?.map((test) => protocol.claim_tests?.find((item) => item.test_id === test)?.hypothesis || humanLabel(test)) }, [["description", "Departure"], ["reason", "Reason"], ["impact_assessment", "Impact on interpretation"], ["disposition", "Disposition"], ["affected_questions", "Affected questions"]])} /><SourceRef reference={source(`/deviations/${index}`)} onOpen={onSource} label="Departure source" /></section>)}</details>}
    {sections.some(([, body]) => body.length) && <details className="research-details empirical-protocol-details"><summary>Full setup and comparison rules</summary>{sections.filter(([, body]) => body.length).map(([title, body]) => <section key={title}><h4>{title}</h4><ProtocolDetails entries={body} /></section>)}</details>}<SourceRef reference={protocol.generation_ref} onOpen={onSource} /></section>;
}
export function CompleteNumbers({ diagnostics, cases, protocols = [], onSource }) {
  if (!diagnostics.length) return null;
  const overview = diagnosticOverview(diagnostics);
  return <div className="empirical-complete-numbers"><p className="note">Across the evaluation: {overview.stabilityRows ? `${overview.unstable} verdict flips / ${overview.stabilityRows} comparisons` : "Repetition stability not recorded"}. {overview.recordedChecks ? `${overview.incompleteOrNonconverged} incomplete or nonconverged / ${overview.recordedChecks} recorded checks` : "Completion totals not recorded"}. {diagnostics.some((item) => typeof item.runtime?.total_ms === "number") ? `Sum of recorded case times: ${fmtMs(diagnostics.reduce((sum, item) => sum + (item.runtime?.total_ms || 0), 0))}.` : "Case times not recorded."}</p>{diagnostics.map((diagnostic, index) => {
    const ref = diagnostic.generation_ref;
    const matches = (item) => ref?.run_id && item.generation_ref?.run_id === ref.run_id && item.generation_ref.package_id === ref.package_id
      && (!ref.branch || !item.generation_ref.branch || item.generation_ref.branch === ref.branch)
      && (!ref.phase || !item.generation_ref.phase || item.generation_ref.phase === ref.phase);
    const protocol = protocols.find(matches);
    const metrics = Object.fromEntries([...(protocol?.metrics || []), ...(protocol?.amendments || []).flatMap((item) => item.added_metrics || [])].map((item) => [item.metric_id, item]));
    const names = Object.fromEntries(cases.filter((item) => !item.generation_ref || matches(item)).map((item) => [item.case_id || item.id, item.label || item.title || item.case_id || item.id]));
    const namedRows = (rows) => (rows || []).map((row) => ({ ...row, case_id: names[row.case_id] || row.case_id }));
    return <section key={diagnostic.diagnostics_id || index}><DiagnosticsTables metrics={metrics} d={{ ...diagnostic, headline_numbers: namedRows(diagnostic.headline_numbers), stability: namedRows(diagnostic.stability), ...(diagnostic.runtime ? { runtime: { ...diagnostic.runtime, per_case: namedRows(diagnostic.runtime.per_case) } } : {}) }} /><SourceRef reference={ref} onOpen={onSource} /><details className="research-details"><summary>Complete numerical source</summary><pre className="record">{JSON.stringify(diagnostic, null, 2)}</pre></details></section>;
  })}</div>;
}

export function diagnosticReadingLabel(diagnostics) {
  const tables = diagnostics.reduce((count, record) => count + [record.headline_numbers?.length, record.stability?.length, record.solver_health?.length, record.runtime].filter(Boolean).length, 0);
  const rows = diagnostics.reduce((count, record) => count + (record.headline_numbers?.length || 0) + (record.stability?.length || 0) + (record.solver_health?.length || 0) + (record.runtime ? (record.runtime.per_case?.length || 0) + 1 : 0), 0);
  return `${diagnostics.length} ${diagnostics.length === 1 ? "record" : "records"} · ${tables} ${tables === 1 ? "table" : "tables"} · ${rows} ${rows === 1 ? "row" : "rows"}`;
}

export function EmpiricalQuestionDesignDocument({ question, cases, onSource }) {
  // A supporting reader belongs to the frozen evaluation. Always inspect its
  // tested generation, even if a newer theory becomes current while it is open.
  return <EmpiricalQuestionSetup question={question} cases={cases} onSource={onSource}
    onTheory={(statementId, reference) => onSource?.(reference, statementId)} />;
}

export function ExperimentSetupDocument({ protocols = [], progressData, onSource }) {
  const plans = protocols.filter((protocol) => protocol.work_items?.length || protocol.amendments?.length);
  return <div className="empirical-study-background">
    {progressData && <section className="empirical-current-plan"><h3>Completed evaluation plan</h3><EmpiricalPlan progress={progressData} settled compact /></section>}
    {plans.map((plan, index) => <section className="empirical-current-plan" key={plan.protocol_id || index}><h3>{plan.title || "Recorded experiment plan"}</h3><EmpiricalPlan progress={{ plan }} planOnly compact /><SourceRef reference={plan.generation_ref} onOpen={onSource} /></section>)}
    {protocols.map((protocol, index) => <ProtocolSetup key={protocol.protocol_id || index} protocol={protocol} onSource={onSource} />)}
  </div>;
}

export default function EmpiricalWorkbench({ diagnostics = [], exhibits = [], questions = [], cases = [], protocols = [], summaries = [], implementations = [], progress = null, progressData = null, progressState, progressRun, issues = null, furtherWork = null, awaitingDirection = false, loadErrors = [], branch, onSource, onRequest, onTheory, decisionQuestions = [], onDecision, initialTab, reading = {}, onReadingChange }) {
  const { diags, figures, protocolList, caseList, items } = evaluationSources({ branch, diagnostics, exhibits, questions, cases, protocols });
  const summary = summaries.filter((item) => !item.branch || item.branch === branch).find((item) => item.decision_summary);
  const coverage = summary?.decision_summary?.coverage || [];
  const hasNotation = hasSharedNotation(summary) || typeof summary?.decision_summary?.notation_markdown === "string" && Boolean(summary.decision_summary.notation_markdown.trim());
  const id = useId(); const panel = useRef(null);
  const [focusQuestion, setFocusQuestion] = useState(null); const [focusExhibit, setFocusExhibit] = useState(null); const [notationOpen, setNotationOpen] = useState(null); const [focusTab, setFocusTab] = useState(null);
  const normalizeTab = (value) => ({ results: "comparisons", design: "setup", review: "comparisons", next: "comparisons" }[value] || (EVIDENCE_TABS.some(([key]) => key === value) ? value : null));
  const [tab, setTab] = useState(() => normalizeTab(reading.tab || initialTab) || "setup");
  const explore = (value) => { setTab(value); setFocusTab(value); };
  const readingChange = useRef(onReadingChange); readingChange.current = onReadingChange;
  useEffect(() => { if (normalizeTab(tab)) readingChange.current?.({ tab }); }, [tab]);
  useEffect(() => { setTab(normalizeTab(reading.tab || initialTab) || "setup"); setFocusQuestion(null); setFocusExhibit(null); setNotationOpen(false); }, [branch]);
  useEffect(() => { if (focusQuestion) { const target = [...(panel.current?.querySelectorAll("[data-question-id]") || [])].find((element) => element.dataset.questionId === focusQuestion); if (target?.tagName === "DETAILS") target.open = true; focusHeadlineExhibit(target); target?.querySelector("summary")?.focus({ preventScroll: true }); setFocusQuestion(null); } }, [tab, focusQuestion]);
  useEffect(() => { if (focusExhibit) { focusHeadlineExhibit(document.getElementById(focusExhibit)); setFocusExhibit(null); } }, [tab, focusExhibit]);
  useEffect(() => { if (focusTab) { focusHeadlineExhibit(document.getElementById(`${id}-${focusTab}`) || document.getElementById(`${id}-scope`)); setFocusTab(null); } }, [tab, focusTab, id]);
  const choose = (questionId) => { if (items.some((item) => item.id === questionId)) setFocusQuestion(questionId); };
  const routed = routeEmpiricalExhibits(figures, items, coverage, summary);
  const exhibitAnchor = (entry) => `${id}-exhibit-${encodeURIComponent(entry.key)}`;
  const showExhibit = (exhibit) => { const entry = routed.find((item) => item.key === exhibitKey(exhibit)); if (entry) { setTab(entry.topic); setFocusExhibit(exhibitAnchor(entry)); } };
  const headlineIds = summary?.decision_summary?.headline_exhibit_ids || [];
  const missingHeadlines = headlineIds.filter((exhibitId) => !figures.some((exhibit) => exhibit.exhibit_id === exhibitId && exhibit.source_verified === true && !exhibit.source_error && exhibit.generation_ref?.run_id === summary?.generation_ref?.run_id && exhibit.generation_ref?.package_id === summary?.generation_ref?.package_id));
  const primaryExhibits = primaryEmpiricalExhibits(routed, summary);
  const orderedExhibits = [...routed].sort((a, b) => { const rank = (entry) => primaryExhibits.includes(entry) ? primaryExhibits.indexOf(entry) : primaryExhibits.length + (headlineIds.includes(entry.exhibit.exhibit_id) ? headlineIds.indexOf(entry.exhibit.exhibit_id) : headlineIds.length); return rank(a) - rank(b); });
  const topics = numericalSectionTopics(coverage, items, routed, summary);
  const sections = [...EVIDENCE_TABS, ["actual_data", "Actual-data application"]].filter(([key]) => topics.includes(key)).sort(([a], [b]) => Number(b === "comparisons") - Number(a === "comparisons"));
  const sectionCoverage = (key) => coverageForTab(coverage, key, items, summary);
  const accountHome = (entry) => { const home = coverageHomeTab(entry, items, summary); return sections.some(([key]) => key === home) ? home : "scope"; };
  const scopeCoverage = coverage.filter((entry) => accountHome(entry) === "scope");
  const implementationList = implementations.filter((record) => !record.branch || record.branch === branch);
  const producingRef = summary?.generation_ref || protocolList[0]?.generation_ref;
  const anchor = `evaluation:${branch}:${producingRef?.run_id || producingRef?.generation_id || "unpublished"}:${producingRef?.package_id || ""}`;
  const currentPlan = progressData && <section className="empirical-current-plan"><h3>{progressState === "published" ? "Completed evaluation plan" : "Current evaluation plan"}</h3>{progressState !== "published" && <p className="note">This plan and its progress are provisional. Published findings above retain their original evidence.</p>}<EmpiricalPlan progress={progressData} settled={["published", "assessed", "failed", "cancelled"].includes(progressState)} compact /></section>;
  const empty = { setup: "No synthetic example or implementation-check answer is recorded.", comparisons: "No performance evidence is recorded. Unstudied performance remains unassessed.", computation: "No computation-cost evidence is recorded. Experiment-budget time does not establish per-fit method cost.", tuning: "No tuning answer is recorded. Tuning remains unassessed unless the saved protocol states it is not applicable.", sensitivity: "No robustness evidence is recorded. Behavior outside the studied conditions remains unassessed." };
  const renderExhibit = (entry) => <div key={entry.key} className="empirical-canonical-exhibit">{entry.association === "related" && <p className="note">Related result, linked by the recorded test or case. A more specific topic assignment is unavailable.</p>}<CompactEmpiricalExhibit exhibit={entry.exhibit} primary={primaryExhibits.includes(entry)} anchorId={exhibitAnchor(entry)} readingAnchor={`${anchor}:exhibit:${entry.key}`} onSource={onSource} /></div>;
  const accountAnchor = (entry) => `${id}-coverage-${coverage.indexOf(entry)}`;
  const renderAccount = (entry, ownedExhibits = []) => <section className="empirical-topic-account" key={coverage.indexOf(entry)} id={accountAnchor(entry)} tabIndex={-1} data-reading-anchor={`${anchor}:coverage:${entry.dimension}:${coverage.filter((item) => item.dimension === entry.dimension).indexOf(entry)}`}>
    <h4>{humanLabel(entry.dimension)} <span className="note">Research Lead · {humanLabel(entry.status || "Assessment not recorded")}</span></h4>
    {entry.summary ? <ResearchDocument text={entry.summary} /> : <p className="note">No authored account is recorded for this topic.</p>}
    {ownedExhibits.map(renderExhibit)}
    {referencedCoverageExhibits(entry, figures, summary).filter((exhibit) => !ownedExhibits.some((item) => item.key === exhibitKey(exhibit))).map((exhibit) => <p className="empirical-shared-result" key={exhibitKey(exhibit)}><ActionButton action="details" variant="link" onClick={() => showExhibit(exhibit)}>View {exhibit.title || "recorded result"} in {EVIDENCE_TABS.find(([key]) => key === routed.find((item) => item.key === exhibitKey(exhibit))?.topic)?.[1] || (routed.find((item) => item.key === exhibitKey(exhibit))?.topic === "actual_data" ? "Actual-data application" : "Other recorded results")}</ActionButton></p>)}
    {(entry.limitation_markdown || entry.limitations_markdown) && <section className="empirical-topic-continuation"><h5>Limitations</h5><ResearchDocument text={entry.limitation_markdown || entry.limitations_markdown} /></section>}
    {entry.implication_markdown && <section className="empirical-topic-continuation"><h5>Implication</h5><ResearchDocument text={entry.implication_markdown} /></section>}
    <SourceRef reference={summary?.generation_ref && { ...summary.generation_ref, entry_pointer: `/decision_summary/coverage/${coverage.indexOf(entry)}` }} onOpen={onSource} label={coverageTab(entry.dimension) === "actual_data" ? "Actual-data coverage source" : "Coverage source"} />
  </section>;
  const renderQuestion = (question) => {
    const evidence = diagnosticsForQuestion(question, diags, caseList, protocolList);
    const protocol = protocolList.find((item) => item.generation_ref?.run_id && item.generation_ref.run_id === question.generation_ref?.run_id && item.generation_ref.package_id === question.generation_ref?.package_id);
    const questionCoverage = coverage.filter((entry) => entry.question_ids?.includes(question.id));
    const designSettings = caseList.filter((item) => question.case_ids?.includes(item.case_id)).length;
    const designSize = empiricalReadingSize([question.result?.design_markdown || question.caption || question.design, question.result?.conditions_markdown || question.scope || question.conditions, question.falsification_rule], [designSettings ? `${designSettings} experiment ${designSettings === 1 ? "setting" : "settings"}` : "", question.statement_ids?.length ? `${question.statement_ids.length} tested ${question.statement_ids.length === 1 ? "claim" : "claims"}` : ""]);
    return <details className="question-detail empirical-question-row" key={question.id} data-question-id={question.id} tabIndex={-1} data-reading-anchor={`${anchor}:question:${question.id}`}><summary><span className="empirical-question-title">{question.title}</span><span className="empirical-question-state">{question.result && <span>{question.review?.review_markdown || question.review?.theorist_findings_markdown ? "Analyst account and scientific review" : "Analyst account"}</span>}<Outcome state={questionOutcome(question)} /><span>{questionDataLabel(questionDataOrigins(question, caseList, protocolList))}</span>{questionCoverage.length ? questionCoverage.map((entry, index) => <span key={index}>{humanLabel(entry.dimension)}: {humanLabel(entry.status)}</span>) : <span>Coverage not recorded</span>}</span></summary><div className="empirical-question-answer"><QuestionTheoryContext question={question} onSource={onSource} /><EmpiricalQuestion question={question} cases={caseList} diagnostics={evidence.diagnostics} hasMapping={evidence.hasMapping} protocol={protocol} onSource={onSource} onRequest={onRequest} onTheory={onTheory} showEvidence={false} showRecordedValues={!question.exhibits.some(hasInlineResult)} onExhibit={showExhibit} />{designSize ? <div className="reading-toolbar empirical-support-toolbar"><EmpiricalReadingButton kind="p4-question-design" title="Experiment design and sources" sizeLabel={designSize} input={{ question, cases: caseList }} renderBody={(input, openSource) => <EmpiricalQuestionDesignDocument {...input} onSource={openSource} />} onSource={onSource} /></div> : <p className="note">No separate experiment design or settings are recorded for this question.</p>}</div></details>;
  };
  const sources = { branch, onSource, decisionQuestions, onDecision, artifacts: summary?.source_artifacts || [], records: [summary, ...protocolList, ...items.map((item) => item.result), ...items.map((item) => item.review), ...implementationList, ...implementationList.map((item) => item.theorist_review)].filter(Boolean), files: [...(summary?.run_sources || []), ...figures, ...implementationList.flatMap((record) => (record.files || []).map((file) => ({ ...file, branch: record.generation_ref?.branch || record.branch })))] };
  const hasInterpretation = Boolean(summary?.decision_summary);
  const hasSetupReading = protocolList.length > 0 || progressData && progressState === "published";
  return <EmpiricalSourceProvider value={sources}><EmpiricalDecisionSummary record={summary} questions={items} dataSources={protocolList.flatMap((protocol) => [...(protocol.data_sources || []), ...(protocol.amendments || []).flatMap((item) => item.added_data_sources || [])])} onSelect={choose} onSource={onSource} onNotation={() => setNotationOpen(summary)} onExplore={explore} awaitingDirection={awaitingDirection} hasProgress={Boolean(progressData)} progressState={progressState} progressRun={progressRun} branch={branch} />{progress}
    <section className="card empirical-code-card" data-card-role="research" data-reading-anchor={`${anchor}:implementation`}><div className="card-heading"><h2>Implementation and Code</h2></div><div className="body"><ImplementationReading records={implementationList} protocols={protocolList} summary={summary} hasNotation={hasNotation} onNotation={() => setNotationOpen(summary)} onSource={onSource} /></div></section>
    <section className="card empirical-workspace" data-card-role="research"><div className="card-heading"><h2>Experiments and Results</h2></div><div className="body">
      <EmpiricalQuestionTabs id={id} selected={tab} onSelect={explore} questions={items} coverage={coverage} summary={summary} sections={[...sections, ["scope", "Other scope"]]} />
      {(hasNotation || diags.length > 0 || hasInterpretation || hasSetupReading) && <div className="reading-toolbar empirical-support-toolbar empirical-support-row" aria-label="Experiment supporting documents">
        {hasNotation && <ActionButton action="details" variant="link" aria-haspopup="dialog" onClick={() => setNotationOpen(summary)}>Notation</ActionButton>}
        {diags.length > 0 && <EmpiricalReadingButton kind="p4-diagnostics" title="Numerical results and diagnostics" sizeLabel={diagnosticReadingLabel(diags)} input={{ diagnostics: diags, cases: caseList, protocols: protocolList }} renderBody={(input, openSource) => <CompleteNumbers {...input} onSource={openSource} />} onSource={onSource} />}
        <EmpiricalFullInterpretation record={summary} onSource={onSource} />
        {hasSetupReading && <EmpiricalReadingButton kind="p4-experiment-setup" title="Setup and recorded plans" sizeLabel={`${protocolList.length} ${protocolList.length === 1 ? "protocol" : "protocols"}${progressData && progressState === "published" ? " · Completed evaluation plan" : ""}`} input={{ protocols: protocolList, progressData: progressState === "published" ? progressData : null }} renderBody={(input, openSource) => <ExperimentSetupDocument {...input} onSource={openSource} />} onSource={onSource} />}
      </div>}
      {scoped(loadErrors, branch, "P4").map((issue, index) => <p className="note warn" role="alert" key={index}>A source from this evaluation could not be verified or loaded: {issue.message}.</p>)}
      {missingHeadlines.length > 0 && <p className="note warn" role="alert">{missingHeadlines.length} referenced result {missingHeadlines.length === 1 ? "exhibit could" : "exhibits could"} not be verified or loaded. Inspect the retained sources before interpreting {missingHeadlines.length === 1 ? "it" : "them"}.</p>}
      <div className="empirical-numerical-section" ref={panel}>
        {sections.map(([key, label]) => {
          const relatedAccounts = sectionCoverage(key);
          const accounts = relatedAccounts.filter((entry) => accountHome(entry) === key);
          const topicExhibits = orderedExhibits.filter((entry) => entry.topic === key);
          const homes = new Map(topicExhibits.map((entry) => [entry.key, accounts.find((account) => referencedCoverageExhibits(account, [entry.exhibit], summary).length)]));
          const topicQuestions = items.filter((question) => questionTopics(question, coverage).includes(key));
          return <section className="empirical-reading-section" key={key} id={`${id}-${key}`} tabIndex={-1} data-reading-anchor={`${anchor}:topic:${key}`} aria-labelledby={`${id}-${key}-heading`}>
            <h3 id={`${id}-${key}-heading`}>{label}</h3>
            {accounts.map((entry) => renderAccount(entry, topicExhibits.filter((exhibit) => homes.get(exhibit.key) === entry)))}
            {relatedAccounts.filter((entry) => accountHome(entry) !== key).map((entry) => <p className="empirical-shared-account" key={coverage.indexOf(entry)}><ActionButton action="details" variant="link" onClick={() => { setTab(accountHome(entry)); setFocusExhibit(accountAnchor(entry)); }}>Read {humanLabel(entry.dimension)} in {sections.find(([topic]) => topic === accountHome(entry))?.[1] || "Other scope"}</ActionButton></p>)}
            {!relatedAccounts.length && <p className="note">{key === "setup" ? protocolList.length ? "No authored experimental setup is recorded in the primary account. The complete saved protocol remains available in Setup and recorded plans." : "No authored experimental setup or complete protocol is recorded for this evaluation." : "No authored topic account is recorded. The saved exhibits and per-test accounts retain their original scope."}</p>}
            {topicExhibits.filter((entry) => !homes.get(entry.key)).map(renderExhibit)}
            {topicQuestions.length > 0 && <div className="empirical-topic-accounts"><h4>Supporting accounts and scientific reviews</h4>{topicQuestions.map((question) => questionHomeTab(question, coverage) === key ? renderQuestion(question) : <p key={question.id} className="empirical-shared-question"><ActionButton action="details" variant="link" onClick={() => choose(question.id)}>Read the full answer: {question.title}</ActionButton></p>)}</div>}
          </section>;
        })}
        <section className="empirical-reading-section empirical-other-scope" id={`${id}-scope`} tabIndex={-1} data-reading-anchor={`${anchor}:scope`} aria-labelledby={`${id}-scope-heading`}><h3 id={`${id}-scope-heading`}>Other scope</h3>
          {scopeCoverage.map((entry) => renderAccount(entry))}
          {EVIDENCE_TABS.filter(([key]) => key !== "setup" && !topics.includes(key) && !scopeCoverage.some((entry) => sectionCoverage(key).includes(entry))).map(([key, label]) => <p className="note" key={key}><b>{label}:</b> {empty[key]}</p>)}
          {!scopeCoverage.length && EVIDENCE_TABS.every(([key]) => topics.includes(key)) && <p className="note">No additional unassessed topic is recorded in this account.</p>}
          {items.filter((question) => !sections.some(([key]) => questionHomeTab(question, coverage) === key)).map(renderQuestion)}
        </section>
        {routed.some((entry) => entry.topic === "other") && <details className="research-details empirical-other-results" data-reading-anchor={`${anchor}:other-results`}><summary>Other recorded results</summary><p className="note">These results have no unambiguous topic assignment. Their saved sources and original scope are retained.</p>{orderedExhibits.filter((entry) => entry.topic === "other").map(renderExhibit)}</details>}
      </div>
      {currentPlan && progressState !== "published" && currentPlan}
      {!protocolList.length && !items.length && !figures.length && !summary && !progressData && <p className="note">{awaitingDirection ? "The evaluation is waiting for your direction. Its setup will appear when the analyst saves a plan." : "No experiments have been completed for this model yet. The study setup will appear here when it is recorded."}</p>}
    </div></section>{issues}{furtherWork}{notationOpen && <EmpiricalNotation record={notationOpen} onSource={onSource} onClose={() => setNotationOpen(null)} />}</EmpiricalSourceProvider>;
}

// History carries provenance; all quantitative displays belong to Experiments.
export function EmpiricalEvaluationHistory(props) {
  const { diags, protocolList } = evaluationSources(props); const { onSource } = props;
  return <details className="research-details complete-evaluation" data-card-role="history"><summary>Evaluation provenance and original sources</summary><p className="note">All numerical results and recorded diagnostics are available in Experiments and Results.</p>{diags.map((diagnostic, index) => <SourceRef key={diagnostic.diagnostics_id || index} reference={diagnostic.generation_ref} onOpen={onSource} label="Numerical source" />)}{protocolList.map((protocol, index) => <SourceRef key={protocol.protocol_id || index} reference={protocol.generation_ref} onOpen={onSource} label={protocol.title || "Original protocol and cases"} />)}</details>;
}

function QuestionTheoryContext({ question, onSource }) {
  const context = question.theory_context;
  if (!context) return null;
  const labels = { current: "Uses the current theory", unchanged: "Linked theory is unchanged", affected: "Reassessment needed after a theory change", early_exploration: "Early exploration", method_changed: "A newer model version is selected", unknown: "Theory comparison is unavailable" };
  return <div className="context-note question-theory-context"><b>{labels[context.state] || "Theory context"}</b>{context.message && <p>{context.message}</p>}{context.tested_ref && <div className="question-theory-source"><span className="note">Theory used for this evaluation</span><SourceRef reference={context.tested_ref} onOpen={onSource} /></div>}{context.affected_statement_ids?.length > 0 && <p className="note">Claims to reassess: {context.affected_statement_ids.map(humanLabel).join(", ")}.</p>}</div>;
}
