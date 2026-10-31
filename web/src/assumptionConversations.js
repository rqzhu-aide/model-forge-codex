import { hasExactRef, sameRef, TERMINAL } from "./research.js";
import { GOAL_POINTER, goalSourceKey } from "./phaseOneReader.js";

export const conversationPurpose = (target, conversation) => conversation?.assessment_purpose || target?.assessmentPurpose
  || (["report_section", "notation_entry"].includes(target?.kind) ? "model_dialogue" : target?.kind === "project_context" ? "project_context" : target?.kind === "assumption" ? "explanation" : "issue_explanation");
export const defaultConversationQuestion = target => conversationPurpose(target) === "issue_suggestions"
  ? "Help me answer this question using its context and my note. If it asks for a choice, explain the alternatives, their consequences and what information would change your advice. If it asks for a study fact, explain what information would answer it and what can remain unknown. Do not infer my preference or a missing study fact." : "";

export function responseDraftPayload(draft) {
  return draft ? { kind: draft.kind, ...(draft.kind === "choice" ? { option_id: draft.option_id } : {}), note: draft.note || "" } : null;
}

export function responseDraftText(draft) {
  if (!draft) return "";
  const parts = draft.kind === "choice" ? [draft.label || "Selected option", draft.consequence]
    : draft.kind === "unknown" ? ["Not sure yet"] : [];
  return [...parts, draft.note].filter(Boolean).join("\n\n");
}

export function isConversationTarget(target) {
  if (target?.kind === "researcher_pause") return Boolean(target.branch && target.phase && target.run_id && target.request_id && target.revision != null && target.sha256);
  if (target?.kind === "project_context") return Boolean(target.project_id && Number.isInteger(target.context_revision) && Number.isInteger(target.brief_revision) && target.sha256)
    && (!target.goal_source_ref || hasExactRef(target.goal_source_ref) && target.goal_source_ref.kind === "research_goal" && target.goal_source_ref.branch === "trunk" && target.goal_source_ref.phase === "P1" && target.goal_source_ref.family === "research_basis" && target.goal_source_ref.entry_pointer === GOAL_POINTER);
  if (target?.kind === "p4_pause") return target.phase === "P4" && Boolean(target.branch && target.run_id && target.request_id && target.revision != null && target.sha256);
  if (target?.kind === "phase_issue") return hasExactRef(target) && Boolean(target.entry_pointer && target.object_id);
  if (target?.kind === "notation_entry") return hasExactRef(target) && /^[a-f0-9]{64}$/.test(target.snapshot_sha256 || "")
    && typeof target.entry_id === "string" && Boolean(target.entry_id.trim()) && target.object_id === target.entry_id;
  if (target?.kind === "report_section") return hasExactRef(target) && target.phase === "P5" && target.family === "technical_report"
    && ["problem", "model", "existing_approaches", "justification", "numerical_analysis", "limitations", "reproducibility"].includes(target.object_id);
  return hasExactRef(target) && target.phase === "P3" && target.kind === "assumption"
    && ["theory_record", "complete_theory"].includes(target.family) && Boolean(target.object_id);
}

export function conversationsForTarget(conversations, target) {
  if (!isConversationTarget(target)) return [];
  return (conversations || []).filter((conversation) => {
    const source = conversation.target;
    if (target.kind === "project_context") return conversation.assessment_purpose === "project_context" && isConversationTarget(source)
      && source.kind === target.kind && source.project_id === target.project_id && (source.object_id || "") === (target.object_id || "")
      && Boolean(source.goal_source_ref) === Boolean(target.goal_source_ref);
    return ["explanation", "issue_explanation", "model_dialogue", "issue_suggestions"].includes(conversation.assessment_purpose) && isConversationTarget(source)
      && (conversation.assessment_purpose === "issue_suggestions") === (conversationPurpose(target) === "issue_suggestions")
      && source.branch === target.branch && source.phase === target.phase
      && source.family === target.family && source.object_id === target.object_id && source.kind === target.kind
      && (!["p4_pause", "researcher_pause"].includes(target.kind) || source.run_id === target.run_id);
  }).sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
}

