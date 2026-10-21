import { hasExactRef, refKey } from "./research.js";
import { researchBlocks } from "./researchMarkdown.js";
import { REPORT_SECTION_KEYS, reportSectionHeadings } from "./reportSections.js";

function reportTargetReference(source, projectId, conversation) {
  const target = conversation?.target;
  if (!projectId || conversation?.source_error || !hasExactRef(target) || target.kind !== "report_section"
      || target.phase !== "P5" || target.family !== "technical_report" || !REPORT_SECTION_KEYS.includes(target.object_id)
      || !/^[a-f0-9]{64}$/.test(target.sha256) || !target.run_id || !target.package_id) return null;
  const [project, branch, phase, family, generation] = [projectId, target.branch, target.phase, target.family, target.generation_id].map(encodeURIComponent);
  const url = `/api/v1/projects/${project}/branches/${branch}/phases/${phase}/records/${family}/${generation}`;
  if (conversation.source_url !== url) return null;
  if (source === url) return target;
  if (!source.startsWith(`${url}#`)) return null;
  const anchor = source.slice(url.length + 1);
  const text = conversation.target_statement;
  const firstHeading = researchBlocks(text).findIndex((block) => block.kind === "heading");
  const section = reportSectionHeadings(text, { [target.object_id]: anchor }).get(`document.block${firstHeading}`);
  return section?.anchor === anchor ? target : null;
}

// Only the API's uniquely linked frozen evidence may turn an authored input
// path or projected record URL into a source-window action. A report discussion
// also retains its own exact target and authored section heading. Paths are not opened.
export function conversationSourceReference(source, runId, evidence = [], earlierTurns = [], { projectId, conversation } = {}) {
  if (typeof source !== "string" || typeof runId !== "string" || !runId) return null;
  const local = source.replaceAll("\\", "/");
  if (!/^(?:[A-Za-z]:\/|\/)/.test(local) || local.split("/").some((part) => part === "." || part === "..")) return null;
  const matches = new Map();
  const target = reportTargetReference(source, projectId, conversation);
  if (target) matches.set(refKey(target), target);
  for (const turn of [{ run_id: runId, evidence_refs: evidence }, ...earlierTurns]) {
    if (!turn.run_id) continue;
    for (const item of turn.evidence_refs || []) {
      const ref = item.generation_ref;
      if (item.source_error || !hasExactRef(ref)) continue;
      const suffix = `/runs/${turn.run_id}/inputs/${ref.branch}/${ref.phase.toLowerCase()}/${ref.family}/${ref.generation_id}.json`;
      const recordUrl = item.source_url?.startsWith("/api/") ? item.source_url : null;
      const exactRecordUrl = recordUrl && (source === recordUrl || item.object_id && source === `${recordUrl}#${item.object_id}`);
      if (local.endsWith(suffix) || exactRecordUrl) matches.set(refKey(ref), ref);
    }
  }
  return matches.size === 1 ? [...matches.values()][0] : null;
}
