// Only the authored choice contract creates selectable alternatives. Historical
// prose remains readable without assigning it an invented option identity.
export function decisionOptions(item) {
  if (item.response_kind !== "choice" || !Array.isArray(item.options) || !item.options.length) return [];
  const ids = new Set();
  for (const option of item.options) {
    if (!option || typeof option !== "object" || !["id", "label", "consequence"].every(key => typeof option[key] === "string" && option[key].trim()) || ids.has(option.id)) return [];
    ids.add(option.id);
  }
  return item.options;
}

export function decisionDraft(item, answer, cached) {
  const options = decisionOptions(item);
  if (cached) return { note: cached.text ?? cached.note ?? "", origin: cached.origin || "researcher_reported", choice: cached.choice || (cached.selection?.option_id ? `option:${cached.selection.option_id}` : "") };
  const selected = answer?.selection;
  return {
    note: selected ? selected.note || "" : answer?.note || "",
    origin: answer?.origin || "researcher_reported",
    choice: selected && options.some(option => option.id === selected.option_id) ? `option:${selected.option_id}` : answer ? answer.origin === "unknown" ? "unknown" : "custom" : "",
  };
}

export function decisionSubmission(item, { note = "", origin = "researcher_reported", choice = "" }) {
  const options = decisionOptions(item);
  const option = options.find(entry => `option:${entry.id}` === choice);
  if (option) return { note: note.trim(), origin: "researcher_reported", selection: { option_id: option.id, ...(note.trim() ? { note: note.trim() } : {}) } };
  if (options.length && !["custom", "unknown"].includes(choice)) return null;
  const unknown = options.length ? choice === "unknown" : origin === "unknown";
  const text = note.trim() || (unknown ? options.length ? "I am unsure. Keep this choice unresolved." : "This information remains unknown." : "");
  return text ? { note: text, origin: unknown ? "unknown" : origin } : null;
}

export const decisionPriorityLabel = item => ({ interpretation: "Interpretation", inference: "Inference", data: "Data applicability", resources: "Resources" })[item.decision_priority];
const priorityOrder = { interpretation: 0, inference: 1, data: 2, resources: 3 };
const orderOf = item => Number.isInteger(item.authored_order) ? item.authored_order : Number((item.entry_pointer || item.generation_ref?.entry_pointer || item.explanation_target?.entry_pointer || "").match(/\/(\d+)$/)?.[1] ?? NaN);
export function compareDecisionPriority(a, b) {
  const first = priorityOrder[a.decision_priority], second = priorityOrder[b.decision_priority];
  if (first == null && second == null) return 0;
  if (first == null) return 1;
  if (second == null) return -1;
  const priority = first - second;
  if (priority) return priority;
  const publication = String(b.published_at || "").localeCompare(String(a.published_at || ""));
  if (publication) return publication;
  const aOrder = orderOf(a), bOrder = orderOf(b);
  return Number.isFinite(aOrder) && Number.isFinite(bOrder) ? aOrder - bOrder : 0;
}

export function legacyOptionText(options) {
  if (typeof options === "string") return options;
  if (!Array.isArray(options)) return "";
  return options.map(option => typeof option === "string" ? option : option && typeof option.label === "string" ? [option.label, option.consequence].filter(Boolean).join(". ") : "").filter(Boolean).join("\n\n");
}

export function decisionSupportSections(item, title = item.question || item.title) {
  const authoredBrief = ["choice", "study_fact"].includes(item.response_kind);
  const context = item.context_markdown || item.summary_markdown;
  const consequence = item.likely_consequence || item.consequence_markdown || item.why_it_matters || item.why_it_matters_markdown;
  const shown = new Set([title, consequence, item.recommendation, ...(authoredBrief ? [context] : [])].filter(Boolean));
  return [
    ...(!authoredBrief ? [[context, "Context", "context"]] : []),
    [item.summary_markdown, "Earlier context", "summary"],
    [item.expected_consequence || item.answer_consequences_markdown, "What your answer changes", "answer-consequences"],
    [item.checkability || item.checkability_markdown, "How this could be checked", "checkability"],
    [item.information_limits || item.information_limits_markdown, "What remains unknown", "limits"],
    [item.why_it_matters || item.why_it_matters_markdown, "Supporting explanation", "why"],
    [item.disposition_reason, "The lead's response", "disposition"],
  ].flatMap(([text, heading, section]) => {
    if (!text || shown.has(text)) return [];
    shown.add(text); return [{ text, heading, section }];
  });
}