export const isEarlierConversation = (conversation, target) => target?.kind === "project_context"
  ? conversation?.target?.sha256 !== target.sha256 || conversation?.target?.context_revision !== target.context_revision || conversation?.target?.brief_revision !== target.brief_revision
    || goalSourceKey(conversation?.target?.goal_source_ref) !== goalSourceKey(target.goal_source_ref)
  : ["p4_pause", "researcher_pause"].includes(target?.kind)
  ? conversation?.target?.sha256 !== target.sha256 || conversation?.target?.revision !== target.revision
  : !sameRef(conversation?.target, target) || target?.kind === "notation_entry"
    && (conversation?.target?.snapshot_sha256 !== target.snapshot_sha256 || conversation?.target?.entry_id !== target.entry_id);
export const conversationTitle = (conversation) => conversation.turns?.[0]?.instructions
  || conversation.messages?.find((message) => ["user", "researcher"].includes(message.role))?.content
  || "Saved conversation";
export const isPendingTurn = (turn) => Boolean(turn?.state && !TERMINAL.has(turn.state));

export function conversationDraftKey(projectId, target, conversationId = "new") {
  return `assumption-conversation:${JSON.stringify([projectId, target?.branch, target?.phase,
    target?.family, target?.generation_id, target?.sha256, target?.object_id, target?.run_id, target?.request_id, target?.revision, target?.kind, target?.context_revision, target?.brief_revision, conversationId,
    ...(target?.goal_source_ref ? [goalSourceKey(target.goal_source_ref)] : []),
    ...(target?.kind === "notation_entry" ? [target.snapshot_sha256, target.entry_id] : []),
    ...(conversationPurpose(target) === "issue_suggestions" ? ["issue_suggestions"] : [])])}`;
}

const sessionDrafts = new Map();
const storageFailures = new Set();
const draftListeners = new Set();
export function subscribeConversationDrafts(listener) {
  draftListeners.add(listener);
  return () => draftListeners.delete(listener);
}
export function conversationDrafts(prefix) {
  try {
    const storage = globalThis.sessionStorage;
    for (let index = 0; index < (storage?.length || 0); index++) {
      const key = storage.key(index);
      if (key?.startsWith(prefix) && !sessionDrafts.has(key)) readConversationDraft(key);
    }
  } catch { /* The in-session map remains the source when storage is unavailable. */ }
  return [...sessionDrafts.entries()].filter(([key]) => key.startsWith(prefix)).map(([key, draft]) => ({ key, draft }));
}
export function readConversationDraft(key) {
  if (storageFailures.has(key)) return sessionDrafts.get(key) || null;
  try {
    const storage = globalThis.sessionStorage;
    if (!storage) return sessionDrafts.get(key) || null;
    const draft = JSON.parse(storage.getItem(key) || "null");
    if (draft) sessionDrafts.set(key, draft); else sessionDrafts.delete(key);
    return draft;
  } catch { return sessionDrafts.get(key) || null; }
}

export function saveConversationDraft(key, draft) {
  if (draft) sessionDrafts.set(key, draft); else sessionDrafts.delete(key);
  try {
    const storage = globalThis.sessionStorage;
    if (!storage) { storageFailures.add(key); return; }
    if (draft) storage.setItem(key, JSON.stringify(draft)); else storage.removeItem(key);
    storageFailures.delete(key);
  } catch { storageFailures.add(key); }
  finally { for (const listener of draftListeners) listener(key); }
}

export function assumptionSource(target) {
  return Object.fromEntries(["branch", "phase", "family", "generation_id", "sha256", "run_id", "package_id", "stage_id", "object_id", "kind", "entry_pointer", "request_id", "revision", "project_id", "context_revision", "brief_revision", "model_ref", "goal_source_ref", "snapshot_sha256", "entry_id"]
    .filter((key) => target?.[key] != null).map((key) => [key, target[key]]));
}
