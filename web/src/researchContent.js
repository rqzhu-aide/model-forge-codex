import { isBareMathDefinition } from "./researchMath.js";

// Only explicitly authored research fields belong in the readable view.
// Unknown fields and execution metadata remain in the complete source record.
export const narrativeFields = [
  ["body_md", null], ["body_markdown", null], ["markdown", null], ["manuscript_markdown", null], ["report_markdown", null],
  ["content_markdown", null], ["summary_markdown", null], ["evaluation_markdown", null],
  ["abstract", "Abstract"], ["summary", null], ["text", null], ["body", null], ["content", null],
  ["scientific_question", "Research question"], ["current_conclusion", "Conclusion"],
  ["conclusion", "Conclusion"], ["overall_assessment", "Overall assessment"],
  ["assessment", "Assessment"], ["rationale", "Rationale"], ["theory_scope", "Scope"],
  ["scope", "Scope"], ["scope_justification", "Scope"], ["reviewed_scope", "What was reviewed"],
  ["innovation", "Contribution"], ["definition", "Definition"], ["evaluation", "Assessment"],
  ["context_markdown", "Mathematical context"], ["question", "Question"], ["statement", "Statement"], ["issue", "Finding"],
  ["likely_consequence", "Why it matters"],
  ["scientific_consequence", "Why it matters"], ["consequence", "Why it matters"],
  ["requested_resolution", "Requested change"], ["smallest_decisive_result", "What would resolve this"],
  ["change_summary", "What changed"], ["location", "Location"], ["proof", "Proof"],
  ["proof_sketch", "Proof idea"], ["purpose", "Purpose"], ["operation", "Operation"],
  ["domain", "Domain"], ["mathematical_role", "Role in the argument"],
  ["key_contribution", "Contribution"], ["relevance_to_question", "Relevance to the research question"],
  ["status_reason", "Reason for status"], ["disposition_reason", "Reason for the decision"],
  ["policy_class_reconciliation", "Policy class distinction"],
  ["status_audit", "Source status checks"], ["novelty_statement", "Limits on novelty claims"],
  ["statement_markdown", "Research setting"], ["instructions_markdown", "Instructions"],
  ["formulation_markdown", "Mathematical formulation"], ["explanation_markdown", "Contribution and intuition"],
  ["assumptions_markdown", "Assumptions and conditions"], ["changes_markdown", "Mathematical changes"],
  ["consequences_markdown", "Consequences"], ["computational_requirements_markdown", "Information and computational requirements"],
  ["scope_markdown", "Scope of scientific review"], ["reason_markdown", "Reason for the correction"],
  ["reading_extent", "Reading basis"],
  ["relevance_markdown", "Relevance"], ["limitations_markdown", "Limitations"],
  ["specification_markdown", "Supplied model"], ["data_requirements_markdown", "Data requirements"],
  ["proposed_evaluation_markdown", "Proposed evaluation"], ["assessment_markdown", "Assessment"],
  ["reasoning_markdown", "Reasoning"], ["consequence_markdown", "Consequence"],
  ["overview_markdown", "Overview"], ["comparison_markdown", "Model comparison"], ["description_markdown", null],
  ["search_scope_markdown", "Search scope"], ["locator", "Location in source"],
  ["admissible_values", "Admissible values"], ["selection_rule", "Selection rule"],
];

