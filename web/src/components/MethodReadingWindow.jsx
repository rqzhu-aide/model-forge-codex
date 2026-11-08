import React, { useRef } from "react";
import { Dialog } from "./Shared";
import { formatReadingSize } from "../readingSize";
import { ActionButton } from "./Visuals";
import { useReadingPosition } from "../readingWindowPosition";

export function ReadingDocumentButton({ title, size, sizeLabel, className = "", ...props }) {
  const estimate = sizeLabel ?? (size ? formatReadingSize(size) : null);
  return <ActionButton action="source" aria-haspopup="dialog" className={`reading-button p2-reading-button ${className}`.trim()} {...props}>
    <span className="p2-reading-label"><span>{title}</span>{estimate && <span className="p2-reading-estimate">{estimate}</span>}</span>
  </ActionButton>;
}

// Reading offsets are session-only and belong to the exact contributing records.
// Opening a different project, method or published revision starts at its beginning.
export function methodReadingKey(projectId, selectedKey, name, input) {
  return JSON.stringify([projectId, selectedKey, name, input.selected?.generation_ref,
    input.selected ? null : input.catalogMethod?.source_ref, input.method?.identity, input.reviewed?.comparison?.generation_ref,
    (input.proposals || []).map((record) => record.generation_ref),
    (input.reviews || []).map((record) => record.generation_ref), input.literatureSources]);
}

export function MethodReadingWindow({ snapshot, onClose, returnFocus }) {
  const bodyRef = useRef(null);
  const { save } = useReadingPosition({ key: snapshot.key, bodyRef });
  const subtitle = snapshot.subtitle ?? (snapshot.methodTitle ? `${snapshot.methodTitle}${snapshot.version != null ? ` · Version ${snapshot.version}` : ""}` : undefined);
  const estimate = snapshot.sizeLabel ?? (snapshot.size ? formatReadingSize(snapshot.size) : null);
  return <Dialog title={snapshot.title} subtitle={subtitle} className="reading-window p2-method-reader" onClose={() => { save(); onClose(); }}
    returnFocus={returnFocus} bodyRef={bodyRef} onBodyScroll={save}>
    {estimate && <p className="note p2-reading-size">{estimate}</p>}
    {snapshot.body}
  </Dialog>;
}
