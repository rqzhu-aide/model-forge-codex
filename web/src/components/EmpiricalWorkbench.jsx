import React, { useEffect, useId, useRef, useState } from "react";
import { diagnosticOverview, fmtMs, humanLabel, scoped } from "../research";
import { coverageForTab, coverageTab, diagnosticsForQuestion, exhibitKey, exhibitsForQuestion, questionDataLabel, questionDataOrigins, questionHomeTab, questionOutcome, questionTopics, referencedCoverageExhibits, routeEmpiricalExhibits } from "../empirical";
import { DiagnosticsTables } from "./PhaseEvidence";
import { Outcome, SourceRef } from "./Shared";
import ResearchDocument, { EmpiricalSourceProvider } from "./EmpiricalDocument";
import EmpiricalQuestion, { EmpiricalDecisionSummary, EmpiricalExhibit, EmpiricalFullInterpretation, EmpiricalQuestionSetup, EmpiricalQuestionTabs, EVIDENCE_TABS, evidenceTab } from "./EmpiricalQuestion";
import { EmpiricalPlan } from "./EmpiricalProgress";
import ImplementationReading from "./ImplementationReading";
import { ActionButton } from "./Visuals";

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
  return <dl className={compact ? "empirical-setup-fields empirical-setting-summary" : "empirical-setup-fields"}>{entries.map((entry, index) => <div key={index}><dt>{entry.title}</dt><dd>{entry.body ? <ProtocolDetails entries={entry.body} /> : <ResearchDocument text={entry.text} />}</dd></div>)}</dl>;
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
function TopicProtocol({ protocol, tab, onSource }) {
  const sources = [...(protocol.data_sources || []), ...(protocol.amendments || []).flatMap((entry) => entry.added_data_sources || [])];
  const synthetic = sources.length ? sources.every((source) => source.origin === "synthetic") : ["simulation", "synthetic"].includes(protocol.data_or_simulation_unit?.source_type);
  const fields = tab === "setup" ? [
    ...protocolFields(protocol.data_or_simulation_unit, [["sampling_or_generation_process", "Data generation"], ["unit_definition", "Observation unit"], ["sample_sizes", "Sample sizes"], ["independence_structure", "Independence and pairing"], ["splits", "Data splits"]]),
    ...protocolFields({ baselines: (protocol.baselines || []).map((item) => item.name).filter(Boolean) }, [["baselines", "Comparators"]]),
    ...protocolFields(protocol.repetitions_and_uncertainty, [["repetitions", "Repetitions"], ["paired_design", "Paired comparisons"]]),
  ] : tab === "tuning" ? protocolFields(protocol.tuning_budget, [["selection_data", "Data used for selection"], ["search_space", "Settings considered"], ["optimization_rule", "Selection rule"], ["maximum_trials", "Maximum trials"], ["compute_limit", "Computation limit"], ["fairness_rule", "Fairness across models"]]) : [];
  return fields.length ? <section className="empirical-topic-protocol"><h3>{tab === "setup" ? synthetic ? "Synthetic design" : "Study design" : "Tuning protocol"}</h3><ProtocolDetails entries={fields} compact /><SourceRef reference={tab === "tuning" && protocol.generation_ref ? { ...protocol.generation_ref, entry_pointer: "/tuning_budget" } : protocol.generation_ref} onOpen={onSource} label="Protocol source" /></section> : null;
}

