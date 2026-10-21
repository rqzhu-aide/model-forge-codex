import { hasExactRef, OUTCOMES } from "./research.js";

const ids = (value) => Array.isArray(value) ? value.filter((id) => typeof id === "string" && id) : [];
const unique = (values) => [...new Set(values)];
const testIds = (value = {}) => unique([...ids(value.test_ids), ...(value.test_id ? [value.test_id] : [])]);
const caseIds = (value = {}) => unique([...ids(value.case_ids), ...(value.case_id ? [value.case_id] : [])]);
const intersects = (a, b) => a.some((id) => b.includes(id));

export const evidenceTab = (question) => ({ implementation: "setup", implementation_fidelity: "setup", performance: "comparisons", accuracy: "comparisons", uncertainty: "comparisons", cost: "computation", computation: "computation", tuning: "tuning", sensitivity: "sensitivity", robustness: "sensitivity", assumptions: "sensitivity", failures: "sensitivity" }[question?.result?.category || question?.category] || "setup");
// These are exact legacy labels, not keyword guesses about scientific prose.
export function coverageTab(dimension) {
  return ({ setup: "setup", synthetic_example: "setup", "synthetic example": "setup", implementation: "setup", implementation_fidelity: "setup", "implementation and portability": "setup", fidelity: "setup", performance: "comparisons", accuracy: "comparisons", uncertainty: "comparisons", "accuracy+uncertainty": "comparisons", "accuracy + uncertainty": "comparisons", computation: "computation", cost: "computation", tuning: "tuning", robustness: "sensitivity", sensitivity: "sensitivity", actual_data: "actual_data", "actual-data application": "actual_data", "actual data application": "actual_data" })[String(dimension || "").trim().toLowerCase()] || null;
}
const questionId = (question) => question.id || question.question_id || question.test_id;
export function coverageForTab(coverage = [], tab, questions = []) {
  return coverage.filter((entry) => {
    const topic = coverageTab(entry.dimension);
    return topic ? topic === tab : ids(entry.question_ids).some((id) => questions.some((question) => questionId(question) === id && evidenceTab(question) === tab));
  });
}
export function questionTopics(question, coverage = []) {
  const topics = coverage.filter((entry) => ids(entry.question_ids).includes(questionId(question))).map((entry) => coverageTab(entry.dimension)).filter((topic) => topic && topic !== "actual_data");
  return topics.length ? unique(topics) : [evidenceTab(question)];
}
export function questionHomeTab(question, coverage = []) {
  const topics = questionTopics(question, coverage);
  return topics.includes(evidenceTab(question)) ? evidenceTab(question) : topics[0];
}
export const exhibitKey = (exhibit) => JSON.stringify([exhibit.generation_ref?.run_id, exhibit.generation_ref?.package_id, exhibit.exhibit_id]);
function mentionsExhibit(text, id) {
  if (typeof text !== "string" || !id) return false;
  const escaped = id.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`(^|[^A-Za-z0-9_.-])${escaped}(?=$|[^A-Za-z0-9_.-]|[.]?(?:\\s|$))`).test(text);
}
export const referencedCoverageExhibits = (entry, exhibits = []) => exhibits.filter((exhibit) => ids(entry.exhibit_ids).includes(exhibit.exhibit_id) || mentionsExhibit(entry.summary, exhibit.exhibit_id));
// Give each saved exhibit one location. Author-declared topic links outrank a
// broad test/case relationship. Figures inherit only explicit data links.
export function routeEmpiricalExhibits(exhibits = [], questions = [], coverage = [], summary) {
  const canonical = [...new Map(exhibits.map((exhibit) => [exhibitKey(exhibit), exhibit])).values()];
  const entries = coverage.filter((entry) => coverageTab(entry.dimension) && coverageTab(entry.dimension) !== "actual_data");
  const routed = canonical.map((exhibit) => {
    const scopedEntries = !summary || sameEvaluation(summary, exhibit) ? entries : [];
    const direct = scopedEntries.find((entry) => ids(entry.exhibit_ids).includes(exhibit.exhibit_id));
    const mentioned = scopedEntries.find((entry) => mentionsExhibit(entry.summary, exhibit.exhibit_id));
    const exactQuestions = questions.filter((question) => sameEvaluation(question, exhibit) && [...ids(question.result?.exhibit_ids), ...ids(question.exhibit_ids)].includes(exhibit.exhibit_id));
    const related = questions.filter((question) => exhibitsForQuestion(question, [exhibit]).length);
    const exactTopics = unique(exactQuestions.map((question) => questionHomeTab(question, coverage)));
    const relatedTopics = unique(related.flatMap((question) => questionTopics(question, coverage)));
    // A result explicitly cited by several questions lives with the first
    // authored question. The other questions navigate to that one saved result.
    const topic = direct || mentioned ? coverageTab((direct || mentioned).dimension) : exactTopics.length ? exactTopics[0] : relatedTopics.length === 1 ? relatedTopics[0] : "other";
    return { exhibit, key: exhibitKey(exhibit), topic, association: direct ? "coverage" : mentioned ? "coverage_reference" : exactQuestions.length ? "question" : related.length ? "related" : "unassigned" };
  });
  for (const entry of routed) {
    if (["coverage", "coverage_reference"].includes(entry.association) || !ids(entry.exhibit.data_exhibit_ids).length) continue;
    const data = routed.filter((candidate) => sameEvaluation(entry.exhibit, candidate.exhibit) && ids(entry.exhibit.data_exhibit_ids).includes(candidate.exhibit.exhibit_id));
    const topics = unique(data.map((candidate) => candidate.topic).filter((topic) => topic !== "other"));
    if (topics.length === 1) { entry.topic = topics[0]; entry.association = "figure_data"; }
  }
  return routed;
}

