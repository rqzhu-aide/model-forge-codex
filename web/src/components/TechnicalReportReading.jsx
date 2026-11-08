import React, { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { hasExactRef, humanLabel, sameRef } from "../research";
import { researchDocumentContent, researchDocumentTitle } from "../researchContent";
import { researchReadingSize } from "../readingSize";
import { rememberReadingPosition, restoreReadingPosition, useReadingPosition } from "../readingWindowPosition";
import { REPORT_SECTION_KEYS, reportSectionHeadings, reportReferenceBoundary } from "../reportSections";
import { Dialog, ResearchDocument, SourceRef, MethodStatusNote } from "./Shared";
import { ActionButton, ActionIcon, EmptyState } from "./Visuals";
import { PhaseTabs, ScientificDocuments } from "./PhaseReading";
import ReportDeliveryStatus from "./ReportDeliveryStatus";
import ClaimTraceability from "./ClaimTraceability";
import { NotationLookup } from "./SharedNotation";
import { hasSharedNotation } from "../sharedNotation";
import ResearchCardLayout from "./ResearchCardLayout";
import { reportHtmlPreview, bindReportHtmlFrame } from "../reportHtmlSource";
import { ReadingDocumentButton } from "./MethodReadingWindow";
import { readingDocumentKey, useReadingHost } from "./ReadingHost";
import "../technicalReportReading.css";

export const isTechnicalReport = (document) => ["technical_report", "technical_report_candidate"].includes(document?.kind);
const usableArtifactUrl = (url) => typeof url === "string" && /^\/api\//.test(url);

export const noReportNote = "No technical report has been assembled for this model yet. An interim report can identify missing theory or numerical work from the available sources.";
export const reportExportNote = (portable) => portable ? "Shareable HTML includes rendered mathematics, figures, references and scientific source extracts. Private notes and machine paths are omitted. The proof appendix stays separate from the main account, with a standalone download. Linked code and configuration document the recorded evaluation; exporting does not rerun it." : "Offline export is unavailable for this report version.";
export const reportCompletionLabel = (document) => {
  const completion = document?.completion || document?.structured?.completion;
  return completion?.status === "complete" ? "Complete report" : completion?.status === "interim" ? "Interim report" : "Completion not established";
};
export function reportReviewMessage(document) {
  const ref = document?.generation_ref;
  const reviewed = document?.review_status === "independently_reviewed";
  const exactReview = reviewed && hasExactRef(ref) && (!document.reviewed_report_ref || (hasExactRef(document.reviewed_report_ref) && sameRef(document.reviewed_report_ref, ref)));
  return !hasExactRef(ref) ? "The report version is unidentified; independent review of this version cannot be established."
    : exactReview ? "This version was independently reviewed"
    : document.reviewed_report_ref && !hasExactRef(document.reviewed_report_ref) ? "The report version covered by review is unidentified; independent review of this version cannot be established."
    : document.reviewed_report_ref && !sameRef(document.reviewed_report_ref, ref) ? "Review concerns an earlier version; it does not confirm independent review of this draft."
    : document.review_status === "not_independently_reviewed" ? "This version has not been independently reviewed"
    : "I can't confirm an independent review of this draft.";
}
export function reportExports(document) {
  const portable = hasExactRef(document?.generation_ref) && usableArtifactUrl(document?.portable_artifact_url) ? document.portable_artifact_url : null;
  return { portable, download: portable ? `${portable}${portable.includes("?") ? "&" : "?"}download=1` : null, markdown: usableArtifactUrl(document?.primary_artifact_url) ? document.primary_artifact_url : null };
}
// The current technical report family owns the Phase 5 reading. Earlier
// article drafts no longer have a reading path here; reviews and change accounts
// are grouped by document kind, and claim traceability renders on its own.
export function partitionReportDocuments(documents = [], traceability = []) {
  const canonical = documents.filter((document) => document.kind === "technical_report");
  const reports = canonical.length ? canonical : documents.filter(isTechnicalReport);
  const candidates = canonical.length ? documents.filter((document) => document.kind === "technical_report_candidate" && !canonical.some((current) => current.generation_ref?.sha256 && current.generation_ref.sha256 === document.generation_ref?.sha256)) : [];
  const reviews = documents.filter((document) => /review|audit/.test(document.kind || "") && !/ledger|issues/.test(document.kind || ""));
  const changes = documents.filter((document) => /revision|change|reconciliation/.test(document.kind || ""));
  const supporting = documents.filter((document) => !isTechnicalReport(document) && !reviews.includes(document) && !changes.includes(document) && !(traceability.length && document.kind === "claim_traceability"));
  return { canonical, currentRef: canonical[0]?.generation_ref, reports, candidates, reviews, changes, supporting };
}
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

export function standaloneReportMaterial(portable, material, materials) {
  const id = material?.artifact_id;
  const markdownPath = (material?.authored_path || material?.path || "").replace(/\.html?$/i, ".md");
  if (!usableArtifactUrl(portable) || !verifiedMaterial(material) || !htmlMaterial(material)
      || !id || materials.filter(item => item.artifact_id === id).length !== 1
      || materials.filter(item => verifiedMaterial(item) && markdownMaterial(item) && (item.authored_path || item.path) === markdownPath).length !== 1) return null;
  const query = new URLSearchParams(portable.split("?")[1] || "");
  query.set("view", "attachment"); query.set("material_id", id);
  return `${portable.split("?")[0]}?${query}`;
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
  const [opened, setOpened] = useState(null);
  const invoker = useRef(null);
  return <><a href={materialHref(material, fragment)} ref={invoker} className={sourceAction ? "source-link ui-action" : undefined} data-ui-role={sourceAction ? "system" : undefined} onClick={(event) => { event.preventDefault(); setOpened(structuredClone({ material, fragment, path, materials, notationRecord })); }}>{sourceAction && <ActionIcon name="source" />}{label}</a>
    {opened && createPortal(<ReportMaterialDialog {...opened} onSource={onSource} onClose={() => setOpened(null)} returnFocus={invoker} />, document.body)}</>;
}

export function ReportMaterialDialog({ material, fragment = "", path, materials, onClose, returnFocus, notationRecord, onSource }) {
  const [content, setContent] = useState({ loading: true });
  const [attempt, setAttempt] = useState(0);
  const [missingAnchor, setMissingAnchor] = useState("");
  const [sourceError, setSourceError] = useState("");
  const [nestedSource, setNestedSource] = useState(null);
  const root = useRef(null);
  const bodyRef = useRef(null);
  const htmlFrame = useRef(null);
  const frameCleanup = useRef(null);
  const isHtml = htmlMaterial(material);
  const title = material.label || material.title || material.authored_path || path || material.path || "Supporting document";
  const readingKey = readingDocumentKey({ phase: "P5" }, "report-material", [material.artifact_url,
    material.sha256, material.artifact_sha256, material.generation_ref, material.artifact_id]);
  const currentContent = content.key === readingKey;
  const { save } = useReadingPosition({ key: readingKey, ready: currentContent && content.text !== undefined, bodyRef, fragment });
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
    setContent({ key: readingKey, loading: true });
    fetch(material.artifact_url).then((response) => {
      if (!response.ok) throw new Error(`The retained supporting text could not be loaded (${response.status}).`);
      return response.text();
    }).then((text) => { if (active) setContent(isHtml ? { key: readingKey, html: reportHtmlPreview(text) } : { key: readingKey, text }); })
      .catch((error) => { if (active) setContent({ key: readingKey, error: error.message }); });
    return () => { active = false; };
  }, [readingKey, isHtml, attempt]);
  useEffect(() => () => frameCleanup.current?.(), [content.html]);
  useEffect(() => { if (currentContent && content.text !== undefined && fragment) focusAnchor(fragment); }, [currentContent, content.text, fragment]);
  const close = () => { save(); frameCleanup.current?.(); frameCleanup.current = null; onClose(); };
  const htmlSourceLink = (source, label, invoker) => {
    setSourceError("");
    if (/^https?:\/\//i.test(source)) { window.open(source, "_blank", "noopener,noreferrer"); return; }
    const resolved = retainedReportMaterial(materials, source, path);
    if (!verifiedMaterial(resolved.material)) { setSourceError(`${label || "Supporting source"}: ${resolved.material?.source_error || "The exact retained file is unavailable."}`); return; }
    if (readableMaterial(resolved.material)) setNestedSource({ ...resolved, path: materialBase(resolved.material, resolved.path), returnFocus: { current: invoker || htmlFrame.current } });
    else window.open(materialHref(resolved.material, resolved.fragment), "_blank", "noopener,noreferrer");
  };
  return <Dialog title={title} onClose={close} returnFocus={returnFocus} bodyRef={bodyRef} onBodyScroll={save}>
    <NotationLookup record={material._notation || material.notation_snapshot ? material : notationRecord} section={material.notation_section || material.artifact_id} onSource={onSource} />
    {!currentContent || content.loading ? <p className="note" role="status">Loading supporting detail…</p>
      : content.error ? <div className="error" role="alert">{content.error}<ActionButton action="retry" onClick={() => setAttempt((value) => value + 1)}>Retry</ActionButton></div>
      : content.html !== undefined ? <>
        {missingAnchor && <p className="note warn" role="status">The retained document has no unique section named {missingAnchor}.</p>}
        {sourceError && <p className="note warn" role="status">{sourceError}</p>}
        <iframe ref={htmlFrame} className="report-html-source" title={`${title} retained HTML`} sandbox="allow-same-origin" srcDoc={content.html} onLoad={() => {
          frameCleanup.current?.();
          const frame = htmlFrame.current;
          const unbind = bindReportHtmlFrame(frame, { fragment, onClose: close, onSourceLink: htmlSourceLink, onMissingAnchor: setMissingAnchor });
          const sourceDocument = frame?.contentDocument;
          const scrolling = sourceDocument?.scrollingElement || sourceDocument?.documentElement || sourceDocument?.body;
          const frameKey = `${readingKey}:html`;
          if (!fragment) restoreReadingPosition(frameKey, scrolling);
          const saveFrame = () => rememberReadingPosition(frameKey, scrolling);
          sourceDocument?.addEventListener("scroll", saveFrame, true);
          sourceDocument?.addEventListener("toggle", saveFrame, true);
          frameCleanup.current = () => {
            saveFrame(); unbind();
            sourceDocument?.removeEventListener("scroll", saveFrame, true);
            sourceDocument?.removeEventListener("toggle", saveFrame, true);
          };
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

function focusReportAnchor(root, id) {
  const matches = [...(root?.querySelectorAll(".report-anchor") || [])].filter((element) => element.id === id);
  const target = matches.length === 1 ? matches[0] : null;
  if (!target) return false;
  target.scrollIntoView({ block: "start" }); target.focus({ preventScroll: true });
  return true;
}

export function ReportInternalLink({ fragment, targetId, label }) {
  const [missingTarget, setMissingTarget] = useState(null);
  return <><a href={`#${targetId}`} onClick={(event) => {
    if (event.defaultPrevented || (event.button != null && event.button !== 0) || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    setMissingTarget(focusReportAnchor(event.currentTarget.closest(".technical-report"), targetId) ? null : targetId);
  }}>{label}</a>{missingTarget === targetId && <span className="note warn" role="status"> The linked section is unavailable in this retained report. <code>{fragment}</code></span>}</>;
}

export function ReportFragmentTarget({ fragment, generationId, unavailable, children }) {
  const root = useRef(null);
  const [missingAnchor, setMissingAnchor] = useState("");
  useEffect(() => {
    if (unavailable) { setMissingAnchor(""); return; }
    setMissingAnchor(focusReportAnchor(root.current, `report-${generationId}-${fragment}`) ? "" : fragment);
  }, [fragment, generationId, unavailable]);
  return <div ref={root}>
    {missingAnchor && <p className="note warn" role="status">The linked section is unavailable in this retained report. <code>{missingAnchor}</code></p>}
    {children}
  </div>;
}

export function TechnicalReportDocument({ document, onSource, showRecordSource = true, showStatusAndTools = true, onDiscussSection, fragment = "" }) {
  const record = document.structured || document;
  const completion = document.completion || record.completion;
  const model = document.method_identity || record.method_identity;
  const ref = document.generation_ref;
  const { portable, download, markdown } = reportExports(document);
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
  const article = <article className="scientific-block technical-report" data-reading-anchor={readingAnchor}>
    {!(typeof content === "string" && /^\s*#\s+/.test(content)) && <h3>{researchDocumentTitle(document) || "Technical report"}</h3>}
    {showStatusAndTools && <dl className="report-metadata">
      <div><dt>Completion</dt><dd>{reportCompletionLabel(document)}</dd></div>
      <div><dt>Independent review</dt><dd>{reportReviewMessage(document)}</dd></div>
    </dl>}
    {completion?.missing_work?.length > 0 && <section className="report-completion-gaps"><h4>Work still needed</h4><ResearchDocument text={completion.missing_work} /></section>}
    {document.method_status && <MethodStatusNote status={document.method_status} onOpen={onSource} />}
    {(document.context_change_notices || []).map((notice, index) => <p className={`note${notice.status === "reassessment_required" ? " warn" : ""}`} key={index}>{notice.message || (notice.status === "reassessment_required" ? "This report cites context that changed and needs reassessment." : "The saved context changed after this report was produced. Its applicability has not been reassessed.")} {notice.item_id && `${notice.item_id}: revision ${notice.previous_revision ?? "absent"} to ${notice.current_revision ?? "absent"}.`}</p>)}
    {document.report_materials_error && <p className="note warn">{document.report_materials_error}</p>}
    {boundaryError && <p className="note warn" role="status">The report's References boundary could not be verified. {boundaryError}</p>}
    {showStatusAndTools && <div className="report-utility-row">
    <NotationLookup record={document} onSource={onSource} />
    {(model || document.problem_context_ref || record.problem_context_ref || document.report_generation_id || ref?.generation_id) && <details className="research-details report-source-details" data-reading-anchor={`${readingAnchor}:source-details`}><summary>Source details</summary><dl className="report-metadata">
      {model && <div><dt>Model identity</dt><dd>{model.stable_id || model.method_id || "Selected model"}</dd></div>}
      {model && <div><dt>Model version</dt><dd>{model.version ?? "Version not recorded"}</dd></div>}
      {(document.problem_context_ref || record.problem_context_ref) && <div><dt>Problem context</dt><dd>Revision {(document.problem_context_ref || record.problem_context_ref).revision}</dd></div>}
      {(document.report_generation_id || ref?.generation_id) && <div><dt>Report generation</dt><dd className="identity-line">{document.report_generation_id || ref.generation_id}</dd></div>}
    </dl></details>}
    <details className="research-details report-tools" data-reading-anchor={`${readingAnchor}:tools`}><summary>Report tools</summary>
      <div className="btnrow report-export-actions">{showRecordSource && <SourceRef reference={ref} onOpen={onSource} label="Inspect exact report source" />}
        {portable && <><a className="source-link ui-action" data-action="save" data-ui-role="system" href={download} download><ActionIcon name="save" />Download offline HTML</a><a className="source-link ui-action" data-action="source" data-ui-role="system" href={portable} target="_blank" rel="noreferrer"><ActionIcon name="source" />Open HTML report</a></>}
        {markdown && <a className="source-link ui-action" data-action="source" data-ui-role="system" href={markdown} target="_blank" rel="noreferrer"><ActionIcon name="source" />Open retained Markdown source</a>}
      </div>
      <p className="note">{reportExportNote(portable)}</p>
    </details>
    </div>}
    {document.document_error ? <p className="error" role="alert">The retained report text could not be loaded. {document.document_error}</p> : <ResearchDocument text={content} referenceHeadingIndex={referenceBoundary?.headingIndex} renderHeading={renderHeading} renderImage={image} renderFileLink={fileLink} renderAnchor={(name, path) => reservedAnchors.has(name) && !/^document\.block\d+$/.test(path) ? <></> : <span id={anchorId(name)} className="report-anchor" tabIndex={-1} />} renderInternalLink={(href, label) => {
      const fragment = fragmentName(href.slice(1));
      return <ReportInternalLink fragment={fragment} targetId={anchorId(fragment)} label={label} />;
    }} />}
    {materials.length > 0 && <details className="research-details report-materials" data-reading-anchor={`${readingAnchor}:materials`}><summary>Sources and reproducibility</summary>{materials.map((artifact, index) => {
      const printable = printableReportMaterial(portable, artifact, materials, primary.artifact_id);
      const standalone = standaloneReportMaterial(portable, artifact, materials);
      const label = artifact.label || artifact.title || artifact.authored_path || artifact.path || "Supporting document";
      return <div className="report-material-actions" key={index}>{verifiedMaterial(artifact) ? readableMaterial(artifact) ? <ReportMaterialLink material={artifact} path={materialBase(artifact)} materials={materials} label={label} sourceAction notationRecord={document} onSource={onSource} /> : <a className="source-link ui-action" data-ui-role="system" href={artifact.artifact_url} target="_blank" rel="noreferrer"><ActionIcon name="source" />{label}</a> : <p className="note warn">{label}: {artifact.source_error || "The retained file is unavailable."}</p>}
        {printable && <a className="source-link ui-action" data-ui-role="system" href={printable} target="_blank" rel="noreferrer" aria-label={`Open HTML edition with ${label}`} title={`Open HTML edition with ${label}`}><ActionIcon name="source" />HTML edition</a>}
        {standalone && <a className="source-link ui-action" data-ui-role="system" href={standalone} download={(artifact.authored_path || artifact.path || "appendix.html").split(/[\\/]/).at(-1).replace(/\.html?$/i, ".shareable.html")} aria-label={`Download standalone ${label}`}><ActionIcon name="save" />Download standalone HTML</a>}
      </div>;
    })}</details>}
  </article>;
  return fragment ? <ReportFragmentTarget fragment={fragment} generationId={ref?.generation_id || document.report_generation_id} unavailable={Boolean(document.document_error)}>{article}</ReportFragmentTarget> : article;
}

export function ReportSupportingDocuments({ documents = [], onSource, embedded = false }) {
  const reader = useReadingHost();
  if (!documents.length) return embedded ? null : <p className="note">Retained model, justification, and numerical sources appear here when assembled into the report.</p>;
  const identities = new Set();
  const listed = documents.filter((document) => {
    // Different versions and artifact renditions remain separate. A title or
    // body resemblance cannot establish that two entries share an exact source.
    if (!hasExactRef(document.generation_ref) && !(usableArtifactUrl(document.primary_artifact_url) && document.primary_artifact_sha256)) return true;
    const identity = readingDocumentKey({}, "report-supporting-source", [document.kind, document.generation_ref,
      document.primary_artifact_kind, document.primary_artifact_url, document.primary_artifact_sha256]);
    if (identities.has(identity)) return false;
    identities.add(identity); return true;
  });
  const toolbar = <div className="reading-toolbar">{listed.map((document, index) => {
      const title = researchDocumentTitle(document) || humanLabel(document.kind || "Research account");
      const content = researchDocumentContent(document);
      const contentSize = researchReadingSize([content, document.review_focus]);
      const size = ["pdf", "tex_source"].includes(document.primary_artifact_kind) || !(contentSize.words || contentSize.equations) ? undefined
        : researchReadingSize([title, content, document.review_focus]);
      return <ReadingDocumentButton key={readingDocumentKey({}, "report-supporting-button", [document.kind, document.generation_ref, document.primary_artifact_url, index])} title={title}
        size={size?.words || size?.equations ? size : undefined} onClick={(event) => {
          const frozen = structuredClone(document);
          reader.open({ title, size: size?.words || size?.equations ? size : undefined,
            key: readingDocumentKey(reader.scope, "report-supporting-document", [frozen.kind, frozen.generation_ref || frozen,
              frozen.primary_artifact_url, frozen.primary_artifact_sha256]),
            body: <ScientificDocuments documents={[frozen]} onSource={onSource} /> }, event.currentTarget);
        }} />;
    })}</div>;
  return embedded ? toolbar : <section className="report-supporting-documents"><h3>Supporting documents</h3>{toolbar}</section>;
}

function reportAccountMatches(report, account) {
  const a = report?.generation_ref, b = account?.generation_ref;
  if (!a || !b || ["branch", "phase", "run_id", "package_id"].some((key) => a[key] && b[key] && a[key] !== b[key])) return false;
  return Boolean(a.package_id && b.package_id ? a.package_id === b.package_id : a.run_id && a.run_id === b.run_id);
}

// Phase 5 Summary. The current technical report owns its status, exports,
// notation and supporting material here, once; the Report tab below keeps the
// complete text. A decision or lead account is shown only when it belongs to
// the same run or package as the report, so a stale account cannot be read as
// the conclusion of a newer report. Prose is rendered as authored.
export function ReportSummary({ documents = [], traceability = [], decision, summaries = [], methodLabel, onSource, onReadReport }) {
  const host = useReadingHost();
  const { reports, candidates, supporting } = partitionReportDocuments(documents, traceability);
  const report = reports[0] || null;
  if (!report) return null;
  const record = report.structured || report;
  const belongs = (item) => reportAccountMatches(report, item);
  const pairedDecision = belongs(decision) ? decision : null;
  const decisionAccount = pairedDecision?.conclusion || pairedDecision?.headline || null;
  const headline = typeof pairedDecision?.headline === "string" && typeof pairedDecision?.conclusion === "string"
    && pairedDecision.headline.trim() && pairedDecision.conclusion.trim() && pairedDecision.headline.trim() !== pairedDecision.conclusion.trim() ? pairedDecision.headline : null;
  const lead = summaries.find((summary) => belongs(summary) && (summary.evaluation_markdown || summary.summary_markdown)) || null;
  const leadText = lead ? lead.evaluation_markdown || lead.summary_markdown : null;
  const account = decisionAccount || leadText;
  const accountSource = decisionAccount ? pairedDecision : lead;
  const leadSize = leadText ? researchReadingSize(leadText) : null;
  const leadReader = decisionAccount && leadText && host.scope.projectId ? <ReadingDocumentButton title="Lead summary" size={leadSize} onClick={(event) => host.open({
    key: readingDocumentKey(host.scope, "report-lead-assessment", [lead.generation_ref || leadText]), title: "Lead summary", subtitle: methodLabel ? `${methodLabel} · Research Lead` : "Research Lead", size: leadSize,
    body: <><ResearchDocument text={leadText} />{lead.generation_ref && <div className="p2-reader-sources"><SourceRef reference={lead.generation_ref} onOpen={onSource} label="Lead summary source" /></div>}</> }, event.currentTarget)} /> : null;
  const sections = pairedDecision ? [
    ["Contribution", pairedDecision.fundamental_contribution],
    ["Main uncertainty", pairedDecision.principal_uncertainty],
    ["Main risk or limitation", pairedDecision.principal_risk],
    ["Unresolved differences", pairedDecision.material_disagreement?.length > 0 ? pairedDecision.material_disagreement : null],
    ["What remains to be established", pairedDecision.smallest_decisive_result],
  ].filter(([, text]) => text) : [];
  const model = report ? report.method_identity || record.method_identity : null;
  const problemContext = report ? report.problem_context_ref || record.problem_context_ref : null;
  const reportGeneration = report ? report.report_generation_id || report.generation_ref?.generation_id : null;
  const { portable, download, markdown } = reportExports(report);
  const readingAnchor = `report-summary:${report?.generation_ref?.generation_id || report?.report_generation_id || "unavailable"}`;
  const tabs = [["report", "Report"], ["evidence", "Supporting evidence"], ["reviews", "Reviews"], ["changes", "Changes"], ...(candidates.length ? [["candidates", "Retained candidates"]] : [])];
  const actions = report && (onReadReport || portable) ? <section><h3>Read the report</h3><div className="btnrow">
      {onReadReport && tabs.map(([tab, label]) => <ActionButton key={tab} action="details" onClick={() => onReadReport(tab)}>{label}</ActionButton>)}
      {portable && <><a className="source-link ui-action" data-action="save" data-ui-role="system" href={download} download><ActionIcon name="save" />Download offline HTML</a><a className="source-link ui-action" data-action="source" data-ui-role="system" href={portable} target="_blank" rel="noreferrer"><ActionIcon name="source" />Open HTML report</a></>}
    </div><p className="note">{reportExportNote(portable)}</p></section> : null;
  const supportingList = supporting.length > 0 ? <ReportSupportingDocuments documents={supporting} onSource={onSource} embedded /> : null;
  const resources = report || accountSource ? <>
    {report && hasSharedNotation(report) && <section><h3>Notation</h3><p className="note">Not sure what a symbol means? Open the notation table.</p><NotationLookup record={report} onSource={onSource} /></section>}
    <section><h3>Supporting reading</h3>
      {leadReader && <div className="p2-reading-links">{leadReader}</div>}
      {supportingList}
      <div className="p2-reader-sources">
        {markdown && <a className="source-link ui-action" data-action="source" data-ui-role="system" href={markdown} target="_blank" rel="noreferrer"><ActionIcon name="source" />Open retained Markdown source</a>}
        {report && <SourceRef reference={report.generation_ref} onOpen={onSource} label="Inspect exact report source" />}
        {accountSource?.generation_ref && <SourceRef reference={accountSource.generation_ref} onOpen={onSource} label={decisionAccount ? "Lead decision source" : "Lead summary source"} />}
      </div>
      {(model || problemContext || reportGeneration) && <details className="research-details report-source-details" data-reading-anchor={`${readingAnchor}:source-details`}><summary>Source details</summary><dl className="report-metadata">
        {model && <div><dt>Model identity</dt><dd>{model.stable_id || model.method_id || "Selected model"}</dd></div>}
        {model && <div><dt>Model version</dt><dd>{model.version ?? "Version not recorded"}</dd></div>}
        {problemContext && <div><dt>Problem context</dt><dd>Revision {problemContext.revision}</dd></div>}
        {reportGeneration && <div><dt>Report generation</dt><dd className="identity-line">{reportGeneration}</dd></div>}
      </dl></details>}
    </section>
  </> : null;
  return <section className="card phase-overview report-summary" data-card-role="summary"><div className="card-heading"><h2>Current report conclusion</h2></div><div className="body">
    <ResearchCardLayout actions={actions} resources={resources} actionsLabel="Report actions" label="Report supporting reading">
    {methodLabel && <p className="note">Model: {methodLabel}</p>}
    <ReportDeliveryStatus state={report?.delivery_state} />
    {report && <dl className="report-metadata">
      <div><dt>Completion</dt><dd>{reportCompletionLabel(report)}</dd></div>
      <div><dt>Independent review</dt><dd>{reportReviewMessage(report)}</dd></div>
    </dl>}
    {decisionAccount && <p className="note">Research Lead assessment</p>}
    {headline && <div className="phase-overview-headline"><ResearchDocument text={headline} /></div>}
    {account ? <ResearchDocument text={account} /> : <p className="note">No matching Lead assessment is recorded for this report.</p>}
    {sections.map(([title, text]) => <section key={title}><h3>{title}</h3><ResearchDocument text={text} /></section>)}
    </ResearchCardLayout>
  </div></section>;
}

export default function TechnicalReportReading({ documents = [], traceability = [], decision, onSource, onDiscussSection, initialTab, selectedTab, onTabChange }) {
  const { currentRef, reports, candidates, reviews, changes, supporting } = partitionReportDocuments(documents, traceability);
  const pairedDecision = reportAccountMatches(reports[0], decision) ? decision : null;
  const tabs = [
    { id: "report", label: "Report", content: reports.length ? reports.map((document, index) => <TechnicalReportDocument key={document.generation_ref?.generation_id || index} document={document} onSource={onSource} onDiscussSection={onDiscussSection} showStatusAndTools={false} />) : <EmptyState><p className="note">{noReportNote}</p></EmptyState> },
    { id: "evidence", label: "Supporting evidence", content: <><ClaimTraceability records={traceability} onSource={onSource} /><ReportSupportingDocuments documents={supporting} onSource={onSource} /></> },
    { id: "reviews", label: "Reviews", content: reviews.length ? reviews.map((document, index) => {
      const target = document.reviewed_report_ref;
      const comparable = hasExactRef(target) && hasExactRef(currentRef);
      const earlier = comparable && !sameRef(target, currentRef);
      return <section key={`${document.kind}:${index}`} className="report-review"><p className={`note${earlier ? " warn" : ""}`}>{!hasExactRef(target) ? "The report version assessed by this review is not identified in the available record." : !hasExactRef(currentRef) ? "The current report is unavailable, so this review cannot be compared with it. Its assessed version is linked below." : earlier ? "This assessment concerns an earlier report version. It does not review the current version." : "This assessment concerns the current report version."}</p><SourceRef reference={target} onOpen={onSource} label="Exact report assessed by this review" /><ScientificDocuments documents={[document]} onSource={onSource} /></section>;
    }) : <p className="note">No independent report review has been retained yet.</p> },
    { id: "changes", label: "Changes", content: <>{pairedDecision?.what_changed && <section className="scientific-block"><h3>What changed</h3><ResearchDocument text={pairedDecision.what_changed} /><SourceRef reference={{ ...pairedDecision.generation_ref, entry_pointer: "/what_changed" }} onOpen={onSource} label="Change account source" /></section>}{(changes.length > 0 || !pairedDecision?.what_changed) && <ScientificDocuments documents={changes} onSource={onSource} empty="No change account is recorded for this report." />}</> },
  ];
  if (candidates.length) tabs.push({ id: "candidates", label: "Retained candidates", content: <><p className="note">These retained report candidates have their own exact sources. The canonical current technical report appears in the Report tab.</p>{candidates.map((document, index) => <TechnicalReportDocument key={document.generation_ref?.generation_id || index} document={document} onSource={onSource} />)}</> });
  return <section className="card technical-report-reader" data-card-role="research" data-reading-anchor="report-reading" tabIndex={-1}><PhaseTabs heading="Technical report and reviews" label="Report detail" initialTab={initialTab} selectedTab={selectedTab} onTabChange={onTabChange} tabs={tabs} /></section>;
}
