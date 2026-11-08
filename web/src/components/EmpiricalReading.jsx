import React, { useRef } from "react";
import { formatReadingSize, researchReadingSize } from "../readingSize";
import { EmpiricalSourceProvider, useEmpiricalSources } from "./EmpiricalDocument";
import { ReadingDocumentButton } from "./MethodReadingWindow";
import { readingDocumentKey, useReadingHost } from "./ReadingHost";

export function empiricalReadingSize(values, parts = []) {
  const size = researchReadingSize(values);
  return [...(size.words || size.equations ? [formatReadingSize(size)] : []), ...parts.filter(Boolean)].join(" · ");
}

// Only data is copied. Source actions deliberately use the current application
// callback, while every locator is interpreted in the producing branch.
export function empiricalReadingSnapshot({ scope, kind, title, subtitle, sizeLabel, input, sources = {}, onSource, renderBody }) {
  const frozen = structuredClone({ input, sources: { branch: sources.branch || scope?.branch,
    artifacts: sources.artifacts || [], records: (sources.records || []).filter(Boolean), files: sources.files || [] } });
  return { key: readingDocumentKey(scope, kind, frozen), title, subtitle, sizeLabel,
    body: <EmpiricalSourceProvider value={{ ...frozen.sources, onSource }}>{renderBody(frozen.input, onSource)}</EmpiricalSourceProvider> };
}

export default function EmpiricalReadingButton({ kind, title, subtitle, sizeLabel, input, renderBody, onSource, ...props }) {
  const reader = useReadingHost();
  const sources = useEmpiricalSources();
  const callback = useRef(onSource || sources.onSource); callback.current = onSource || sources.onSource;
  return <ReadingDocumentButton {...props} title={title} sizeLabel={sizeLabel} onClick={(event) => reader.open(empiricalReadingSnapshot({
    scope: reader.scope, kind, title, subtitle, sizeLabel, input, sources,
    onSource: (...args) => callback.current?.(...args), renderBody,
  }), event.currentTarget)} />;
}
