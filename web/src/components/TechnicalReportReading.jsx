import React, { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { hasExactRef, sameRef } from "../research";
import { researchDocumentContent, researchDocumentTitle } from "../researchContent";
import { REPORT_SECTION_KEYS, reportSectionHeadings, reportReferenceBoundary } from "../reportSections";
import { Dialog, ResearchDocument, SourceRef, MethodStatusNote } from "./Shared";
import { ActionButton, ActionIcon, EmptyState } from "./Visuals";
import { PhaseTabs, ScientificDocuments, ManuscriptReviewStatus } from "./PhaseReading";
import ClaimTraceability from "./ClaimTraceability";
import { NotationLookup } from "./SharedNotation";
import { reportHtmlPreview, bindReportHtmlFrame } from "../reportHtmlSource";
import "../technicalReportReading.css";

export const isTechnicalReport = (document) => ["technical_report", "technical_report_candidate"].includes(document?.kind);
const usableArtifactUrl = (url) => typeof url === "string" && /^\/api\//.test(url);
const verifiedMaterial = (material) => material?.source_verified === true && !material.source_error && usableArtifactUrl(material.artifact_url);
const markdownMaterial = (material) => material?.media_type?.split(";")[0] === "text/markdown" || /\.md$/i.test(material?.authored_path || material?.path || "");
const htmlMaterial = (material) => material?.media_type?.split(";")[0] === "text/html" || /\.html?$/i.test(material?.authored_path || material?.path || "");
const readableMaterial = (material) => markdownMaterial(material) || htmlMaterial(material);
const fragmentName = (fragment) => { try { return decodeURIComponent(fragment); } catch { return fragment; } };
const materialPath = (source, basePath) => {
  if (/^(?:[a-z][a-z\d+.-]*:|\/)/i.test(source)) return source;
  const parts = basePath.split("/").slice(0, -1);
  for (const part of source.split("/")) {
    if (!part || part === ".") continue;
    if (part === "..") { if (!parts.length) return null; parts.pop(); }
    else parts.push(part);
  }
  return parts.join("/");
};

export function retainedReportMaterial(materials, source, basePath = "") {
  const separator = source.indexOf("#");
  const path = separator < 0 ? source : source.slice(0, separator);
  const fragment = separator < 0 ? "" : fragmentName(source.slice(separator + 1));
  const resolved = materialPath(path, basePath);
  if (resolved === null) return { material: null, fragment, path };
  const authored = materials.filter((item) => item.authored_path === resolved);
  const matches = authored.length ? authored : materials.filter((item) => [item.path, item.artifact_path, item.artifact_id, item.uri, item.artifact_url].includes(resolved)
    || basePath && [item.artifact_id, item.uri, item.artifact_url].includes(path));
  return { material: matches.length === 1 ? matches[0] : null, fragment, path: resolved };
}

const materialHref = (material, fragment) => material.artifact_url + (fragment ? `#${encodeURIComponent(fragment)}` : "");
const materialBase = (material, path) => material.authored_path || path || material.path || material.artifact_path || "";

export function printableReportMaterial(portable, material, materials, primaryId) {
  const id = material?.artifact_id;
  return usableArtifactUrl(portable) && verifiedMaterial(material) && material.media_type === "text/markdown"
    && typeof id === "string" && id && id !== primaryId
    && materials.filter((item) => item.artifact_id === id).length === 1
    ? `${portable}${portable.includes("?") ? "&" : "?"}material_id=${encodeURIComponent(id)}` : null;
}

function retainedFileLink(materials, source, label, basePath = "", notationRecord, onSource) {
  const { material, fragment, path } = retainedReportMaterial(materials, source, basePath);
  if (!verifiedMaterial(material)) return <span className="note warn">{label}: {material?.source_error || "The exact retained file is unavailable."}</span>;
  return readableMaterial(material)
    ? <ReportMaterialLink {...{ material, fragment, materials, label, notationRecord, onSource }} path={materialBase(material, path)} />
    : <a href={materialHref(material, fragment)} target="_blank" rel="noreferrer">{label}</a>;
}

function retainedImage(materials, source, caption, basePath = "") {
  const { material, fragment } = retainedReportMaterial(materials, source, basePath);
  return verifiedMaterial(material) && /^image\//.test(material.media_type || "")
    ? <span className="report-inline-exhibit"><img src={materialHref(material, fragment)} alt={caption} loading="lazy" /><span className="note report-exhibit-caption">{caption}</span></span>
    : <span className="note warn">{caption || "Report figure"}: {material?.source_error || "The exact retained figure is unavailable."}</span>;
}

export function ReportMaterialLink({ material, fragment = "", path, materials, label, sourceAction = false, notationRecord, onSource }) {
  const [open, setOpen] = useState(false);
  const invoker = useRef(null);
  return <><a href={materialHref(material, fragment)} ref={invoker} className={sourceAction ? "source-link ui-action" : undefined} data-ui-role={sourceAction ? "system" : undefined} onClick={(event) => { event.preventDefault(); setOpen(true); }}>{sourceAction && <ActionIcon name="source" />}{label}</a>
    {open && createPortal(<ReportMaterialDialog {...{ material, fragment, path, materials, notationRecord, onSource }} onClose={() => setOpen(false)} returnFocus={invoker} />, document.body)}</>;
}

export function ReportMaterialDialog({ material, fragment = "", path, materials, onClose, returnFocus, notationRecord, onSource }) {
  const [content, setContent] = useState({ loading: true });
  const [attempt, setAttempt] = useState(0);
  const [missingAnchor, setMissingAnchor] = useState("");
  const [sourceError, setSourceError] = useState("");
  const [nestedSource, setNestedSource] = useState(null);
  const root = useRef(null);
  const htmlFrame = useRef(null);
  const frameCleanup = useRef(null);
  const isHtml = htmlMaterial(material);
  const prefix = `report-material-${useId().replace(/[^a-zA-Z0-9_-]/g, "_")}`;
  const anchorId = (name) => `${prefix}-${Array.from(name).map((character) => character.codePointAt(0).toString(16)).join("-")}`;
  const focusAnchor = (name) => {
    const matches = name ? [...(root.current?.querySelectorAll("[data-material-anchor]") || [])].filter((element) => element.dataset.materialAnchor === name) : [];
    const target = name ? matches.length === 1 ? matches[0] : null : root.current;
    setMissingAnchor(target || !name ? "" : name);
    if (!target) return;
    target.scrollIntoView({ block: "start" }); target.focus({ preventScroll: true });
  };
  useEffect(() => {
    let active = true;
    setContent({ loading: true });
    fetch(material.artifact_url).then((response) => {
      if (!response.ok) throw new Error(`The retained supporting text could not be loaded (${response.status}).`);
      return response.text();
    }).then((text) => { if (active) setContent(isHtml ? { html: reportHtmlPreview(text) } : { text }); })
      .catch((error) => { if (active) setContent({ error: error.message }); });
    return () => { active = false; };
  }, [material.artifact_url, material.sha256, material.artifact_sha256, isHtml, attempt]);
  useEffect(() => () => frameCleanup.current?.(), [content.html]);
  useEffect(() => { if (content.text !== undefined) focusAnchor(fragment); }, [content.text, fragment]);
  const htmlSourceLink = (source, label, invoker) => {
    setSourceError("");
    if (/^https?:\/\//i.test(source)) { window.open(source, "_blank", "noopener,noreferrer"); return; }
    const resolved = retainedReportMaterial(materials, source, path);
    if (!verifiedMaterial(resolved.material)) { setSourceError(`${label || "Supporting source"}: ${resolved.material?.source_error || "The exact retained file is unavailable."}`); return; }
    if (readableMaterial(resolved.material)) setNestedSource({ ...resolved, path: materialBase(resolved.material, resolved.path), returnFocus: { current: invoker || htmlFrame.current } });
    else window.open(materialHref(resolved.material, resolved.fragment), "_blank", "noopener,noreferrer");
  };
  return <Dialog title="Research source" onClose={onClose} returnFocus={returnFocus}>
    <NotationLookup record={material._notation || material.notation_snapshot ? material : notationRecord} section={material.notation_section || material.artifact_id} onSource={onSource} />
    {content.loading ? <p className="note" role="status">Loading supporting detail…</p>
      : content.error ? <div className="error" role="alert">{content.error}<ActionButton action="retry" onClick={() => setAttempt((value) => value + 1)}>Retry</ActionButton></div>
      : content.html !== undefined ? <>
        {missingAnchor && <p className="note warn" role="status">The retained document has no unique section named {missingAnchor}.</p>}
        {sourceError && <p className="note warn" role="status">{sourceError}</p>}
        <iframe ref={htmlFrame} className="report-html-source" title="Retained supporting document" sandbox="allow-same-origin" srcDoc={content.html} onLoad={() => {
          frameCleanup.current?.();
          frameCleanup.current = bindReportHtmlFrame(htmlFrame.current, { fragment, onClose, onSourceLink: htmlSourceLink, onMissingAnchor: setMissingAnchor });
        }} />
      </> : <div ref={root} tabIndex={-1}>
        {missingAnchor && <p className="note warn" role="status">The retained document has no unique section named {missingAnchor}.</p>}
        <ResearchDocument text={content.text}
          renderAnchor={(name) => <span id={anchorId(name)} data-material-anchor={name} tabIndex={-1} />}
          renderInternalLink={(href, label) => <a href={`#${anchorId(fragmentName(href.slice(1)))}`} onClick={(event) => { event.preventDefault(); focusAnchor(fragmentName(href.slice(1))); }}>{label}</a>}
          renderFileLink={(source, label) => retainedFileLink(materials, source, label, path, notationRecord, onSource)}
          renderImage={(source, caption) => retainedImage(materials, source, caption, path)} />
      </div>}
    {nestedSource && createPortal(<ReportMaterialDialog material={nestedSource.material} fragment={nestedSource.fragment} path={nestedSource.path} materials={materials} notationRecord={notationRecord} onSource={onSource} onClose={() => setNestedSource(null)} returnFocus={nestedSource.returnFocus} />, document.body)}
  </Dialog>;
}

export function TechnicalReportDocument({ document, onSource, showRecordSource = true, onDiscussSection }) {
  const record = document.structured || document;
  const completion = document.completion || record.completion;
  const model = document.method_identity || record.method_identity;
  const ref = document.generation_ref;
  const reviewed = document.review_status === "independently_reviewed";
  const exactReview = reviewed && hasExactRef(ref) && (!document.reviewed_report_ref || (hasExactRef(document.reviewed_report_ref) && sameRef(document.reviewed_report_ref, ref)));
  const reviewMessage = !hasExactRef(ref) ? "The report version is unidentified; independent review of this version cannot be established."
    : exactReview ? "This version was independently reviewed"
    : document.reviewed_report_ref && !hasExactRef(document.reviewed_report_ref) ? "The report version covered by review is unidentified; independent review of this version cannot be established."
    : document.reviewed_report_ref && !sameRef(document.reviewed_report_ref, ref) ? "Review concerns an earlier version; it does not confirm independent review of this draft."
    : document.review_status === "not_independently_reviewed" ? "This version has not been independently reviewed"
    : "I can't confirm an independent review of this draft.";
  const portable = hasExactRef(ref) && usableArtifactUrl(document.portable_artifact_url) ? document.portable_artifact_url : null;
  const materials = document.report_materials || document.supplementary_artifacts || [];
  const readingAnchor = `technical-report:${ref?.generation_id || document.report_generation_id || "unavailable"}`;
  const anchorId = (name) => `report-${ref?.generation_id || document.report_generation_id}-${name}`;
  const content = researchDocumentContent(document);
  const anchors = document.section_anchors || record.section_anchors;
  const reservedAnchors = new Set([...REPORT_SECTION_KEYS, "references"].map((key) => anchors?.[key]).filter(Boolean));
  const sectionHeadings = reportSectionHeadings(content, anchors);
  let referenceBoundary = null; let boundaryError = "";
  try { referenceBoundary = reportReferenceBoundary(content, anchors); }
  catch (error) { boundaryError = error.message; }
  const primary = record.report_artifact || document.report_artifact || {};
  const primaryPath = record.artifact_authored_paths?.[primary.artifact_id] || primary.authored_path || primary.path || primary.artifact_path || "";
  const canDiscuss = document.kind === "technical_report" && hasExactRef(ref) && ref.phase === "P5" && ref.family === "technical_report" && onDiscussSection;
  const renderHeading = ({ level, path, children }) => {
    const Heading = `h${Math.max(1, Math.min(6, level))}`;
    if (referenceBoundary?.headingPath === path) return <div className="report-reference-heading" data-reading-anchor={`${readingAnchor}:references`}><Heading>{children}</Heading></div>;
    const section = sectionHeadings.get(path);
    if (!section) return null;
    return <div className="report-section-heading" data-report-section={section.key} data-reading-anchor={`${readingAnchor}:section:${section.key}`}>
      <Heading>{children}</Heading>
      <NotationLookup record={document} section={section.key} onSource={onSource} />
      {canDiscuss && <ActionButton action="ask" uiRole="research" className="report-section-discuss" title={`Discuss or comment on ${section.label}`} aria-label={`Discuss or comment on ${section.label}`} onClick={() => onDiscussSection({ ...ref, kind: "report_section", object_id: section.key, label: section.label, assessmentPurpose: "model_dialogue", responsible_role: "research_lead" })}>Discuss</ActionButton>}
    </div>;
  };
  const fileLink = (source, label) => retainedFileLink(materials, source, label, primaryPath, document, onSource);
  const image = (source, caption) => retainedImage(materials, source, caption, primaryPath);
  return <article className="scientific-block technical-report" data-reading-anchor={readingAnchor}>
    {!(typeof content === "string" && /^\s*#\s+/.test(content)) && <h3>{researchDocumentTitle(document) || "Technical report"}</h3>}
    <dl className="manuscript-metadata report-metadata">
      <div><dt>Completion</dt><dd>{completion?.status === "complete" ? "Complete report" : completion?.status === "interim" ? "Interim report" : "Completion not established"}</dd></div>
      <div><dt>Independent review</dt><dd>{reviewMessage}</dd></div>
    </dl>
    {completion?.missing_work?.length > 0 && <section className="report-completion-gaps"><h4>Work still needed</h4><ResearchDocument text={completion.missing_work} /></section>}
    {document.method_status && <MethodStatusNote status={document.method_status} onOpen={onSource} />}
    {(document.context_change_notices || []).map((notice, index) => <p className={`note${notice.status === "reassessment_required" ? " warn" : ""}`} key={index}>{notice.message || (notice.status === "reassessment_required" ? "This report cites context that changed and needs reassessment." : "The saved context changed after this report was produced. Its applicability has not been reassessed.")} {notice.item_id && `${notice.item_id}: revision ${notice.previous_revision ?? "absent"} to ${notice.current_revision ?? "absent"}.`}</p>)}
    {document.report_materials_error && <p className="note warn">{document.report_materials_error}</p>}
    {boundaryError && <p className="note warn" role="status">The report's References boundary could not be verified. {boundaryError}</p>}
    <div className="report-utility-row">
    <NotationLookup record={document} onSource={onSource} />
    {(model || document.problem_context_ref || record.problem_context_ref || document.report_generation_id || ref?.generation_id) && <details className="research-details report-source-details" data-reading-anchor={`${readingAnchor}:source-details`}><summary>Source details</summary><dl className="manuscript-metadata report-metadata">
      {model && <div><dt>Model identity</dt><dd>{model.stable_id || model.method_id || "Selected model"} · {model.version ?? "Version not recorded"}</dd></div>}
      {model && <div><dt>Model version</dt><dd>{model.version ?? "Version not recorded"}</dd></div>}
      {(document.problem_context_ref || record.problem_context_ref) && <div><dt>Problem context</dt><dd>Revision {(document.problem_context_ref || record.problem_context_ref).revision}</dd></div>}
      {(document.report_generation_id || ref?.generation_id) && <div><dt>Report generation</dt><dd className="identity-line">{document.report_generation_id || ref.generation_id}</dd></div>}
    </dl></details>}
    <details className="research-details report-tools" data-reading-anchor={`${readingAnchor}:tools`}><summary>Report tools</summary>
      <div className="btnrow report-export-actions">{showRecordSource && <SourceRef reference={ref} onOpen={onSource} label="Inspect exact report source" />}
        {portable && <><a className="source-link ui-action" data-action="save" data-ui-role="system" href={`${portable}${portable.includes("?") ? "&" : "?"}download=1`} download><ActionIcon name="save" />Download offline HTML</a><a className="source-link ui-action" data-action="source" data-ui-role="system" href={portable} target="_blank" rel="noreferrer"><ActionIcon name="source" />Open HTML report</a></>}
        {usableArtifactUrl(document.primary_artifact_url) && <a className="source-link ui-action" data-action="source" data-ui-role="system" href={document.primary_artifact_url} target="_blank" rel="noreferrer"><ActionIcon name="source" />Open retained Markdown source</a>}
      </div>
      <p className="note">{portable ? "Read and share the report as HTML, with rendered mathematics, figures, references and linked supporting documents. The proof appendix stays separate from the main account." : "Offline export is unavailable for this report version."}</p>
    </details>
    </div>
    {document.document_error ? <p className="error" role="alert">The retained report text could not be loaded. {document.document_error}</p> : <ResearchDocument text={content} renderHeading={renderHeading} renderImage={image} renderFileLink={fileLink} renderAnchor={(name, path) => reservedAnchors.has(name) && !/^document\.block\d+$/.test(path) ? <></> : <span id={anchorId(name)} className="report-anchor" tabIndex={-1} />} renderInternalLink={(href, label) => <a href={`#${anchorId(fragmentName(href.slice(1)))}`}>{label}</a>} />}
    {materials.length > 0 && <details className="research-details report-materials" data-reading-anchor={`${readingAnchor}:materials`}><summary>Sources and reproducibility</summary>{materials.map((artifact, index) => {
      const printable = printableReportMaterial(portable, artifact, materials, primary.artifact_id);
      const label = artifact.label || artifact.title || artifact.authored_path || artifact.path || "Supporting document";
      return <div className="report-material-actions" key={index}>{verifiedMaterial(artifact) ? readableMaterial(artifact) ? <ReportMaterialLink material={artifact} path={materialBase(artifact)} materials={materials} label={label} sourceAction notationRecord={document} onSource={onSource} /> : <a className="source-link ui-action" data-ui-role="system" href={artifact.artifact_url} target="_blank" rel="noreferrer"><ActionIcon name="source" />{label}</a> : <p className="note warn">{label}: {artifact.source_error || "The retained file is unavailable."}</p>}
        {printable && <a className="source-link ui-action" data-ui-role="system" href={printable} target="_blank" rel="noreferrer" aria-label={`Open HTML edition with ${label}`} title={`Open HTML edition with ${label}`}><ActionIcon name="source" />HTML edition</a>}
      </div>;
    })}</details>}
  </article>;
}

export default function TechnicalReportReading({ documents = [], traceability = [], decision, reviewContext, onSource, onDiscussSection, initialTab, selectedTab, onTabChange }) {
  const canonical = documents.filter((document) => document.kind === "technical_report");
  const currentRef = canonical[0]?.generation_ref;
  const reports = canonical.length ? canonical : documents.filter(isTechnicalReport);
  const candidates = canonical.length ? documents.filter((document) => document.kind === "technical_report_candidate" && !canonical.some((current) => current.generation_ref?.sha256 && current.generation_ref.sha256 === document.generation_ref?.sha256)) : [];
  const manuscripts = documents.filter((doc) => ["manuscript", "manuscript_candidate"].includes(doc.kind));
  const historicalReviews = documents.filter((doc) => doc.reviewed_manuscript_ref);
  const reviews = documents.filter((doc) => /review|audit/.test(doc.kind || "") && !historicalReviews.includes(doc));
  const changes = documents.filter((doc) => /revision|change|reconciliation/.test(doc.kind || ""));
  const supporting = documents.filter((doc) => !isTechnicalReport(doc) && !manuscripts.includes(doc) && !historicalReviews.includes(doc) && !reviews.includes(doc) && !changes.includes(doc) && !(traceability.length && doc.kind === "claim_traceability"));
  const tabs = [
    { id: "report", label: "Report", content: reports.length ? reports.map((document, index) => <TechnicalReportDocument key={document.generation_ref?.generation_id || index} document={document} onSource={onSource} onDiscussSection={onDiscussSection} />) : <EmptyState><p className="note">No technical report has been assembled for this model yet. An interim report can identify missing theory or numerical work from the available sources.</p></EmptyState> },
    { id: "evidence", label: "Supporting evidence", content: <><ClaimTraceability records={traceability} onSource={onSource} /><ScientificDocuments documents={supporting} onSource={onSource} empty="Retained model, justification, and numerical sources appear here when assembled into the report." /></> },
    { id: "reviews", label: "Reviews", content: reviews.length ? reviews.map((document, index) => {
      const target = document.reviewed_report_ref;
      const comparable = hasExactRef(target) && hasExactRef(currentRef);
      const earlier = comparable && !sameRef(target, currentRef);
      return <section key={`${document.kind}:${index}`} className="report-review"><p className={`note${earlier ? " warn" : ""}`}>{!hasExactRef(target) ? "The report version assessed by this review is not identified in the available record." : !hasExactRef(currentRef) ? "The current report is unavailable, so this review cannot be compared with it. Its assessed version is linked below." : earlier ? "This assessment concerns an earlier report version. It does not review the current version." : "This assessment concerns the current report version."}</p><SourceRef reference={target} onOpen={onSource} label="Exact report assessed by this review" /><ScientificDocuments documents={[document]} onSource={onSource} /></section>;
    }) : <p className="note">No independent report review has been retained yet.</p> },
    { id: "changes", label: "Changes", content: <>{decision?.what_changed && <ResearchDocument text={decision.what_changed} />}<ScientificDocuments documents={changes} onSource={onSource} empty={decision?.what_changed ? "" : "No report revision account has been retained yet."} /></> },
  ];
  if (candidates.length) tabs.push({ id: "candidates", label: "Retained candidates", content: <><p className="note">These retained report candidates have their own exact sources. The canonical current technical report appears in the Report tab.</p>{candidates.map((document, index) => <TechnicalReportDocument key={document.generation_ref?.generation_id || index} document={document} onSource={onSource} />)}</> });
  if (manuscripts.length) tabs.push({ id: "manuscripts", label: "Historical manuscripts", content: <><p className="note">These historical manuscripts retain their original document type and scope. They occupy their own document family and are not the current technical report.</p><ManuscriptReviewStatus context={reviewContext} onSource={onSource} /><ScientificDocuments documents={[...manuscripts, ...historicalReviews]} onSource={onSource} /></> });
  return <section className="card technical-report-reader" data-card-role="research"><PhaseTabs heading="Technical report and reviews" label="Report detail" initialTab={initialTab} selectedTab={selectedTab === "manuscript" ? "manuscripts" : selectedTab} onTabChange={onTabChange} tabs={tabs} /></section>;
}