function CompleteNumbers({ diagnostics, cases, onSource }) {
  if (!diagnostics.length) return null;
  const overview = diagnosticOverview(diagnostics);
  const names = Object.fromEntries(cases.map((item) => [item.case_id || item.id, item.label || item.title || humanLabel(item.case_id || item.id)]));
  return <details className="research-details empirical-complete-numbers"><summary>Complete numerical results and recorded diagnostics</summary><p className="note">Across the evaluation: {overview.stabilityRows ? `${overview.unstable} verdict flips / ${overview.stabilityRows} comparisons` : "Repetition stability not recorded"}. {overview.recordedChecks ? `${overview.incompleteOrNonconverged} incomplete or nonconverged / ${overview.recordedChecks} recorded checks` : "Completion totals not recorded"}. {diagnostics.some((item) => typeof item.runtime?.total_ms === "number") ? `Sum of recorded case times: ${fmtMs(diagnostics.reduce((sum, item) => sum + (item.runtime?.total_ms || 0), 0))}.` : "Case times not recorded."}</p>{diagnostics.map((diagnostic, index) => <section key={diagnostic.diagnostics_id || index}><DiagnosticsTables d={{ ...diagnostic, headline_numbers: (diagnostic.headline_numbers || []).map((row) => ({ ...row, case_id: names[row.case_id] || humanLabel(row.case_id), metric: diagnostic.metric_labels?.[row.metric] || humanLabel(row.metric) })) }} /><SourceRef reference={diagnostic.generation_ref} onOpen={onSource} /><details className="research-details"><summary>Complete numerical source</summary><pre className="record">{JSON.stringify(diagnostic, null, 2)}</pre></details></section>)}</details>;
}