export const collectionFields = [
  ["scientific_outcome", "Recorded assessment"], ["strengths", "Strengths"],
  ["findings", "Findings"], ["prioritized_issues", "Prioritized findings"], ["issues", "Findings"],
  ["evidence_basis", "Evidence"], ["assumptions", "Assumptions"], ["statements", "Statements"],
  ["limitations", "Limitations"], ["access_limits", "Search limitations"],
  ["missing_materials", "Missing material"], ["exclusions", "Excluded from this search"],
  ["gaps", "Research gaps"], ["unresolved_gaps", "Open gaps"], ["unresolved_issues", "Open issues"],
  ["open_questions", "Open questions"], ["open_items", "Open questions"],
  ["material_disagreement", "Unresolved differences"], ["suggested_actions", "Possible next steps"],
  ["available_actions", "Possible next steps"], ["required_checks", "Checks still needed"],
  ["evidence_that_would_change_assessment", "What would change the assessment"],
  ["completed_work", "Work completed"], ["material_changes", "What changed"],
  ["sections", "Manuscript"], ["claim_tests", "Empirical questions"],
  ["novelty_search_boundary", "Novelty search boundary"], ["sources_consulted", "Sources searched"],
  ["query_concepts", "Search concepts"], ["revision_account", "Revision account"],
  ["mathematical_definition", "Mathematical definition"], ["canonical_definition", null],
  ["target_or_estimand", "Target"], ["input_information", "Available information"],
  ["feature_definition", "Predictor construction"], ["objective_or_estimating_equation", "Objective or estimating equation"],
  ["derivatives", "Gradient and curvature"],
  ["algorithm_or_update_rule", "Algorithm"], ["constraints_and_normalization", "Constraints"],
  ["tuning_definition", "Tuning parameters"],
  ["calculation_defining_assumptions", "Assumptions required for the calculation"],
  ["computational_consequences", "Computational implications"],
  ["work_summaries", "Research accounts"], ["search_boundaries", "Search boundaries"],
  ["covered_questions", "Questions covered"], ["coverage_by_question", "Coverage by question"],
  ["coverage", "Search coverage"],
  ["covered_areas", "Areas covered"], ["focused_exclusions", "Excluded from this focused search"],
  ["open_gaps", "Open gaps"], ["synthesis", null],
  ["formulation_semantics", "What the constraint means"], ["manuscript_audit", "Manuscript formulation audit"],
  ["algorithm_options", "Algorithm options"], ["recommended_preliminary_design", "Proposed preliminary experiment"],
  ["coverage_and_provenance", "Coverage and limitations"],
  ["research_setting", "Research setting"], ["phase2_preparation", "Phase 2 preparation"],
  ["landscape", "Literature landscape"], ["frameworks", "Frameworks"], ["variants", "Variants"],
  ["relationships", "Relationships"], ["algorithm_families", "Existing algorithm families"],
  ["scientific_review", "Scientific review"], ["entry_corrections", "Lead corrections"],
  ["changes", "Corrected content"], ["evidence_locations", "Evidence locations"],
];

// These P1 records contain authored research inside named objects. Project only
// their known research fields; bookkeeping alongside them stays in the source.
const researchObjectFields = {
  formulation_semantics: [
    ["resource_cost_overrun", "Expected budget overrun"], ["units_and_discount", "Units and discounting"],
    ["expected_cost_comparison", "Comparison with expected cost"], ["chance_comparison", "Comparison with violation probability"],
    ["cvar_comparison", "Comparison with CVaR"], ["pathwise_comparison", "When the budget holds almost surely"],
    ["feasibility", "Feasibility"], ["reward_shortfall", "Reward shortfall in the manuscript"],
  ],
  manuscript_audit: [
    ["status", "Inspection limits"], ["reward_identity", "Reward identity"], ["cost_identity", "Cost identity"],
    ["residual_coordinate", "Residual coordinate"], ["convexity_boundary", "Limits of the convexity claim"],
  ],
  recommended_preliminary_design: [
    ["choice", "Starting experiment"], ["reason", "Why this experiment"], ["environment", "Environment"],
    ["calibration_gate", "Design checks"], ["offline_coverage", "Offline coverage experiment"],
    ["comparators", "Comparators"], ["metrics", "Measures"], ["separation", "Training and evaluation"], ["status", "Execution status"],
  ],
  coverage_and_provenance: [
    ["focused_exclusions", "Excluded from this focused search"], ["status_check", "Source status checks"],
    ["novelty_limit", "Limits on novelty claims"],
  ],
};

function labeledResearchFields(value, fields) {
  return fields.flatMap(([key, title]) => {
    const text = value[key];
    return (typeof text === "string" && text.trim()) || (Array.isArray(text) && text.length) ? [{ title, text }] : [];
  });
}

