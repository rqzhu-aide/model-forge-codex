import React, { useEffect, useId, useRef, useState } from "react";
import { humanLabel, scoped } from "../research";
import { citationLinks, filterLiterature } from "../researchContent";
import { assessmentKey, entryIdentity, groupPaperSources, resolveLandscapeEntry } from "../literatureLandscape";
import FrameworkLandscape, { ScientificReviewFindings } from "./FrameworkLandscape";
import { Dialog, MathText, ResearchDocument, SourceRef } from "./Shared";
import { hasConciseP1Account } from "../phaseOneReader";
import { ActionButton, ActionIcon } from "./Visuals";
import { landscapeRecords } from "../literatureLandscape";
import { captureReadingPosition, restoreReadingPosition } from "../readingPosition";
import { CitedResearchDocument, LiteratureCitation } from "./LiteratureCitation";
import { availableFocusTarget } from "../dialogFocus";
import { phaseInputStickyOffset } from "../phaseInputNavigation";

const count = (value) => Array.isArray(value) ? value.length : Number.isFinite(value) ? value : null;
export const perspective = (record) => ({ research_lead: "Research Lead", theorist: "Theorist", data_analyst: "Data Analyst" }[record.role] || { lead: "Research Lead", theory: "Theorist", empirical: "Data Analyst" }[record.family?.split(".").pop()?.split("_")[0]] || "Research assessment");
const assessmentNote = (card) => card?.assessment_predates_source_revision ? "This assessment predates the latest source revision and needs to be read against the updated reference." : card?.assessment_basis_unverified ? "The source revision used for this assessment could not be verified." : null;
const discoveryRoles = ["research_lead", "theorist", "data_analyst"];
const updateDate = (record) => /^\d{4}-\d{2}-\d{2}(?:T|$)/.test(record?.published_at || "") ? record.published_at.slice(0, 10) : null;
const sourceMatches = (source, identity) => Boolean(source && [source.source_id, ...(source.source_ids || []), ...(source.source_aliases || [])].includes(identity));

function focusSelectedPaper(target) {
  if (!availableFocusTarget(target)) return;
  const reader = target.closest('[data-reader-ready="true"]');
  const offset = reader ? phaseInputStickyOffset(reader) : 16;
  window.scrollTo({ top: Math.max(0, window.scrollY + target.getBoundingClientRect().top - offset), behavior: "instant" });
  target.focus({ preventScroll: true });
}

export function focusCitationReturn(root, anchor, fallbackSelector) {
  const target = [...root.querySelectorAll("[data-reading-anchor]")].find((item) => item.getAttribute("data-reading-anchor") === anchor && availableFocusTarget(item))
    || [...root.querySelectorAll(fallbackSelector)].find(availableFocusTarget);
  if (!target) return null;
  if (/^H[1-6]$/.test(target.tagName) && !target.hasAttribute("tabindex")) target.tabIndex = -1;
  target.focus({ preventScroll: true });
  return target;
}

export function literatureCoverageGroups(collections = []) {
  const records = scoped(collections, "trunk", "P1");
  const current = records.filter((record) => record.is_current_package === true);
  const history = new Map();
  for (const [index, record] of records.entries()) {
    if (record.is_current_package === true) continue;
    const key = record.package_id || record.generation_ref?.package_id || record.generation_ref?.run_id || `unassociated.${index}`;
    if (!history.has(key)) history.set(key, { key, collections: [], associationKnown: record.is_current_package === false });
    history.get(key).collections.push(record);
  }
  return { current, history: [...history.values()] };
}

