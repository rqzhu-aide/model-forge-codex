import { humanLabel } from "./research.js";

// This is an editable reading copy of the original scientific fields. Exact
// identity and the complete definition remain in the separate source reference.
function scientificText(value, depth = 2) {
  if (value == null) return "";
  if (typeof value !== "object") return String(value);
  if (Array.isArray(value)) return value.map((item, index) => typeof item === "object" ? scientificText(item, depth) : `${index + 1}. ${item}`).filter(Boolean).join("\n\n");
  return Object.entries(value).filter(([key]) => !["identity", "content_sha256", "definition_sha256", "record_id", "source_run_id", "generation_ref"].includes(key)).map(([key, item]) => {
    if (key === "latex" && typeof item === "string") return `$$\n${item}\n$$`;
    const text = scientificText(item, Math.min(depth + 1, 6));
    return text ? `${"#".repeat(depth)} ${humanLabel(key)}\n\n${text}` : "";
  }).filter(Boolean).join("\n\n");
}

export function methodSeedMarkdown(method = {}) {
  const definition = method.canonical_definition || method.mathematical_definition?.canonical_definition || method.mathematical_definition || method.definition;
  return [method.title ? `# ${method.title}` : "", method.summary || "", method.scientific_question ? `## Research question\n\n${method.scientific_question}` : "", definition ? scientificText(definition) : "", method.assumptions?.length ? `## Assumptions\n\n${scientificText(method.assumptions)}` : "", method.limitations?.length ? `## Limitations\n\n${scientificText(method.limitations)}` : ""].filter(Boolean).join("\n\n");
}

// Keep the original source identity beside the editable scientific reading
// copy. Run launch verifies and freezes these exact published generations.
export function methodStartingPoint(method, proposal, catalogMethod) {
  return {
    title: method.title,
    specification_markdown: methodSeedMarkdown(method),
    source_reference: JSON.stringify({
      kind: "p2_method_starting_point",
      method_identity: method.identity || method.method_identity,
      // An earlier proposal keeps its own publication's recorded origin even
      // when the current catalog retains the same exact method identity.
      catalog_ref: proposal?.catalog_ref || catalogMethod?.source_ref,
      ...(proposal?.generation_ref ? { proposal_ref: proposal.generation_ref, proposal_id: proposal.proposal_id } : {}),
    }),
  };
}

export function methodStartingPointSource(suppliedMethod) {
  try {
    const source = JSON.parse(suppliedMethod?.source_reference);
    return source?.kind === "p2_method_starting_point" ? source : null;
  } catch { return null; }
}
