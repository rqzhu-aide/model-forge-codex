import React from "react";
import { groupRunFindings } from "../runFindings.js";

const member = (family) => ({ "p1.lead_literature": "Lead", "p1.theory_literature": "Theorist", "p1.empirical_literature": "Analyst" }[family] || family);
const value = (item) => Array.isArray(item) ? item.map((part) => typeof part === "object" ? JSON.stringify(part) : part).join("; ") : String(item ?? "Not recorded");
export default function RunFindings({ findings }) {
  return groupRunFindings(findings).map((group, index) => <article className="finding" key={index}>
    {group.title ? <><h3>{group.title}</h3><p>{group.action}</p>{group.fields.map((field) => <div key={field}><strong>{field.replaceAll("_", " ")}</strong><dl>{group.entries.map((entry) => <React.Fragment key={`${entry.family}:${entry.json_pointer}`}><dt>{member(entry.family)}</dt><dd>{value(entry.source?.[field])}</dd></React.Fragment>)}</dl></div>)}</> : <p>{group.findings[0].code === "literature.source_identity_conflict" ? "Citation metadata needs review. Exact differences were not recorded for this older run; expand the finding sources to inspect its records." : group.findings[0].message}</p>}
    <details><summary className="note">Finding sources ({group.findings.length})</summary>{group.findings.map((finding, owner) => <div key={owner}><span className="code">{finding.code}</span><p className="ptr">{finding.object_id} · {finding.json_pointer || "file"}</p><p>{finding.message}</p></div>)}</details>
  </article>);
}
