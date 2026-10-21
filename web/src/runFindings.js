export function groupRunFindings(findings = []) {
  const groups = new Map();
  for (const [index, finding] of findings.entries()) {
    const detail = finding.details;
    const key = detail?.kind === "citation_conflict" && detail.group_id ? `citation:${detail.group_id}` : finding.code === "literature.source_identity_conflict" ? `legacy:${finding.message}` : `finding:${index}`;
    const group = groups.get(key) || { title: detail?.paper_title || "", action: detail?.action || "", fields: [], entries: [], findings: [] };
    group.findings.push(finding);
    for (const field of detail?.differing_fields || []) if (!group.fields.includes(field)) group.fields.push(field);
    for (const entry of detail?.entries || []) if (!group.entries.some((old) => old.family === entry.family && old.json_pointer === entry.json_pointer && old.source_sha256 === entry.source_sha256)) group.entries.push(entry);
    groups.set(key, group);
  }
  return [...groups.values()];
}