// Explicit source metadata may rule out a match. A shared case name alone must
// never pull a result from another publication into the selected question.
function sameEvaluation(question, source) {
  const questionRef = question.generation_ref; const sourceRef = source.generation_ref;
  if (questionRef && sourceRef) {
    for (const key of ["branch", "phase", "package_id", "run_id"]) {
      if (questionRef[key] && sourceRef[key] && questionRef[key] !== sourceRef[key]) return false;
    }
    if (questionRef.family === "protocol" && sourceRef.family === "protocol") {
      for (const key of ["generation_id", "sha256"]) {
        if (questionRef[key] && sourceRef[key] && questionRef[key] !== sourceRef[key]) return false;
      }
    }
  }
  if (questionRef?.family === "protocol" && questionRef.sha256 && source.provenance?.protocol_sha256 && questionRef.sha256 !== source.provenance.protocol_sha256) return false;
  return true;
}

export const DATA_VIEWS = [["all", "All data"], ["synthetic", "Synthetic"], ["researcher_observed", "Your data"], ["external_data", "Benchmark"], ["computational_check", "Checks"], ["other", "Other recorded evidence"]];
const sourceOrigin = (value) => DATA_VIEWS.some(([key]) => key === value) && value !== "all" ? value : "other";

// A filter selects a complete authored answer. It never removes table rows or
// changes a conclusion that also draws on a second data source.
export function questionDataOrigins(question = {}, cases = [], protocols = []) {
  const matchingProtocols = protocols.filter((protocol) => sameEvaluation(question, protocol));
  const sources = matchingProtocols.flatMap((protocol) => [...(protocol.data_sources || []), ...(protocol.amendments || []).flatMap((item) => item.added_data_sources || [])]);
  const declaredCases = matchingProtocols.flatMap((protocol) => [...(protocol.cases || []), ...(protocol.amendments || []).flatMap((item) => item.added_cases || [])]);
  const scopedCases = [...new Map([...cases.filter((item) => sameEvaluation(question, item)), ...declaredCases].map((item) => [item.case_id || item.id, item])).values()];
  const selectedCases = scopedCases.filter((item) => caseIds(question).includes(item.case_id || item.id) || intersects(testIds(question), testIds(item)));
  const sourceIds = unique([...ids(question.data_source_ids), ...selectedCases.flatMap((item) => ids(item.data_source_ids))]);
  const origins = sourceIds.map((id) => sourceOrigin(sources.find((item) => item.data_source_id === id)?.origin));
  if (!origins.length || selectedCases.some((item) => !ids(item.data_source_ids).length)) origins.push("other");
  return unique(origins);
}

export function questionDataLabel(origins = []) {
  return origins.length > 1 ? "Mixed" : DATA_VIEWS.find(([key]) => key === origins[0])?.[1] || "Other recorded evidence";
}

export function availableDataViews(questions = [], cases = [], protocols = []) {
  const available = new Set([...questions.flatMap((question) => questionDataOrigins(question, cases, protocols)),
    ...protocols.flatMap((protocol) => [...(protocol.data_sources || []), ...(protocol.amendments || []).flatMap((item) => item.added_data_sources || [])]).map((source) => sourceOrigin(source.origin))]);
  return DATA_VIEWS.filter(([key]) => key === "all" || available.has(key));
}

export function questionOutcome(question = {}) {
  return question.result?.outcome || (OUTCOMES[question.status] ? question.status : "not_assessed");
}