// Older named mathematical objects sometimes stored a bare formula in
// `definition`. Recover only standalone symbolic relations in these known
// fields. A sentence, mixed prose, code, or already delimited math stays as
// authored; this never changes the canonical source record.
function namedMathematicalObjectForDisplay(value) {
  if (Array.isArray(value)) return value.map(namedMathematicalObjectForDisplay);
  if (!value || typeof value !== "object" || typeof value.definition !== "string") return value;
  if (!isBareMathDefinition(value.definition)) return value;
  return { ...value, definition: { latex: value.definition } };
}

function readableResearchBody(key, body) {
  // Typed scope objects describe applicability, not an authored research account.
  if (key === "scope" && ["project", "model"].includes(body?.kind)) return null;
  if (["target_or_estimand", "input_information", "feature_definition", "objective_or_estimating_equation", "derivatives", "constraints_and_normalization"].includes(key)) return namedMathematicalObjectForDisplay(body);
  if (researchObjectFields[key] && body && typeof body === "object" && !Array.isArray(body)) {
    return labeledResearchFields(body, researchObjectFields[key]);
  }
  if (!Array.isArray(body)) return body;
  if (key === "algorithm_or_update_rule") return [...body].sort((a, b) => (a.order || 0) - (b.order || 0)).map((step) => ({ ...step, title: step.title || (step.order ? `Step ${step.order}` : undefined) }));
  if (key === "covered_areas") return body.flatMap((item) => typeof item === "string" ? [item] : typeof item?.area === "string" ? [item.area] : []);
  if (key === "focused_exclusions") return body.map((item) => typeof item === "string" ? item
    : { title: item?.work, rationale: item?.reason, status_reason: item?.status });
  if (key === "algorithm_options") return body.map((item) => typeof item === "string" ? item : {
    title: item?.family,
    body: labeledResearchFields(item || {}, [["data_regime", "Data available"], ["learns", "What is learned"],
      ["policy_class", "Policy class"], ["constraint_handling", "How the constraint is handled"], ["failure_boundary", "Limitations"]]),
  });
  return body;
}

export function readableSections(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return [];
  const seen = new Set();
  return [...narrativeFields, ...collectionFields].flatMap(([key, label]) => {
    const body = readableResearchBody(key, value[key]);
    if (body == null || body === "" || (Array.isArray(body) && !body.length)) return [];
    if (typeof body !== "string" && typeof body !== "object") return [];
    const signature = JSON.stringify(body);
    if (seen.has(signature)) return [];
    seen.add(signature);
    return [{ key, label, body }];
  });
}