function SearchScope({ collection, role, onSource }) {
  return <section className="scientific-passage literature-search-scope" data-search-role={role || collection.role}>
    <h4>{perspective(collection)} · search scope</h4>
    {collection.search_scope_markdown || collection.search_scope ? <ResearchDocument text={collection.search_scope_markdown || collection.search_scope} /> : <p className="note">The member's search scope is unavailable in this record.</p>}
    {collection.coverage_limits?.length > 0 && <><h5>Search limits</h5><ResearchDocument text={collection.coverage_limits} /></>}
    {collection.data_profiles?.length > 0 && <details className="research-details"><summary>Recorded descriptive data profiles</summary><ResearchDocument text={collection.data_profiles} /></details>}
    <SourceRef reference={collection.generation_ref} onOpen={onSource} label="Member search record" />
  </section>;
}

export function LiteratureCoverage({ collections = [], onSource }) {
  const { current, history } = literatureCoverageGroups(collections);
  const dates = [...new Set(current.map(updateDate).filter(Boolean))];
  return <>
    {current.length > 0 && <section className="literature-current-search" data-coverage-update="current"><h3>This literature update</h3>
      <p className="note">{dates.length === 1 ? `Published ${dates[0]}.` : "The publication date is unavailable or inconsistent in these records."} These scopes describe this update's searches; Papers retains the cumulative library.</p>
      {discoveryRoles.map((role) => { const collection = current.find((item) => item.role === role); return collection ? <SearchScope key={role} collection={collection} onSource={onSource} /> : <section className="scientific-passage" key={role}><h4>{perspective({ role })} · search scope</h4><p className="note">This member's collection is unavailable in the current package.</p></section>; })}
    </section>}
    {!current.length && history.length > 0 && <p className="note">No search collections are identified with the current package. Recorded scopes remain below with their available dates and source associations.</p>}
    {history.length > 0 && <details className="research-details literature-search-history" data-card-role="history"><summary>Earlier and unassociated search scopes ({history.length} {history.length === 1 ? "update" : "updates"})</summary>
      {history.map((group) => { const groupDates = [...new Set(group.collections.map(updateDate).filter(Boolean))]; return <details className="research-details" key={group.key} data-coverage-update={group.associationKnown ? "earlier" : "unverified"}><summary>{group.associationKnown ? "Earlier literature update" : "Update association unverified"} · {groupDates.length === 1 ? groupDates[0] : "publication date unavailable"}</summary>
        {!group.associationKnown && <p className="note">These records do not establish whether this search belongs to the current package.</p>}
        {group.collections.map((collection, index) => <SearchScope key={`${collection.role}:${index}`} collection={collection} onSource={onSource} />)}
      </details>; })}
    </details>}
  </>;
}

export function PaperAssessment({ card, review, onSource }) {
  const concise = hasConciseP1Account(card);
  const explanation = <>{(card.explanation_markdown || card.innovation) && <><h4>Contribution, theory and computation</h4><ResearchDocument text={card.explanation_markdown || card.innovation} /></>}{card.relevance_markdown && <><h4>Relevance to this setting</h4><ResearchDocument text={card.relevance_markdown} /></>}{(card.limitations_markdown || card.evaluation) && <><h4>Strengths and limitations</h4><ResearchDocument text={card.limitations_markdown || card.evaluation} /></>}</>;
  return <div className="literature-assessment">
    {card.lead_revision && <div className="paper-revision"><p className="note">Originally authored by {perspective(card)} · Revised by Research Lead.</p><details className="research-details"><summary>Reason and source evidence for this revision</summary><ResearchDocument text={card.lead_revision.correction?.reason_markdown} />{card.lead_revision.correction?.evidence_locations?.length > 0 && <ResearchDocument text={card.lead_revision.correction.evidence_locations} />}<SourceRef reference={card.lead_revision.generation_ref} onOpen={onSource ? (reference) => onSource({ ...reference, entry_pointer: card.lead_revision.entry_pointer }) : undefined} label="Lead correction record" /></details></div>}
    {assessmentNote(card) && <p className="note warn">{assessmentNote(card)}</p>}
    {card.from_earlier_run && <p className="note">Recorded in an earlier literature update.</p>}
    {concise ? explanation : <details className="research-details" data-reading-anchor={`legacy-assessment:${card.entry_sha256 || card.entry_id || card.card_id}`}><summary>Read the earlier member assessment</summary>{explanation}</details>}
    <details className="research-details" data-reading-anchor={`paper-math:${card.entry_sha256 || card.entry_id || card.card_id}`}><summary>Full mathematics and reading basis</summary>{card.reading_extent && <p className="note">Reading basis: {card.reading_extent}</p>}{(card.formulation_markdown || card.definition) && <ResearchDocument text={card.formulation_markdown || card.definition} />}</details>
    <ScientificReviewFindings review={review} card={card} />
    {card.evidence_locations?.length > 0 && <details className="research-details" data-reading-anchor={`assessment-evidence:${card.entry_sha256 || card.entry_id || card.card_id}`}><summary>Evidence locations</summary><ResearchDocument text={card.evidence_locations} /></details>}
    <SourceRef reference={card.generation_ref} onOpen={onSource ? (reference) => onSource({ ...reference, entry_pointer: card.entry_pointer, card_id: card.entry_pointer ? undefined : card.card_id }) : undefined} label="Original member record" />
  </div>;
}

export function SelectedPaper({ source, review, initialSelection, focusRef, onSource, onSelection, readingId }) {
  const assessments = source.cards || (source.card ? [source.card] : []); const [member, setMember] = useState(initialSelection?.assessmentKey || ""); const id = useId();
  const resolvedMember = initialSelection?.assessmentKey;
  useEffect(() => { if (resolvedMember) setMember(resolvedMember); }, [resolvedMember]);
  const selected = assessments.find((card, i) => assessmentKey(card, i) === (resolvedMember || member))
    || assessments.find((card) => card.role === initialSelection?.exactCard?.role) || assessments[0];
  const referencedHistory = selected && assessmentKey(selected) === initialSelection?.assessmentKey ? initialSelection.historyIndex : null;
  const exact = initialSelection?.exactCard || (referencedHistory != null ? selected?.assessment_history?.[referencedHistory] : selected);
  const bibliography = exact?.source || source;
  const links = citationLinks(bibliography);
  return <article className="literature-entry selected-paper" ref={focusRef} tabIndex={-1} data-reading-anchor={`paper:${readingId || source.source_id}`} aria-label={`Selected paper: ${bibliography.title || "Untitled source"}`}><div className="section-heading"><h3>{bibliography.title || "Untitled source"}</h3>{source.source_status && source.source_status !== "active" && <span className={`pill ${["withdrawn", "retracted"].includes(source.source_status) ? "fail" : "warn"}`}>{humanLabel(source.source_status)}</span>}</div>
    <p className="literature-citation">{[bibliography.authors?.join(", "), bibliography.year, bibliography.venue].filter(Boolean).join(" · ")}</p>
    {source.status_reason && <p className="note warn">{source.status_reason}</p>}
    {source.landscape_reason && <p className="note">{humanLabel(source.landscape_status)}: {source.landscape_reason}</p>}
    <div className="btnrow">{links.map((link) => <a key={link.href} className="source-link ui-action" data-action="source" data-ui-role="system" href={link.href} target="_blank" rel="noreferrer"><ActionIcon name="source" />{link.label}</a>)}</div>
    {assessments.length > 1 ? <div className="field member-selector"><label htmlFor={`${id}-member`}>Member assessment</label><select id={`${id}-member`} value={assessmentKey(selected, 0)} onChange={(event) => { setMember(event.target.value); const card = assessments.find((item, i) => assessmentKey(item, i) === event.target.value); if (card) onSelection?.({ sourceId: source.source_id, reference: entryIdentity(card), memberKey: event.target.value }); }}>{assessments.map((card, i) => <option key={assessmentKey(card, i)} value={assessmentKey(card, i)}>{perspective(card)}{card.lead_revision ? " · Lead revised" : ""}</option>)}</select></div> : selected && <p className="note">{perspective(selected)}</p>}
    {(initialSelection?.exactCard || referencedHistory != null) && <div className="exact-assessment-note"><p className="note">Showing {perspective(exact)}'s exact assessment used by this literature finding.</p>{onSelection && selected && <ActionButton action="details" variant="link" onClick={() => onSelection({ sourceId: source.source_id, reference: entryIdentity(selected), memberKey: assessmentKey(selected) })}>Read current member assessment</ActionButton>}</div>}
    {exact ? <PaperAssessment card={exact} review={review} onSource={onSource} /> : <p className="note">Bibliographic record retained; no member assessment is linked to this source.</p>}
    {(source.search_provenance?.length > 0 || selected?.assessment_history?.length > 0) && <details className="research-details"><summary>Original submissions, revision history and search provenance</summary>{source.search_provenance?.map((search, i) => <p className="note" key={i}>{[search.search_source, search.query, search.searched_at?.slice(0, 10)].filter(Boolean).join(" · ")}</p>)}{selected?.assessment_history?.map((card, i) => <details key={i} className="research-details"><summary>{perspective(card)} · {card.lead_revision ? "earlier lead revision" : "original submission"}</summary><PaperAssessment card={card} review={review} onSource={onSource} /></details>)}</details>}
  </article>;
}

const literatureTabs = [["setting", "Setting"], ["frameworks", "Frameworks"], ["papers", "Papers"], ["coverage", "Coverage"]];

export function LiteratureTabs({ id, selected, onSelect }) {
  const move = (event, index) => {
    const next = event.key === "ArrowRight" ? (index + 1) % literatureTabs.length : event.key === "ArrowLeft" ? (index + literatureTabs.length - 1) % literatureTabs.length : event.key === "Home" ? 0 : event.key === "End" ? literatureTabs.length - 1 : null;
    if (next == null) return;
    event.preventDefault(); onSelect(literatureTabs[next][0]); event.currentTarget.parentElement.querySelectorAll('[role="tab"]')[next]?.focus();
  };
  return <div className="phase-reader-tabs p1-reader-tabs" role="tablist" aria-label="Literature sections">{literatureTabs.map(([key, label], index) => <button type="button" key={key} id={`${id}-tab-${key}`} role="tab" aria-selected={selected === key} aria-controls={`${id}-panel-${key}`} tabIndex={selected === key ? 0 : -1} onClick={() => onSelect(key)} onKeyDown={(event) => move(event, index)}>{label}</button>)}</div>;
}

export function MainFindings({ basis, onSource, onOpenCitation, embedded = false, children, sources = [], onOpenEvidence }) {
  const id = useId(); const landscape = basis?.landscape || {}; const records = landscapeRecords(landscape);
  const approachScope = basis?.generation_ref?.generation_id || basis?.generation_ref?.package_id || basis?.generation_ref?.run_id || "unpublished";
  const selected = (landscape.overview_item_ids || []).map((key) => records.find((item) => item.id === key)).filter(Boolean);
  const Heading = embedded ? "h3" : "h2";
  const concise = hasConciseP1Account(basis);
  const cited = (text, section) => <CitedResearchDocument {...{ basis, onOpenCitation, text, section }} />;
  return <section className={embedded ? "historical-findings" : "card literature-overview-card"} data-card-role="summary" data-reading-anchor={embedded ? `findings:${basis?.generation_ref?.generation_id}` : "main-findings"} aria-labelledby={`${id}-overview`}>
    <div className={embedded ? "section-heading" : "card-heading"}><Heading id={`${id}-overview`}>Main Findings</Heading>{basis && <SourceRef reference={basis.generation_ref} onOpen={onSource} label="Research basis source" />}</div><div className={embedded ? undefined : "body"}>
      {landscape.summary_markdown ? concise || embedded ? cited(landscape.summary_markdown, "summary") : <details className="research-details" data-reading-anchor="earlier-synthesis"><summary>Read the earlier literature synthesis</summary>{cited(landscape.summary_markdown, "summary")}</details> : <p className="note">The team's literature findings will appear here after publication.</p>}
      {selected.length > 0 && <section className="scientific-passage"><h3>Relevant approaches</h3>{selected.map(({ id: itemId, record }) => <article key={`${approachScope}:${itemId}`} className={`overview-object relevance-${record.project_relevance || "unspecified"}`} data-reading-anchor={`approach:${approachScope}:${itemId}`}>
        <details className="overview-approach" data-reading-anchor={`approach-account:${approachScope}:${itemId}`}>
          <summary><h4>{record.title}{record.project_relevance && <span className="relevance-label">{({ direct: "Closely related", conditional: "Conditional fit", background: "Background" })[record.project_relevance]}</span>}</h4></summary>
        {concise && <>{record.explanation_markdown && cited(record.explanation_markdown, `${itemId}:explanation`)}{record.relevance_reason_markdown && cited(record.relevance_reason_markdown, `${itemId}:fit`)}</>}
        <details className="research-details" data-reading-anchor={`approach-detail:${approachScope}:${itemId}`}><summary>{concise ? "Mathematics, assumptions and evidence" : "Read the earlier mathematical account"}</summary>
          {cited(record.formulation_markdown, `${itemId}:formulation`)}{!concise && <>{cited(record.explanation_markdown, `${itemId}:explanation`)}{cited(record.relevance_reason_markdown, `${itemId}:fit`)}</>}
          {record.assumptions_markdown && <><h4>Assumptions</h4>{cited(record.assumptions_markdown, `${itemId}:assumptions`)}</>}
          {record.limitations?.length > 0 && cited(record.limitations, `${itemId}:limits`)}
          {(record.entry_refs || []).map((reference, index) => { const match = resolveLandscapeEntry(sources, reference); const citation = basis?.citations?.find(entry => Object.entries(reference).every(([key,value]) => entry.entry_ref?.[key] === value)); const anchor = `approach-evidence:${basis?.generation_ref?.generation_id}:${itemId}:${index}`; return citation ? <LiteratureCitation key={index} citation={citation} label={citation.bibliography?.title || "Supporting paper"} anchor={anchor} onOpen={(entry, origin) => onOpenCitation?.(entry, { ...origin, basis })} /> : match && onOpenEvidence ? <ActionButton key={index} action="source" data-reading-anchor={anchor} onClick={() => onOpenEvidence(match, { id: itemId, record, anchor })}>{match.source.title || "Supporting assessment"}</ActionButton> : <p key={index} className="note">Exact supporting assessment unavailable here. Inspect the complete source.</p>; })}
        </details>
        </details>
        {record.support_status && record.support_status !== "source_supported" && <p className="note overview-support">Source support: {humanLabel(record.support_status)}.</p>}
      </article>)}</section>}
      {landscape.common_assumptions?.length > 0 && <details className="research-details" data-reading-anchor="common-assumptions"><summary>Common assumptions and project fit</summary>{landscape.common_assumptions.map((item) => <article className="overview-assumption" key={item.assumption_id}>
        <h4>{item.title}</h4><CitedResearchDocument basis={basis} onOpenCitation={onOpenCitation} text={item.statement_markdown} section={`${item.assumption_id}:statement`} />
        {item.landscape_item_ids?.length > 0 && <p className="note">Used by: {item.landscape_item_ids.map((key) => records.find((entry) => entry.id === key)?.record.title || "Unavailable formulation").join(", ")}</p>}
        <CitedResearchDocument basis={basis} onOpenCitation={onOpenCitation} text={item.project_fit_markdown} section={`${item.assumption_id}:fit`} />
        <div className="assumption-citations">{item.citation_ids?.map((sourceId) => { const citation = basis?.citations?.find((entry) => entry.source_id === sourceId); const source = citation?.bibliography; return <LiteratureCitation key={sourceId} citation={citation} label={source ? `${source.authors?.[0] || source.title}, ${source.year || "date unavailable"}` : sourceId} anchor={`citation:${basis?.generation_ref?.generation_id}:${item.assumption_id}:${sourceId}`} onOpen={(entry, origin) => onOpenCitation?.(entry, { ...origin, basis })} />; })}</div>
      </article>)}</details>}
      {basis && !Object.hasOwn(landscape, "overview_item_ids") && <p className="note">This earlier account has no authored overview selection or shared-assumption summary. Its original mathematical records remain available below.</p>}
      {basis?.coverage_limits?.length > 0 && <details className="research-details" data-reading-anchor="coverage-limits"><summary>Review scope and limits</summary>{cited(basis.coverage_limits, "coverage-limits")}</details>}
      {children}
    </div>
  </section>;
}

export function LiteratureHistory({ collections = [], coverage = [], bases = [], libraries = [], cards = [], syntheses = [], displayedBasis, onSource }) {
  const [citation, setCitation] = useState(null); const exactFocus = useRef(null); const returnTarget = useRef(null); const historyRoot = useRef(null);
  const [returnCount, setReturnCount] = useState(0);
  const openCitation = (entry, origin) => { returnTarget.current = { anchor: origin.anchor, position: captureReadingPosition(historyRoot.current) }; setCitation({ ...entry, basis: origin.basis }); };
  useEffect(() => { if (citation) focusSelectedPaper(exactFocus.current); }, [citation]);
  useEffect(() => {
    if (!returnCount || !returnTarget.current || !historyRoot.current) return;
    return restoreReadingPosition(historyRoot.current, returnTarget.current.position, false, (container) => {
      focusCitationReturn(container, returnTarget.current.anchor, ".historical-findings h3");
    });
  }, [returnCount]);
  const close = () => { setCitation(null); setReturnCount((value) => value + 1); };
  const library = scoped(libraries, "trunk", "P1")[0]; const sources = library?.sources || [];
  const unlinked = cards.filter((card) => !sources.some((source) => source.source_id === card.subject_ref || source.cards?.some((item) => item.card_id === card.card_id)));
  const recordCount = Number.isInteger(library?.total_sources) ? library.total_sources : Array.isArray(library?.sources) ? sources.length : null;
  const assessmentCount = Array.isArray(library?.sources) && sources.every((source) => Array.isArray(source.cards) || source.card) ? sources.reduce((sum, source) => sum + (source.cards?.length ?? 1), 0) : null;
  const latestChanges = library?.changes ? [["added", "new"], ["updated", "updated"], ["rediscovered", "found again"]].filter(([key]) => count(library.changes[key]) != null).map(([key, label]) => `${count(library.changes[key])} ${label}`).join(" · ") : "";
  return <div className="literature-history-content" ref={historyRoot}>
    <details className="research-details" data-reading-anchor="literature-history"><summary>Literature accounts, search scopes and review</summary>
      <LiteratureCoverage {...{ collections, onSource }} />
      <details className="research-details literature-library-counts"><summary>Cumulative library and update counts</summary><div className="literature-overview">{recordCount != null ? <><dl className="literature-statistics"><div className="literature-statistic"><dt className="literature-count-label">Accepted source {recordCount === 1 ? "record" : "records"}</dt><dd className="literature-count-value">{recordCount}</dd></div>{assessmentCount != null && <div className="literature-statistic"><dt className="literature-count-label">Current linked member {assessmentCount === 1 ? "assessment" : "assessments"}</dt><dd className="literature-count-value">{assessmentCount}</dd></div>}</dl><p className="note">Published source records across Phase 1 updates. The paper selector groups verified equivalent publication links. Assessments count the latest linked account by each member for each source.</p></> : <p className="note">A record count is not available until a published literature library can be loaded.</p>}{latestChanges && <p className="note">Latest update: {latestChanges}</p>}</div></details>
      {scoped(coverage, "trunk", "P1").map((record, i) => <div key={i}><ResearchDocument text={record.body_md || record.structured || record} /><SourceRef reference={record.generation_ref} onOpen={onSource} /></div>)}
      {unlinked.length > 0 && <details className="research-details"><summary>Additional member records ({unlinked.length})</summary>{unlinked.map((card, i) => <details key={card.card_id || i}><summary>{card.title || "Paper assessment"} · {perspective(card)}</summary><PaperAssessment card={card} onSource={onSource} /></details>)}</details>}
      {scoped(syntheses, "trunk", "P1").map((record, i) => <details className="research-details" key={i}><summary>Earlier literature synthesis</summary><ResearchDocument text={record.summary_markdown || record.body_md || record.structured || record} /><SourceRef reference={record.generation_ref} onOpen={onSource} /></details>)}
      {displayedBasis?.scientific_review && <details className="research-details"><summary>Current account: review</summary><ResearchDocument text={displayedBasis.scientific_review} /></details>}
      {scoped(bases, "trunk", "P1").filter(record => !displayedBasis?.generation_ref || record.generation_ref?.generation_id !== displayedBasis.generation_ref.generation_id || record.generation_ref?.package_id !== displayedBasis.generation_ref.package_id).map((record, i) => <details className="research-details" key={record.generation_ref?.generation_id || i} data-reading-anchor={`basis-history:${record.generation_ref?.generation_id}`}><summary>Earlier literature account · {(record.published_at || "date unavailable").slice(0, 10)}</summary>
        <MainFindings embedded basis={record} {...{ onSource, onOpenCitation: openCitation }} />
        {record.scientific_review && <><h4>What the Lead checked</h4><ResearchDocument text={record.scientific_review.scope_markdown} /><ResearchDocument text={record.scientific_review.limitations} /></>}
      </details>)}
      {citation && <div><ActionButton action="details" onClick={close}>Back to literature account</ActionButton><SelectedPaper source={{ source_id: citation.canonical_source_id, ...citation.bibliography, cards: [citation.card] }} initialSelection={{ exactCard: citation.card }} focusRef={exactFocus} review={citation.basis?.scientific_review} onSource={onSource} /></div>}
      {scoped(libraries, "trunk", "P1")[0]?.generation_ref && <SourceRef reference={scoped(libraries, "trunk", "P1")[0].generation_ref} onOpen={onSource} label="Complete library source" />}
    </details>
  </div>;
}

export default function LiteratureWorkspace({ libraries = [], basis, bases = [], setting, decisions, onSource, reading = {}, onReadingChange, progress }) {
  const [query, setQuery] = useState(reading.query || ""); const [topicId, setTopicId] = useState(reading.topicId || ""); const [paperId, setPaperId] = useState(reading.paperId || ""); const id = useId();
  const [entrySelection, setEntrySelection] = useState(reading.entrySelection || null); const [selectionCount, setSelectionCount] = useState(0); const paperFocus = useRef(null); const root = useRef(null);
  const [frameworkId, setFrameworkId] = useState(reading.frameworkId || ""); const [origin, setOrigin] = useState(reading.origin || null); const [returnCount, setReturnCount] = useState(0);
  const [frameworkExpanded, setFrameworkExpanded] = useState(reading.tab === "frameworks"); const frameworkFocus = useRef(null);
  const [notation, setNotation] = useState(null); const notationRoot = useRef(null);
  const readingChange = useRef(onReadingChange); readingChange.current = onReadingChange;
  useEffect(() => { readingChange.current?.({ query, topicId, paperId, entrySelection, frameworkId, origin }); }, [query, topicId, paperId, entrySelection, frameworkId, origin]);
  useEffect(() => { if (selectionCount) focusSelectedPaper(paperFocus.current); }, [selectionCount]);
  useEffect(() => {
    if (!notation?.restore) return;
    const frame = requestAnimationFrame(() => {
      const container = notationRoot.current; const modal = container?.closest('.modal-body');
      if (modal) modal.scrollTop = notation.restore.scrollTop || 0;
      if (container) focusCitationReturn(container, notation.restore.anchor, "table");
    });
    return () => cancelAnimationFrame(frame);
  }, [notation]);
  useEffect(() => {
    if (!returnCount || !origin || !root.current) return;
    if (origin.notation) {
      const original = [basis, ...bases].find(record => record?.generation_ref?.generation_id === origin.notation.basisId);
      setNotation({ basis: original, position: origin.position, restore: { ...origin.notation, anchor: origin.anchor } });
      return restoreReadingPosition(root.current, origin.position, false);
    }
    return restoreReadingPosition(root.current, origin.position, false, (container) => {
      if (origin.anchor) {
        const setting = [":setting:", ":component:", ":goal:"].some((part) => origin.anchor.includes(part));
        focusCitationReturn(container, origin.anchor, `[data-reading-anchor="${setting ? "research-setting" : "main-findings"}"] h2`);
      } else if (availableFocusTarget(frameworkFocus.current)) frameworkFocus.current.focus({ preventScroll: true });
    });
  }, [returnCount]);
  const library = scoped(libraries, "trunk", "P1")[0]; const sources = groupPaperSources(library?.sources || []); const topics = basis?.landscape?.topics || [];
  const topic = topics.find((item) => item.topic_id === topicId);
  const topicSources = topic ? sources.filter((source) => [source.source_id, ...(source.source_ids || []), ...(source.source_aliases || [])].some((value) => topic.source_ids?.includes(value))) : sources;
  const matching = filterLiterature(topicSources, query); const selected = matching.find((source) => sourceMatches(source, paperId));
  const citationBasis = entrySelection?.citationBasisId && [basis, ...bases].find((record) => record?.generation_ref?.generation_id === entrySelection.citationBasisId);
  const citation = citationBasis?.citations?.find((item) => (item.canonical_source_id === entrySelection.sourceId || sourceMatches(selected, item.canonical_source_id) && sourceMatches(selected, entrySelection.sourceId)) && Object.entries(entrySelection.reference).every(([key, value]) => item.entry_ref?.[key] === value));
  const resolvedEntry = entrySelection && sourceMatches(selected, entrySelection.sourceId) ? resolveLandscapeEntry([selected], entrySelection.reference) : null;
  const currentMember = citation && resolveLandscapeEntry(selected ? [selected] : [], citation.entry_ref)?.currentCard;
  const citationSelection = entrySelection?.citationBasisId || origin?.kind === "citation" && !entrySelection?.memberKey;
  const selectedEntry = citationSelection
    ? selected && citation?.status === "available" ? { assessmentKey: assessmentKey(currentMember || citation.card), exactCard: citation.card } : null
    : resolvedEntry;
  const unavailable = Boolean(entrySelection && !selectedEntry);
  const clearPaper = () => { setPaperId(""); setEntrySelection(null); setOrigin(null); };
  const openEvidence = (match, selection) => {
    setQuery(""); setTopicId(""); setPaperId(match.source.source_id); setEntrySelection({ sourceId: match.source.source_id, reference: entryIdentity(match.card) });
    setOrigin(selection ? { id: selection.id, title: selection.record.title, ...(selection.anchor ? { anchor: selection.anchor } : {}), position: captureReadingPosition(root.current) } : null); setSelectionCount((value) => value + 1);
  };
  const openCitation = (entry, invocation) => {
    const fromNotation = invocation.notation;
    setOrigin({ kind: "citation", id: entry.source_id, title: invocation.label, anchor: invocation.anchor,
      position: fromNotation ? notation.position : captureReadingPosition(root.current),
      ...(fromNotation ? { notation: { basisId: notation.basis.generation_ref.generation_id, scrollTop: notationRoot.current?.closest('.modal-body')?.scrollTop || 0 } } : {}) });
    if (fromNotation) setNotation(null);
    setQuery(""); setTopicId(""); setPaperId(entry.canonical_source_id);
    setEntrySelection({ sourceId: entry.canonical_source_id, reference: entry.entry_ref, citationBasisId: invocation.basis?.generation_ref?.generation_id });
    setSelectionCount((value) => value + 1);
  };
  const renderDocument = (text, section) => <CitedResearchDocument {...{ text, section, basis, onOpenCitation: openCitation }} />;
  return <div className="literature-reading" ref={root}>
    {typeof setting === "function" ? setting({ renderDocument, onNotation: () => setNotation({ basis, position: captureReadingPosition(root.current) }) }) : setting}
    <MainFindings {...{ basis, onSource, sources }} onOpenCitation={openCitation} onOpenEvidence={openEvidence}>
      {basis?.landscape && <details className="research-details" data-reading-anchor="framework-map" open={frameworkExpanded} onToggle={(event) => setFrameworkExpanded(event.currentTarget.open)}><summary>Explore mathematical frameworks and relationships</summary>
        <FrameworkLandscape embedded basis={basis} sources={sources} onSource={onSource} selectedId={frameworkId} onSelect={setFrameworkId} focusRef={frameworkFocus} onEvidence={openEvidence} />
      </details>}
    </MainFindings>
    {decisions}
    {progress}
    <section className="card literature-library" data-card-role="research" data-reading-anchor="explore-papers" aria-labelledby={`${id}-library`}><div className="card-heading"><h2 id={`${id}-library`}>Explore Individual Papers</h2></div><div className="body">
      <div className="literature-controls">{topics.length > 0 && <div className="field"><label htmlFor={`${id}-topic`}>Research direction</label><select id={`${id}-topic`} value={topic?.topic_id || ""} onChange={(event) => { setTopicId(event.target.value); clearPaper(); }}><option value="">All directions</option>{topics.map((item) => <option key={item.topic_id} value={item.topic_id}>{item.title}</option>)}</select></div>}
        <div className="field"><label htmlFor={`${id}-search`}>Find a paper or research idea</label><input id={`${id}-search`} type="search" value={query} placeholder="Title, author, mathematical concept" onChange={(event) => { setQuery(event.target.value); clearPaper(); }} /></div>
      </div>
      {topic?.description_markdown && renderDocument(topic.description_markdown, `topic:${topic.topic_id}`)}
      <div className="field"><label htmlFor={`${id}-paper`}>Paper ({matching.length})</label><select id={`${id}-paper`} value={selected?.source_id || ""} onChange={(event) => { setPaperId(event.target.value); setEntrySelection(null); setOrigin(null); setSelectionCount((value) => value + 1); }} disabled={!matching.length}><option value="">{matching.length ? "Choose a paper to read" : "No matching papers"}</option>{matching.map((source) => <option key={source.source_id} value={source.source_id}>{source.title}{source.year ? ` (${source.year})` : ""}{source.source_status && source.source_status !== "active" ? ` · ${humanLabel(source.source_status)}` : ""}{source.landscape_status === "exclude" ? " · Outside current focus" : ""}</option>)}</select></div>
      {(selected || origin) && <div className="btnrow paper-reading-actions">{origin && <ActionButton action="details" variant="link" onClick={() => { if (origin.kind !== "citation" && !origin.anchor) { setFrameworkExpanded(true); setFrameworkId(origin.id); } setReturnCount((value) => value + 1); }}>Back to {origin.title}</ActionButton>}<ActionButton action="close" onClick={clearPaper}>Close paper</ActionButton></div>}
      {unavailable ? <p className="note warn" role="status">The exact referenced assessment is unavailable. Choose a paper or member to read another record.</p> : selected ? <SelectedPaper key={`${selected.source_id}:${selectionCount}`} source={selected} readingId={paperId} review={basis?.scientific_review} focusRef={paperFocus} initialSelection={selectedEntry} onSelection={setEntrySelection} onSource={onSource} /> : <p className="note">{matching.length ? "Choose a paper, or follow a citation in the findings, to read its mathematics and member assessments." : query || topic ? "No papers match this selection." : "No papers have been published yet."}</p>}
    </div></section>
    {notation && <Dialog title="Notation" onClose={() => setNotation(null)}><div ref={notationRoot}>
      {notation.basis ? <div className="table-scroll" tabIndex={0} role="region" aria-label="Mathematical components and their meaning"><table className="setting-components"><thead><tr><th scope="col">Symbol</th><th scope="col">Mathematical role</th><th scope="col">Meaning in your problem</th></tr></thead><tbody>{notation.basis.research_setting?.component_interpretations?.map((item, index) => <tr key={index}><th scope="row"><MathText latex={item.symbol_latex} display={false} /></th>{["mathematical_role_markdown", "problem_meaning_markdown"].map(field => <td key={field}><CitedResearchDocument basis={notation.basis} text={item[field]} section={`component:${index}:${field}`} onOpenCitation={(entry, invocation) => openCitation(entry, { ...invocation, notation: true })} /></td>)}</tr>)}</tbody></table></div> : <p role="status">The earlier notation source is unavailable. Close to return to your reading.</p>}
    </div></Dialog>}
  </div>;
}