export function exhibitsForQuestion(question, exhibits = []) {
  const tests = testIds(question); const cases = caseIds(question);
  return exhibits.filter((exhibit) => {
    if (!sameEvaluation(question, exhibit)) return false;
    if (ids(question.result?.exhibit_ids).includes(exhibit.exhibit_id)) return true;
    const exhibitTests = testIds(exhibit);
    // Test labels are more specific than a shared case or an authored figure list.
    if (exhibitTests.length && (!tests.length || !intersects(exhibitTests, tests))) return false;
    if (exhibit.question_id && question.question_id && exhibit.question_id !== question.question_id) return false;
    return Boolean((question.question_id && exhibit.question_id === question.question_id)
      || intersects(tests, exhibitTests)
      || [...ids(question.exhibit_ids), ...ids(question.result?.exhibit_ids)].includes(exhibit.exhibit_id)
      || intersects(cases, caseIds(exhibit)));
  });
}

// Build (case, metric) pairs, rather than selecting all numbers from a case that
// may serve several different scientific questions. Threshold links supply the
// test-to-metric association when claim_tests has no explicit metric_ids.
export function questionDiagnosticScope(question = {}, cases = [], protocols = []) {
  const tests = testIds(question); const declaredCases = caseIds(question);
  const thresholds = protocols.filter((protocol) => sameEvaluation(question, protocol)).flatMap((protocol) => {
    const selectedTests = (protocol.claim_tests || []).filter((test) => tests.includes(test.test_id));
    const thresholdIds = unique([...ids(question.decision_threshold_ids), ...selectedTests.flatMap((test) => ids(test.decision_threshold_ids))]);
    return (protocol.decision_thresholds || []).filter((threshold) => thresholdIds.includes(threshold.threshold_id));
  });
  const metrics = unique([...ids(question.metric_ids), ...thresholds.map((threshold) => threshold.metric_id).filter(Boolean)]);
  const selectedCases = cases.filter((item) => sameEvaluation(question, item)
    && (declaredCases.length ? declaredCases.includes(item.case_id || item.id) : intersects(tests, testIds(item)))
    && (!testIds(item).length || !tests.length || intersects(tests, testIds(item))));
  const pairs = [];
  for (const item of selectedCases) {
    const itemTests = testIds(item); const itemMetrics = ids(item.metric_ids);
    const unambiguousCase = tests.length && itemTests.length && itemTests.every((id) => tests.includes(id));
    const mappedMetrics = metrics.length ? metrics.filter((id) => !itemMetrics.length || itemMetrics.includes(id)) : unambiguousCase ? itemMetrics : [];
    for (const metric of mappedMetrics) pairs.push([item.case_id || item.id, metric]);
  }
  // Exact authored pairs remain usable when older sources omit case descriptions.
  if (!selectedCases.length && declaredCases.length && metrics.length) {
    for (const caseId of declaredCases) for (const metric of metrics) pairs.push([caseId, metric]);
  }
  return { pairs, case_ids: unique(selectedCases.map((item) => item.case_id || item.id)), hasMapping: pairs.length > 0 };
}

export function diagnosticsForQuestion(question, diagnostics = [], cases = [], protocols = []) {
  const scope = questionDiagnosticScope(question, cases, protocols);
  const pairKeys = new Set(scope.pairs.map(([caseId, metric]) => JSON.stringify([caseId, metric])));
  const selectedCases = new Set(scope.pairs.map(([caseId]) => caseId));
  const matches = (row) => pairKeys.has(JSON.stringify([row.case_id, row.metric_id || row.metric]));
  const selected = diagnostics.filter((item) => sameEvaluation(question, item)).map((item) => ({
    ...item,
    headline_numbers: (item.headline_numbers || []).filter(matches),
    stability: (item.stability || []).filter(matches),
    // Regime aggregates and total runtime cover the evaluation. They cannot be
    // presented as question-specific totals without explicit row associations.
    solver_health: [],
    runtime: { per_case: (item.runtime?.per_case || []).filter((row) => selectedCases.has(row.case_id)) },
  })).filter((item) => item.headline_numbers.length || item.stability.length || item.runtime.per_case.length);
  return { ...scope, diagnostics: selected, hasNumbers: selected.length > 0 };
}

export function hasEmpiricalFollowup(question) {
  const target = question?.followup_target;
  return Boolean(hasExactRef(target) && target.phase === "P4" && target.family === "protocol"
    && target.kind === "empirical_question" && Object.hasOwn(target, "package_id") && target.run_id
    && target.question_id && target.question_id === question.question_id && target.object_id === target.question_id
    && sameEvaluation(question, { generation_ref: target })
    && ids(target.test_ids).length && Array.isArray(target.case_ids) && Array.isArray(target.statement_ids));
}

export function theoryClaimSource(question, statementId) {
  const context = question?.theory_context;
  return hasExactRef(context?.tested_ref) && ids(question?.statement_ids).includes(statementId)
    ? [statementId, context.tested_ref, context] : null;
}