export function citationLinks(source) {
  return (Array.isArray(source.identifiers) ? source.identifiers : []).flatMap(({ kind, value }) => {
    if (typeof value !== "string" || !value.trim()) return [];
    if (kind === "doi") {
      const doi = value.replace(/^https?:\/\/(dx\.)?doi\.org\//i, "").replace(/^doi:\s*/i, "");
      return /^10\.\d{4,9}\//.test(doi) ? [{ label: "DOI", href: `https://doi.org/${encodeURI(doi).replaceAll("#", "%23").replaceAll("?", "%3F")}` }] : [];
    }
    if (kind === "arxiv") {
      const id = value.replace(/^https?:\/\/arxiv\.org\/abs\//i, "").replace(/^arxiv:\s*/i, "");
      return /^[\w.-]+(?:\/[\w.-]+)?$/.test(id) ? [{ label: "arXiv", href: `https://arxiv.org/abs/${id}` }] : [];
    }
    return /^https?:\/\//i.test(value) ? [{ label: "Read paper", href: value }] : [];
  }).filter((item, index, items) => items.findIndex((other) => other.href === item.href) === index);
}

export function filterLiterature(sources, query) {
  const terms = query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  return sources.filter((source) => {
    const cards = source.cards || (source.card ? [source.card] : []);
    const text = [source.title, ...(source.authors || []), source.year, source.venue,
      ...(source.identifiers || []).map((id) => id.value),
      ...cards.flatMap((card) => [card.title, card.innovation, card.definition, card.evaluation,
        card.formulation_markdown, card.explanation_markdown, card.relevance_markdown, card.limitations_markdown, ...(card.topics || [])])].join(" ").toLocaleLowerCase();
    return terms.every((term) => text.includes(term));
  });
}

export function sourceEntry(document, pointer, cardId) {
  if (!pointer && cardId) return (Array.isArray(document) ? document : document?.cards || []).find((card) => card.card_id === cardId) || null;
  if (!pointer) return document;
  if (!/^\//.test(pointer)) return null;
  return pointer.slice(1).split("/").reduce((value, part) => {
    const key = part.replaceAll("~1", "/").replaceAll("~0", "~");
    return value && typeof value === "object" && Object.hasOwn(value, key) ? value[key] : null;
  }, document);
}

export const retainedReviewNote = "These retained findings keep their latest recorded status and may concern an earlier manuscript version. A new manuscript draft does not by itself resolve or reassess them.";

export function selectResearchDocuments(documents) {
  const ledgers = documents.filter((doc) => doc.kind === "review_issue_ledger");
  return documents.filter((doc) => doc.kind !== "review_issues" || !ledgers.some((ledger) => ledger.branch === doc.branch && ledger.phase === doc.phase))
    .sort((a, b) => Number(!["manuscript", "manuscript_candidate"].includes(a.kind)) - Number(!["manuscript", "manuscript_candidate"].includes(b.kind)));
}

export const researchDocumentTitle = (document) => document.kind === "review_issue_ledger" ? "Review findings and resolution status" : document.title || document.structured?.title;

// Present the whole declared Analyst account in its authored order. These
// labels never join its informal question keys to structured question IDs.
function analystAccountContent(account) {
  const sections = (value, fields) => labeledResearchFields(value, fields).map(({ title, text }) => ({ title, body: text }));
  const questions = Array.isArray(account.questions) ? account.questions : account.question_results;
  return { title: account.title, body: [
    ...sections(account, [["summary_markdown", "Summary"], ["conclusion", "Conclusion"], ["scope", "Scope"], ["conditions", "Conditions"], ["design", "Study design"]]),
    ...(Array.isArray(questions) ? [{ title: "Empirical questions", body: questions.map((question) => typeof question === "object" && question ? {
      title: question.title, state: question.outcome,
      body: sections(question, [["answer_markdown", "Finding"], ["relevance_markdown", "Relevance"],
        ["design_markdown", "Study design"], ["conditions_markdown", "Conditions"], ["comparison_markdown", "Model comparison"],
        ["reliability_markdown", "Reliability"], ["uncertainty_markdown", "Uncertainty"],
        ["limitations_markdown", "Limitations"], ["decision_implication_markdown", "Implication for the model"],
        ["next_steps_markdown", "Next steps"]]),
    } : question) }] : []),
    ...(account.implementation_summary && typeof account.implementation_summary === "object" ? [{ title: "Implementation summary", body: sections(account.implementation_summary,
      [["rule", "Implemented calculation"], ["correspondence", "Correspondence to the model"], ["environment", "Environment"],
        ["verification", "Verification"], ["limitations", "Limitations"], ["configuration", "Configuration"],
        ["choices", "Implementation choices"], ["departures", "Departures from the model"]]) }] : []),
  ] };
}

export function researchDocumentContent(document) {
  if (document.kind === "analyst_synthesis" && document.primary_source_verified && document.primary_artifact_kind === "json" && document.primary_content) {
    return analystAccountContent(document.primary_content);
  }
  if (document.kind === "analyst_audit" && document.structured) {
    return { ...document.structured, body_md: document.body_md || document.body || document.structured.body_md };
  }
  const review = ["review_issue_ledger", "review_issues", "outside_review", "theory_audit", "empirical_audit"].includes(document.kind);
  if (review && document.structured) return document.structured;
  return document.body_md || document.body || document.text || document.summary || document.structured;
}