export default function EmpiricalWorkbench({ diagnostics = [], exhibits = [], questions = [], cases = [], protocols = [], summaries = [], implementations = [], progress = null, progressData = null, progressState, issues = null, furtherWork = null, awaitingDirection = false, loadErrors = [], branch, onSource, onRequest, onTheory, initialTab, reading = {}, onReadingChange }) {
  const { diags, figures, protocolList, caseList, items } = evaluationSources({ branch, diagnostics, exhibits, questions, cases, protocols });
  const summary = summaries.filter((item) => !item.branch || item.branch === branch).find((item) => item.decision_summary);
  const coverage = summary?.decision_summary?.coverage || [];
  const id = useId(); const panel = useRef(null);
  const [focusQuestion, setFocusQuestion] = useState(null); const [focusExhibit, setFocusExhibit] = useState(null);
  const normalizeTab = (value) => ({ results: "comparisons", design: "setup", review: "comparisons", next: "comparisons" }[value] || (EVIDENCE_TABS.some(([key]) => key === value) ? value : null));
  const firstTopic = () => EVIDENCE_TABS.find(([key]) => coverageForTab(coverage, key, items).length || items.some((question) => questionTopics(question, coverage).includes(key)))?.[0] || "setup";
  const [tab, setTab] = useState(() => normalizeTab(reading.tab || initialTab) || firstTopic());
  const tabChosen = useRef(Boolean(normalizeTab(reading.tab || initialTab)));
  const chooseTab = (value) => { tabChosen.current = true; setTab(value); };
  const readingChange = useRef(onReadingChange); readingChange.current = onReadingChange;
  useEffect(() => { readingChange.current?.({ tab }); }, [tab]);
  useEffect(() => { tabChosen.current = Boolean(normalizeTab(reading.tab || initialTab)); setTab(normalizeTab(reading.tab || initialTab) || firstTopic()); setFocusQuestion(null); setFocusExhibit(null); }, [branch]);
  // An intentionally selected empty topic remains selected through polling.
  useEffect(() => { if (!tabChosen.current && items.length) setTab(firstTopic()); }, [items.map((question) => `${question.id}:${questionTopics(question, coverage).join(",")}`).join("|")]);
  useEffect(() => { if (focusQuestion) { const target = [...(panel.current?.querySelectorAll("[data-question-id]") || [])].find((element) => element.dataset.questionId === focusQuestion); if (target?.tagName === "DETAILS") target.open = true; target?.querySelector("summary")?.focus(); target?.scrollIntoView({ block: "nearest" }); setFocusQuestion(null); } }, [tab, focusQuestion]);
  useEffect(() => { if (focusExhibit) { focusHeadlineExhibit(document.getElementById(focusExhibit)); setFocusExhibit(null); } }, [tab, focusExhibit]);
  const choose = (questionId) => { const question = items.find((item) => item.id === questionId); if (question) { chooseTab(questionHomeTab(question, coverage)); setFocusQuestion(questionId); } };
  const routed = routeEmpiricalExhibits(figures, items, coverage, summary);
  const exhibitAnchor = (entry) => `${id}-exhibit-${encodeURIComponent(entry.key)}`;
  const showExhibit = (exhibit) => { const entry = routed.find((item) => item.key === exhibitKey(exhibit)); if (entry) { if (entry.topic !== "other") chooseTab(entry.topic); setFocusExhibit(exhibitAnchor(entry)); } };
  const selected = items.filter((question) => questionTopics(question, coverage).includes(tab));
  const topicCoverage = coverageForTab(coverage, tab, items);
  const headlineIds = summary?.decision_summary?.headline_exhibit_ids || [];
  const missingHeadlines = headlineIds.filter((exhibitId) => !figures.some((exhibit) => exhibit.exhibit_id === exhibitId && exhibit.source_verified === true && !exhibit.source_error && exhibit.generation_ref?.run_id === summary?.generation_ref?.run_id && exhibit.generation_ref?.package_id === summary?.generation_ref?.package_id));
  const topicExhibits = routed.filter((entry) => entry.topic === tab).sort((a, b) => { const rank = (entry) => headlineIds.includes(entry.exhibit.exhibit_id) ? headlineIds.indexOf(entry.exhibit.exhibit_id) : headlineIds.length; return rank(a) - rank(b); });
  const publishedPlans = protocolList.filter((protocol) => protocol.work_items?.length || protocol.amendments?.length);
  const displayedPublishedPlan = progressData ? null : publishedPlans[0]; const otherPlans = publishedPlans.filter((plan) => plan !== displayedPublishedPlan);
  const implementationList = implementations.filter((record) => !record.branch || record.branch === branch);
  const anchor = `evaluation:${summary?.generation_ref?.generation_id || protocolList[0]?.generation_ref?.generation_id || branch}`;
  const currentPlan = progressData && <section className="empirical-current-plan"><h3>{progressState === "published" ? "Completed evaluation plan" : "Current evaluation plan"}</h3>{progressState !== "published" && <p className="note">This plan and its progress are provisional. Published findings above retain their original evidence.</p>}<EmpiricalPlan progress={progressData} settled={["published", "assessed", "failed", "cancelled"].includes(progressState)} compact /></section>;
  const empty = { setup: "No synthetic example or implementation-check answer is recorded.", comparisons: "No performance evidence is recorded. Unstudied performance remains unassessed.", computation: "No computation-cost evidence is recorded. Experiment-budget time does not establish per-fit method cost.", tuning: "No tuning answer is recorded. Tuning remains unassessed unless the saved protocol states it is not applicable.", sensitivity: "No robustness evidence is recorded. Behavior outside the studied conditions remains unassessed." };
  const renderExhibit = (entry) => <div key={entry.key} className="empirical-canonical-exhibit">{entry.association === "related" && <p className="note">Related result, linked by the recorded test or case. A more specific topic assignment is unavailable.</p>}<EmpiricalExhibit exhibit={entry.exhibit} anchorId={exhibitAnchor(entry)} readingAnchor={`${anchor}:exhibit:${entry.key}`} onSource={onSource} /></div>;
  const sources = { branch, onSource, artifacts: summary?.source_artifacts || [], records: [summary, ...protocolList, ...items.map((item) => item.result), ...items.map((item) => item.review), ...implementationList, ...implementationList.map((item) => item.theorist_review)], files: [...(summary?.run_sources || []), ...figures, ...implementationList.flatMap((record) => (record.files || []).map((file) => ({ ...file, branch: record.generation_ref?.branch || record.branch })))] };
  return <EmpiricalSourceProvider value={sources}><EmpiricalDecisionSummary record={summary} questions={items} dataSources={protocolList.flatMap((protocol) => [...(protocol.data_sources || []), ...(protocol.amendments || []).flatMap((item) => item.added_data_sources || [])])} onSelect={choose} onSource={onSource} awaitingDirection={awaitingDirection} hasProgress={Boolean(progressData)} progressState={progressState} />{progress}
    <section className="card empirical-code-card" data-card-role="research" data-reading-anchor={`${anchor}:implementation`}><h2>Implementation and Code</h2><div className="body"><ImplementationReading records={implementationList} protocols={protocolList} summary={summary} onSource={onSource} /></div></section>
    <section className="card empirical-workspace" data-card-role="research"><h2>Experiments and Results</h2><div className="body">
      <EmpiricalQuestionTabs id={id} selected={tab} onSelect={chooseTab} questions={items} coverage={coverage} />
      {scoped(loadErrors, branch, "P4").map((issue, index) => <p className="note warn" role="alert" key={index}>A source from this evaluation could not be verified or loaded: {issue.message}.</p>)}
      {missingHeadlines.length > 0 && <p className="note warn" role="alert">{missingHeadlines.length} referenced result {missingHeadlines.length === 1 ? "exhibit could" : "exhibits could"} not be verified or loaded. Inspect the retained sources before interpreting it.</p>}
      <div className="empirical-tab-panel" role="tabpanel" id={`${id}-panel`} aria-labelledby={`${id}-${tab}`} tabIndex={0} ref={panel}>
        {topicCoverage.map((entry, index) => <section className="empirical-topic-account" key={index}><h3>{humanLabel(entry.dimension)} <span className="note">{humanLabel(entry.status)}</span></h3>{[entry.summary, entry.limitation_markdown || entry.limitations_markdown, entry.implication_markdown].filter(Boolean).map((text, i) => <ResearchDocument key={i} text={text} />)}<SourceRef reference={summary?.generation_ref && { ...summary.generation_ref, entry_pointer: `/decision_summary/coverage/${coverage.indexOf(entry)}` }} onOpen={onSource} label="Coverage source" />
          {referencedCoverageExhibits(entry, figures).filter((exhibit) => routed.find((item) => item.key === exhibitKey(exhibit))?.topic !== tab).map((exhibit) => <ActionButton key={exhibitKey(exhibit)} action="details" variant="link" onClick={() => showExhibit(exhibit)}>View {exhibit.title || "recorded result"} in {EVIDENCE_TABS.find(([key]) => key === routed.find((item) => item.key === exhibitKey(exhibit))?.topic)?.[1] || "Other recorded results"}</ActionButton>)}
        </section>)}
        {protocolList.map((protocol, index) => <TopicProtocol key={protocol.protocol_id || index} protocol={protocol} tab={tab} onSource={onSource} />)}
        {topicExhibits.map(renderExhibit)}
        {selected.map((question) => {
          if (questionHomeTab(question, coverage) !== tab) return <p key={question.id} className="empirical-shared-question"><ActionButton action="details" variant="link" onClick={() => choose(question.id)}>Read the full answer: {question.title}</ActionButton></p>;
          const evidence = diagnosticsForQuestion(question, diags, caseList, protocolList);
          const protocol = protocolList.find((item) => item.generation_ref?.run_id && item.generation_ref.run_id === question.generation_ref?.run_id && item.generation_ref.package_id === question.generation_ref?.package_id);
          const questionCoverage = coverage.filter((entry) => entry.question_ids?.includes(question.id));
          return <details className="question-detail empirical-question-row" key={question.id} data-question-id={question.id} tabIndex={-1} data-reading-anchor={`${anchor}:question:${question.id}`}><summary><span className="empirical-question-title">{question.title}</span><span className="empirical-question-state"><Outcome state={questionOutcome(question)} /><span>{questionDataLabel(questionDataOrigins(question, caseList, protocolList))}</span>{questionCoverage.length ? questionCoverage.map((entry, index) => <span key={index}>{humanLabel(entry.dimension)}: {humanLabel(entry.status)}</span>) : <span>Coverage not recorded</span>}</span></summary><div className="empirical-question-answer"><QuestionTheoryContext question={question} onSource={onSource} /><EmpiricalQuestion question={question} cases={caseList} diagnostics={evidence.diagnostics} hasMapping={evidence.hasMapping} protocol={protocol} onSource={onSource} onRequest={onRequest} onTheory={onTheory} showEvidence={false} onExhibit={showExhibit} /><details className="research-details"><summary>Experiment design and exact sources</summary><EmpiricalQuestionSetup question={question} cases={caseList} onSource={onSource} onTheory={onTheory} /></details></div></details>;
        })}
        {!selected.length && !topicCoverage.length && !topicExhibits.length && <p className="note">{empty[tab]}</p>}
      </div>
      {coverage.filter((entry) => coverageTab(entry.dimension) === "actual_data").map((entry, index) => <section className="empirical-actual-data" key={index}><h3>Actual-data application <span className="note">{humanLabel(entry.status)}</span></h3>{[entry.summary, entry.limitation_markdown || entry.limitations_markdown, entry.implication_markdown].filter(Boolean).map((text, i) => <ResearchDocument key={i} text={text} />)}<SourceRef reference={summary?.generation_ref && { ...summary.generation_ref, entry_pointer: `/decision_summary/coverage/${coverage.indexOf(entry)}` }} onOpen={onSource} label="Actual-data coverage source" />{referencedCoverageExhibits(entry, figures).map((exhibit) => <ActionButton key={exhibitKey(exhibit)} action="details" variant="link" onClick={() => showExhibit(exhibit)}>View {exhibit.title || "actual-data result"} in {EVIDENCE_TABS.find(([key]) => key === routed.find((item) => item.key === exhibitKey(exhibit))?.topic)?.[1] || "Other recorded results"}</ActionButton>)}</section>)}
      {routed.some((entry) => entry.topic === "other") && <details className="research-details empirical-other-results" data-reading-anchor={`${anchor}:other-results`}><summary>Other recorded results</summary><p className="note">These results have no unambiguous topic assignment. Their saved sources and original scope are retained.</p>{routed.filter((entry) => entry.topic === "other").map(renderExhibit)}</details>}
      <CompleteNumbers diagnostics={diags} cases={caseList} onSource={onSource} />
      <EmpiricalFullInterpretation record={summary} onSource={onSource} />
      {currentPlan && progressState !== "published" && currentPlan}
      <details className="research-details empirical-study-background" data-reading-anchor={`${anchor}:study-design`}><summary>Detailed setup, checks and evaluation plan</summary>
        {!protocolList.length && !items.length && !progressData && <p className="note">{awaitingDirection ? "The evaluation is waiting for your direction. Its setup will appear when the analyst saves a plan." : "No experiments have been completed for this model yet. The study setup will appear here when it is recorded."}</p>}
        {currentPlan && progressState === "published" && <details className="research-details empirical-completed-plan" data-reading-anchor={`${anchor}:completed-plan`}><summary>Completed evaluation plan</summary>{currentPlan}</details>}
        {displayedPublishedPlan && <details className="research-details empirical-completed-plan" data-reading-anchor={`${anchor}:recorded-plan`}><summary>Recorded experiment plan</summary><section className="empirical-current-plan"><h3>Recorded experiment plan</h3><EmpiricalPlan progress={{ plan: displayedPublishedPlan }} planOnly compact /><SourceRef reference={displayedPublishedPlan.generation_ref} onOpen={onSource} /></section></details>}
        {otherPlans.length > 0 && <details className="research-details empirical-recorded-plans"><summary>Other recorded plans and sources ({otherPlans.length})</summary>{otherPlans.map((plan, index) => <section key={plan.protocol_id || index}><h3>{plan.title || "Recorded experiment plan"}</h3><EmpiricalPlan progress={{ plan }} planOnly /><SourceRef reference={plan.generation_ref} onOpen={onSource} /></section>)}</details>}
        {protocolList.map((protocol, index) => <ProtocolSetup key={protocol.protocol_id || index} protocol={protocol} onSource={onSource} />)}
        {coverage.some((entry) => !coverageTab(entry.dimension)) && <section className="empirical-coverage"><h3>Additional recorded scope</h3>{coverage.filter((entry) => !coverageTab(entry.dimension)).map((entry, index) => <section key={index}><h4>{humanLabel(entry.dimension)} · {humanLabel(entry.status)}</h4>{[entry.summary, entry.limitation_markdown || entry.limitations_markdown, entry.implication_markdown].filter(Boolean).map((text, i) => <ResearchDocument key={i} text={text} />)}</section>)}</section>}
      </details>
    </div></section>{issues}{furtherWork}</EmpiricalSourceProvider>;
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
