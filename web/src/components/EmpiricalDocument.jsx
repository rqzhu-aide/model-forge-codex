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
  // The backend may bind an upstream run locator to the exact generation
  // frozen for this evaluation, including a shared P2 source on trunk.
  for (const file of files) {
    const ref = file.generation_ref;
    if (file.uri === uri && file.source_verified === true && !file.source_error && file.branch === branch
      && hasExactRef(ref) && ref.run_id === runId && ref.sha256 === digest && file.sha256 === digest) {
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
  return (source, label, _path, { bare = false } = {}) => {
    if (!source.startsWith("run://")) return null;
    const target = empiricalSource(source, sources);
    const visible = bare ? empiricalSourceLabel(source, sources, target) : label;
    if (target?.reference) {
      const link = <SourceRef reference={target.reference} onOpen={sources.onSource} label={visible} />;
      return bare ? <span title={source}>{link}</span> : link;
    }
    if (target?.artifact_url) return <a className="source-link ui-action" data-action="source" data-ui-role="system" href={target.artifact_url} title={bare ? source : undefined} target="_blank" rel="noreferrer"><ActionIcon name="source" />{visible}</a>;
    return <span className="note" title={bare ? source : undefined}>{visible} (source unavailable)</span>;
  };
}

// Bare prose has no authored label. Use a title only from the verified exact
// target; an unresolved locator gets its filename, with its full URI retained.
export function empiricalSourceLabel(source, { files = [], records = [] } = {}, target) {
  const uri = source.split("#", 1)[0];
  const sameReference = (reference) => reference && ["branch", "phase", "family", "generation_id", "sha256", "run_id", "stage_id", "package_id"]
    .every((key) => reference[key] === target.reference[key]);
  const matching = target ? files.filter((file) => file.uri === uri && file.source_verified === true && !file.source_error
    && (target.artifact_url ? target.artifact_url.split("#", 1)[0] === file.artifact_url
      : sameReference(file.generation_ref))) : [];
  if (target?.reference) matching.push(...records.filter((record) => !record.source_error
    && sameReference(record.generation_ref)));
  const labels = [...new Set(matching.map((item) => item.title || item.label).filter((label) => typeof label === "string" && label.trim()))];
  return labels.length === 1 ? labels[0] : uri.slice(uri.lastIndexOf("/") + 1) || "Retained source";
}

export default function EmpiricalDocument({ text, ...props }) {
  const link = useEmpiricalSourceLink();
  return <ResearchDocument {...props} text={text} renderSourceLink={link} />;
}
