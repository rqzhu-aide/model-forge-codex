import React, { createContext, useContext } from "react";
import { hasExactRef } from "../research";
import { ResearchDocument, SourceRef } from "./Shared";
import { ActionIcon } from "./Visuals";

const Sources = createContext({});
export const EmpiricalSourceProvider = Sources.Provider;

// A run URI is only a locator. Bind it through an authored digest and the
// matching projected record or verified file, never through its filename.
export function empiricalSource(source, { branch, artifacts = [], records = [], files = [] } = {}) {
  const match = typeof source === "string" && source.match(/^(run:\/\/([^/#?]+)\/[^#?]+)(?:#(.*))?$/);
  if (!match) return null;
  const [, uri, runId, fragment = ""] = match;
  const pointers = [...artifacts, ...files].filter((item) => item.uri === uri && /^[a-f0-9]{64}$/.test(item.sha256 || ""));
  const digests = new Set(pointers.map((item) => item.sha256));
  if (digests.size !== 1) return null;
  const digest = [...digests][0];
  const references = new Map();
  for (const record of records) {
    const ref = record?.generation_ref;
    if (!record?.source_error && hasExactRef(ref) && ref.branch === branch && ref.run_id === runId && ref.sha256 === digest) {
      references.set([ref.branch, ref.phase, ref.family, ref.generation_id, ref.sha256, ref.run_id, ref.package_id].join("|"), ref);
    }
  }
  if (references.size > 1) return null;
  if (references.size === 1) return { reference: { ...[...references.values()][0], ...(fragment.startsWith("/") ? { entry_pointer: fragment } : {}) } };
  const verifiedFiles = files.filter((file) => file.source_verified === true && !file.source_error
    && (file.generation_ref?.branch || file.branch) === branch
    && (file.sha256 || file.artifact_sha256) === digest && /^\/api\//.test(file.artifact_url || ""));
  const exactFiles = verifiedFiles.filter((file) => file.uri === uri);
  const candidates = exactFiles.length ? exactFiles : verifiedFiles.filter((file) => !file.uri && file.producing_run_id === runId);
  const urls = new Set(candidates.map((file) => file.artifact_url));
  return urls.size === 1 ? { artifact_url: [...urls][0] + (fragment ? `#${fragment}` : "") } : null;
}

export function useEmpiricalSourceLink() {
  const sources = useContext(Sources);
  if (!sources.branch) return undefined;
  return (source, label) => {
    if (!source.startsWith("run://")) return null;
    const target = empiricalSource(source, sources);
    if (target?.reference) return <SourceRef reference={target.reference} onOpen={sources.onSource} label={label} />;
    if (target?.artifact_url) return <a className="source-link ui-action" data-action="source" data-ui-role="system" href={target.artifact_url} target="_blank" rel="noreferrer"><ActionIcon name="source" />{label}</a>;
    return <span className="note">{label} (source unavailable)</span>;
  };
}

export default function EmpiricalDocument({ text, ...props }) {
  const link = useEmpiricalSourceLink();
  return <ResearchDocument {...props} text={text} renderSourceLink={link} />;
}
