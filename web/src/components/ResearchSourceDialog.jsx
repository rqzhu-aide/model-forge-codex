import React, { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { analystQuestionContent, sourceEntry } from "../researchContent";
import { useReadingPosition } from "../readingWindowPosition";
import { readingDocumentKey } from "./ReadingHost";
import { Dialog, ResearchDocument, SourceRef } from "./Shared";
import { ActionButton } from "./Visuals";
import { ScientificDocuments, scientificDocumentLink } from "./PhaseReading";
import { EmpiricalExhibit } from "./EmpiricalQuestion";
import { TechnicalReportDocument } from "./TechnicalReportReading";
import TestedTheorySource from "./TestedTheorySource";

const documentFamilies = new Set(["manuscript", "manuscript_candidate", "technical_report", "technical_report_candidate", "implementation_record", "implementation_record_candidate", "analyst_synthesis", "theory_record", "complete_theory", "theory_candidate", "analyst_audit"]);
const reportCompanions = new Set(["decision", "phase_decision", "assembly_report", "citation_integrity_report"]);
const empiricalEntries = {
  analyst_synthesis: [/^\/question_results\/(0|[1-9]\d*)$/, "Numerical finding"],
  theory_audit: [/^\/findings\/(0|[1-9]\d*)$/, "Theory finding"],
  exhibits: [/^\/(0|[1-9]\d*)$/, "Numerical exhibit"],
};

function EvidencePassage({ document, onSource }) {
  if (document.exhibit) {
    return <EmpiricalExhibit exhibit={document.exhibit} showRecordSource={false} onSource={onSource} />;
  }
  const link = scientificDocumentLink(document, onSource);
  const text = document.family === "analyst_synthesis" ? analystQuestionContent(document.entry) : document.entry;
  return <><ResearchDocument text={text} renderSourceLink={link} renderFileLink={link} />
    {document.cited_exhibits?.length > 0 && <section><h3>Cited results</h3><div className="p2-reading-links">{document.cited_exhibits.map((item, i) =>
      item.reference ? <SourceRef key={item.reference.entry_pointer} label={item.title} reference={item.reference} onOpen={onSource} />
        : <p className="note" key={i}>{item.title}</p>)}</div></section>}</>;
}

// Following a source leaves its parent mounted, including its exact document,
// disclosure state, reading location and invoking control. Dialog owns the stack
// and returns focus when the child closes, including while it is still loading.
export default function ResearchSourceDialog({ projectId, reference, componentId = null, onClose, onCurrentTheory, returnFocus }) {
  const key = readingDocumentKey({ projectId }, "research-source", [reference, componentId]);
  const [content, setContent] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const [child, setChild] = useState(null);
  const bodyRef = useRef(null);
  const current = content?.key === key;
  const ready = current && Object.hasOwn(content, "body");
  const entrySpec = reference.phase === "P4" && Object.hasOwn(empiricalEntries, reference.family) && empiricalEntries[reference.family];
  const entryTitle = entrySpec && entrySpec[0].test(reference.entry_pointer || "") ? entrySpec[1] : null;
  const position = useReadingPosition({ key, bodyRef, ready, fragment: reference.report_fragment, sourceLocator: reference.source_locator });
  useEffect(() => {
    let active = true;
    setContent({ key, loading: true });
    const readable = (documentFamilies.has(reference.family) || reference.phase === "P5" && reportCompanions.has(reference.family)) && !componentId && !reference.entry_pointer && !reference.card_id;
    const request = (readable || entryTitle) ? api.recordDocument(projectId, reference)
      : api.recordBody(projectId, reference.branch, reference.phase, reference.family, reference.generation_id);
    request.then(body => { if (active) setContent({ key, body }); }, error => { if (active) setContent({ key, error: error.message }); });
    return () => { active = false; };
  }, [key, attempt]);
  const close = () => { position.saveBeforeChange(); onClose(); };
  const openSource = (next, nextComponent = null) => setChild({ reference: structuredClone(next), componentId: nextComponent });
  const body = content?.body;
  return <Dialog bodyRef={bodyRef} onBodyScroll={position.onScroll} returnFocus={returnFocus}
    title={componentId ? "Theory used by this evaluation" : entryTitle || "Research source"} onClose={close}>
    {!current || content.loading ? <p className="note">Loading the source…</p>
      : content.error ? <div className="error" role="alert">{content.error}<ActionButton action="retry" onClick={() => setAttempt(value => value + 1)}>Retry</ActionButton></div>
      : <>{componentId ? <TestedTheorySource document={body} componentId={componentId} onCurrentTheory={() => { position.saveBeforeChange(); onCurrentTheory(componentId); }} />
        : entryTitle && body?.entry ? <EvidencePassage document={body} onSource={openSource} />
        : (documentFamilies.has(body?.kind) || body?.phase === "P5" && reportCompanions.has(body?.kind)) && body?.generation_ref
          ? ["technical_report", "technical_report_candidate"].includes(body.kind)
            ? <TechnicalReportDocument document={body} onSource={openSource} showRecordSource={false} fragment={reference.report_fragment} />
            : <ScientificDocuments documents={[body]} onSource={openSource} showRecordSource={false} />
          : <ResearchDocument text={(reference.entry_pointer || reference.card_id) ? sourceEntry(body, reference.entry_pointer, reference.card_id) : typeof body === "string" ? body : body?.body_md || body?.text || body} />}
        <details className="research-details"><summary>Complete record and reference</summary><pre className="record">{JSON.stringify(reference, null, 2)}</pre><pre className="record">{typeof body === "string" ? body : JSON.stringify(body?.structured || body, null, 2)}</pre></details>
      </>}
    {child && <ResearchSourceDialog key={readingDocumentKey({ projectId }, "research-source", [child.reference, child.componentId])}
      projectId={projectId} {...child} onClose={() => setChild(null)} onCurrentTheory={onCurrentTheory} />}
  </Dialog>;
}
