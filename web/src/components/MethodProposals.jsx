import React, { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { phaseLabel, humanLabel } from "../research";
import { MethodStatusNote, ResearchDocument, SourceRef } from "./Shared";
import { perspective } from "./LiteratureWorkspace";
import { citationLinks, collectionFields, narrativeFields } from "../researchContent";
import { inlineTokens } from "../researchMath";
import { catalogMethodForProposal, catalogOnlyMethods, catalogSelectionKey, comparisonCandidates, comparisonForProposal, hasConciseP2Account, methodAnswers, methodIdOf, methodRequests, modificationOptionsFor, orderedProposals, proposalKey, proposalSectionSource, recordedSelections, sameMethodIdentity, successorMethodForProposal, summaryForDisplay } from "../methodWorkspace";
import { methodStartingPointSource } from "../methodSeed";
import { ActionButton, ActionIcon, EmptyState } from "./Visuals";
import { phaseInputStickyOffset } from "../phaseInputNavigation";
import { NotationLookup } from "./SharedNotation";

export function proposalReviews(proposal, reviews) {
  const runId = proposal.generation_ref?.run_id;
  return reviews.filter((review) => runId && review.generation_ref?.run_id === runId).flatMap((review) =>
    (review.assessments || []).filter((assessment) => assessment.proposal_id === proposal.proposal_id).map((assessment) => ({ ...assessment, role: review.role, generation_ref: review.generation_ref,
      applicability_ref: proposalSectionSource(review, proposal.proposal_id, "assessments", "applicability_markdown") })));
}

function LeadResponses({ responses, onSource }) {
  if (!responses.length) return null;
  return <details className="research-details"><summary>Research Lead's response to your directions</summary>{responses.map((response, i) => <div key={response.generation_ref?.run_id || i}><p className="note">{response.is_current_package === false ? "Earlier run · " : ""}No additional method proposed</p><ResearchDocument text={response.reason_markdown} /><SourceRef reference={response.generation_ref} onOpen={onSource} /></div>)}</details>;
}

function exactResearchLink(record, proposals, reviews, onSource) {
  return (href, label) => {
    const run = record?.generation_ref?.run_id;
    const matches = [...proposals, ...reviews].filter((record) => run && record.generation_ref?.run_id === run
      && (record.proposal_id || record.review_id) && href === `#${record.proposal_id || record.review_id}` && record.generation_ref?.generation_id);
    return matches.length === 1 ? <SourceRef reference={matches[0].generation_ref} onOpen={onSource} label={label} /> : null;
  };
}

// Omit standalone audit citations in this overview only. Tokenizing first keeps
// code, math, publication links and references within substantive prose intact.
function overviewForDisplay(text) {
  if (typeof text !== "string") return text;
  const parts = text.split(inlineTokens);
  const audit = (part) => /^\[[^\]]+\]\(#review\.[^)]+\)$/.test(part);
  for (let i = 1; i < parts.length; i += 2) {
    if (!audit(parts[i]) || !/(?:^|[.!?][ \t]+|\n[ \t]*)$/.test(parts[i - 1])) continue;
    let end = i;
    while (audit(parts[end + 2]) && /^[ \t]*(?:[,;][ \t]*(?:and[ \t]+)?|and[ \t]+)$/.test(parts[end + 1])) end += 2;
    const after = parts[end + 1] || "";
    const closing = after.match(/^[ \t]*[.;](?:[ \t]+|(?=\r?\n|$))/) || after.match(/^\s*$/);
    if (!closing) continue;
    parts.fill("", i, end + 1);
    parts[end + 1] = after.slice(closing[0].length);
    i = end;
  }
  return parts.join("").trim();
}

function MethodComparison({ comparison, proposals, reviews = [], onSource }) {
  const excluded = comparisonCandidates(comparison, proposals, "exclude");
  // The overview is prose. Internal records remain in the selected method's
  // review details; only publication citations should act as links here.
  const renderInternalLink = (_href, label) => <span>{label}</span>;
  if (!comparison) return null;
  const overview = overviewForDisplay(comparison.overview_markdown || comparison.comparison_markdown);
  return <div className="p2-comparison" data-reading-anchor="p2-comparison">
      <p className="note">Research Lead's comparison of the proposed methods</p>
      {overview && <ResearchDocument text={overview} renderInternalLink={renderInternalLink} />}
      <NotationLookup record={comparison} onSource={onSource} label="Notation for all methods" />
      {excluded.length > 0 && <details className="research-details"><summary>Not retained in this catalog update ({excluded.length})</summary>
        {excluded.map(({ disposition, proposal }) => <div key={proposalKey(proposal)}>
          <h4>{proposal.method?.title || disposition.proposal_id} · {perspective(proposal)}</h4>
          <ResearchDocument text={disposition.rationale || disposition.rationale_markdown || disposition.reason_markdown} />
        </div>)}
      </details>}
  </div>;
}

// The dropdown is a plain form control: choosing a method only changes what the
// card displays. Activation stays with the two exploration buttons below.
export function MethodPicker({ id, describedBy, controls, proposals, methods = [], comparisons = [], value, onSelect }) {
  const current = orderedProposals(proposals.filter((proposal) => proposal.is_current_package !== false));
  const earlier = proposals.filter((proposal) => proposal.is_current_package === false);
  const catalogOnly = catalogOnlyMethods(methods, proposals);
  const option = (proposal) => {
    const label = [proposal.method.title, perspective(proposal)];
    if (proposal.method.identity?.version != null) label.push(`Version ${proposal.method.identity.version}`);
    if (comparisonForProposal(proposal, comparisons)?.disposition.status === "exclude") label.push("Excluded from this catalog update");
    if (proposal.is_current_package === false) {
      const retained = catalogMethodForProposal(proposal, methods);
      const successor = retained ? null : successorMethodForProposal(proposal, methods);
      const successorVersion = (successor?.identity || successor?.current_identity)?.version;
      label.push(retained ? `${proposal.published_at?.slice(0, 10) || "Earlier run"} · current catalog definition`
        : successor ? `Superseded${successorVersion != null ? ` by version ${successorVersion}` : ""}`
        : proposal.published_at?.slice(0, 10) || "Earlier run");
    }
    return <option key={proposalKey(proposal)} value={proposalKey(proposal)}>{label.join(" · ")}</option>;
  };
  return <div className="field method-branch-selector"><label htmlFor={id}>Choose a method</label><select id={id} value={value} onChange={(event) => onSelect(event.target.value)} aria-controls={controls} aria-describedby={describedBy}>
    {earlier.length || catalogOnly.length ? <>{current.length > 0 && <optgroup label="Current proposals">{current.map(option)}</optgroup>}{earlier.length > 0 && <optgroup label="Earlier proposals">{earlier.map(option)}</optgroup>}</> : current.map(option)}
    {catalogOnly.length > 0 && <optgroup label="Catalog definitions without a linked proposal">{catalogOnly.map((method) => {
      const identity = method.identity || method.current_identity || method.definition?.identity;
      return <option key={catalogSelectionKey(method)} value={catalogSelectionKey(method)}>{[method.title || method.name || method.method_id, identity?.version != null ? `Version ${identity.version}` : method.version != null ? `Version ${method.version}` : null, humanLabel(method.status || "Recorded"), "Catalog definition"].filter(Boolean).join(" · ")}</option>;
    })}</optgroup>}
  </select></div>;
}

// A superseded version stays readable as history and routes to the current
// version; it never offers the exploration actions as if it were current.
export function SupersededNote({ successor, onViewCurrent }) {
  const version = (successor?.identity || successor?.current_identity)?.version;
  return <div className="context-note superseded-note">
    <p>This version is kept as history. {version != null ? `The current catalog carries version ${version} of this model` : "The current catalog carries a different definition of this model"}, so this version cannot start new work.</p>
    {onViewCurrent
      ? <ActionButton action="details" variant="link" onClick={onViewCurrent}>View the current version{version != null ? ` (version ${version})` : ""}</ActionButton>
      : <p>The current version is available in the model selector.</p>}
  </div>;
}

// Prepare work for the exact current definition. Submission stays in LaunchRun.
export function ExploreActions({ catalogMethod, busy, onContinue }) {
  if (!onContinue || !catalogMethod) return null;
  if (!["active", "proposed"].includes(catalogMethod.status)) return <p className="note">This catalog definition is not active for further work.</p>;
  return <><div className="btnrow" aria-busy={busy}>
    <ActionButton action="run" uiRole="research" aria-haspopup="dialog" disabled={busy} onClick={() => onContinue(catalogMethod, "P3", { prepareRun: true })}>{`Run this Method in ${phaseLabel("P3")}`}</ActionButton>
    <ActionButton action="run" uiRole="research" aria-haspopup="dialog" disabled={busy} onClick={() => onContinue(catalogMethod, "P4", { prepareRun: true })}>{`Run this Method in ${phaseLabel("P4")}`}</ActionButton>
  </div><p className="note">Choose the work and review your instructions before starting the run.</p></>;
}

function MethodAudits({ proposal, reviews, onSource }) {
  const audits = proposalReviews(proposal, reviews);
  return <div className="method-audits">{audits.length ? audits.map((audit, i) => <div className="method-audit" key={i}>
    <p className="note">{perspective(audit)}</p>
    {audit.headline && <ResearchDocument text={audit.headline} />}
    <div className="p2-audit-content">
      <ResearchDocument text={audit.assessment_markdown} />
      {audit.findings?.map((finding, j) => <section className="audit-finding" key={finding.finding_id || j}>
        <div role="heading" aria-level={4}>{finding.title ? <ResearchDocument text={finding.title} /> : `Finding ${j + 1}`}</div>
        {finding.consequence_markdown && <><h4>Consequence and next work</h4><ResearchDocument text={finding.consequence_markdown} /></>}
        <h4>Statement under review</h4><ResearchDocument text={finding.statement_reference} />
        <h4>Reasoning</h4>
        <ResearchDocument text={finding.reasoning_markdown} />
        {finding.statement_refs?.length > 0 && <div className="p2-reader-sources">{finding.statement_refs.map((pointer, k) => <SourceRef key={pointer} reference={{ ...proposal.generation_ref, entry_pointer: pointer }} onOpen={onSource} label={`Read referenced equation or step ${k + 1}`} />)}</div>}
      </section>)}
      <div className="p2-reader-sources"><SourceRef reference={audit.generation_ref} onOpen={onSource} label="Original audit report" /></div>
    </div>
  </div>) : <p className="note">No published cross-audit is linked to this exact proposal run.</p>}</div>;
}

const methodPhases = ["P2", "P3", "P4", "P5"];

export function MethodReaderDisclosure({ name, title, modelKey, open, onToggle, children }) {
  return <details className="research-details p2-reader-disclosure" data-reading-anchor={`p2-model:${modelKey}:${name}`} open={open} onToggle={(event) => {
    if (event.currentTarget.open !== Boolean(open)) onToggle?.(event.currentTarget.open);
  }}><summary>{title}</summary><div className="p2-reader-panel">{children}</div></details>;
}

function ReaderSection({ title, author, className = "", children }) {
  return <section className={`p2-reader-section${className ? ` ${className}` : ""}`}><h3>{title}</h3>{author && <p className="note p2-section-author">{author}</p>}{children}</section>;
}

function renderSlot(slot, context) { return typeof slot === "function" ? slot(context) : slot; }

const displayedFields = new Set([...narrativeFields, ...collectionFields].map(([key]) => key).concat(["title", "label", "headline", "latex", "symbol", "severity", "state", "disposition", "status"]));
const sourceMetadataFields = new Set(["canonical_artifact", "definition_locator", "defining_components", "object_id", "assumption_id", "parameter_id", "component_id", "order", "execution_metadata"]);
// ResearchDocument renders the standard authored fields. Preserve custom
// mathematical objects explicitly as well, including nested, unknown fields.
function additionalFormulationFields(value, path = "") {
  if (Array.isArray(value)) return value.flatMap((item, index) => additionalFormulationFields(item, `${path}/${index}`));
  if (!value || typeof value !== "object") return [];
  return Object.entries(value).flatMap(([key, body]) => sourceMetadataFields.has(key) ? [] : displayedFields.has(key)
    ? additionalFormulationFields(body, `${path}/${key}`)
    : [{ path: `${path}/${key}`, body }]);
}

function CompleteFormulation({ definition }) {
  const additional = additionalFormulationFields(definition);
  return <><ResearchDocument text={definition} />{additional.length > 0 && <details className="research-details p2-original-fields"><summary>Additional original formulation fields</summary>
    {additional.map(({ path, body }) => <section key={path}><h4>{humanLabel(path.split("/").filter(Boolean).join(" · "))}</h4>
      {typeof body === "string" ? <ResearchDocument text={body} /> : <pre className="record">{JSON.stringify(body, null, 2)}</pre>}
    </section>)}
  </details>}</>;
}

// One exact selection is shared with both follow-up cards. Publication refreshes
// retain that selection and its drafts until the researcher chooses another model.
function ExploreMethod({ methods = [], cards = [], proposals = [], reviews = [], comparisons = [], comparison, literatureSources = [], projectId, attentionItems = [], researcherAnswers = [], busy, onContinue, onResolved, onSource, initialPick, initialSharedPreparation, onPreparationScopeChange, onPick, modelHistory, issues, furtherWork, progress, reading = {}, onReadingChange }) {
  const id = useId(); const [pick, setPick] = useState(initialPick || "");
  const [disclosures, setDisclosures] = useState(reading.modelDisclosures || {});
  const [savedAnswers, setSavedAnswers] = useState({});
  const readingChange = useRef(onReadingChange); readingChange.current = onReadingChange;
  const clarificationDrafts = useRef(new Map());
  const current = orderedProposals(proposals.filter((proposal) => proposal.is_current_package !== false));
  const earlier = proposals.filter((proposal) => proposal.is_current_package === false);
  const catalogOnly = catalogOnlyMethods(methods, proposals);
  const pickedProposal = proposals.find((proposal) => proposalKey(proposal) === pick);
  const pickedCatalog = catalogOnly.find((method) => catalogSelectionKey(method) === pick);
  const selected = pickedProposal || (!pickedCatalog && (current[0] || earlier[0])) || null;
  const catalogMethod = selected ? catalogMethodForProposal(selected, methods) : pickedCatalog || catalogOnly[0] || null;
  const selectedKey = selected ? proposalKey(selected) : catalogMethod ? catalogSelectionKey(catalogMethod) : "";
  // Next can name another exact proposal while P2 stays mounted. Accept that
  // context change without discarding model drafts or the prepared run scope.
  useLayoutEffect(() => {
    if (initialPick && (proposals.some((proposal) => proposalKey(proposal) === initialPick)
      || catalogOnly.some((method) => catalogSelectionKey(method) === initialPick))) setPick(initialPick);
  }, [initialPick]);
  // Publishing the first model updates the reader without replacing the shared
  // instructions already being prepared. Only an explicit choice changes them.
  const [sharedPreparation, setSharedPreparation] = useState(initialSharedPreparation ?? !selectedKey);
  const focusPreparation = useRef(false);
  useLayoutEffect(() => {
    if (!focusPreparation.current) return;
    focusPreparation.current = false;
    const root = document.getElementById?.(`${id}-models`)?.closest('[data-reader-ready="true"]');
    const settings = root?.querySelector('[data-reading-anchor="further-work"]');
    if (!settings) return;
    settings.open = true;
    const target = settings.querySelector(":scope > summary:not([hidden])") || settings;
    if (target === settings) settings.setAttribute("tabindex", "-1");
    window.scrollTo({ top: Math.max(0, window.scrollY + target.getBoundingClientRect().top - phaseInputStickyOffset(root)), behavior: "instant" });
    target.focus({ preventScroll: true });
  }, [sharedPreparation]);
  const preparationChange = useRef(onPreparationScopeChange); preparationChange.current = onPreparationScopeChange;
  useEffect(() => { preparationChange.current?.(sharedPreparation); }, [sharedPreparation]);
  const selectionChange = useRef(onPick); selectionChange.current = onPick;
  useEffect(() => {
    if (!selectedKey || selectedKey === pick) return;
    setPick(selectedKey); selectionChange.current?.(selectedKey);
  }, [selectedKey, pick]);
  const legacySelection = useRef(selectedKey);
  const legacyTab = useRef(!reading.modelDisclosures && ["assumptions", "computation", "review"].includes(reading.tab) ? reading.tab : null);
  const openSections = disclosures[selectedKey] || (selectedKey === legacySelection.current && legacyTab.current ? { [legacyTab.current]: true } : {});
  const toggleSection = (name, open) => setDisclosures((saved) => ({ ...saved, [selectedKey]: { ...openSections, [name]: open } }));
  useEffect(() => {
    if (selectedKey) readingChange.current?.({ modelDisclosures: { ...disclosures, [selectedKey]: openSections } });
  }, [disclosures, selectedKey]);
  if (!selected && !catalogMethod) {
    const context = { proposal: null, method: null, methodId: null, methodBranch: "trunk", catalogMethod: null, reviewed: null,
      requests: attentionItems, answers: researcherAnswers, phases: methodPhases, emptyState: !cards.length, sharedPreparation: true, modelHistory };
    // Keep the same sibling slots as the populated reader so first publication
    // preserves the mounted preparation form, its disclosure and its focus.
    return <><section className="card p2-landscape p2-models-card" data-card-role="research"><div className="card-heading"><h2>Proposed Methods</h2></div><div className="body">
      <MethodComparison comparison={comparison} proposals={[]} reviews={reviews} onSource={onSource} />{progress}
      {!cards.length && <EmptyState><p>Published proposals will appear here after the team completes its review.</p></EmptyState>}
    </div></section>
      {cards.length > 0 && <section className="card p2-models-card" data-card-role="research"><div className="card-heading"><h2>Select a Method to Explore</h2></div><div className="body"><CatalogRecords cards={cards} onSource={onSource} /></div></section>}
      {renderSlot(issues, context)}{renderSlot(furtherWork, context)}
    </>;
  }
  const definition = catalogMethod?.definition || {};
  const method = selected?.method || { ...definition, title: catalogMethod.title || catalogMethod.name || definition.title || catalogMethod.method_id, identity: catalogMethod.identity || catalogMethod.current_identity || definition.identity };
  const source = selected?.generation_ref || catalogMethod?.source_ref;
  const author = selected ? perspective(selected) : "Published catalog definition";
  const methodId = selected ? methodIdOf(selected) : method.identity?.stable_id || catalogMethod.method_id;
  const startingPoint = methodStartingPointSource(selected?.researcher_origin);
  const canonical = method.mathematical_definition?.canonical_definition;
  const reviewed = selected ? comparisonForProposal(selected, comparisons) : null;
  const conciseLead = Boolean(reviewed?.disposition.method_summary_markdown && hasConciseP2Account(reviewed.comparison));
  const leadInternalLink = exactResearchLink(reviewed?.comparison, proposals, reviews, onSource);
  const leadSummarySource = selected && proposalSectionSource(reviewed?.comparison, selected.proposal_id, "method_dispositions", "method_summary_markdown");
  const leadReviewField = ["rationale", "rationale_markdown", "reason_markdown"].find((field) => reviewed?.disposition[field]);
  const leadReviewSource = selected && proposalSectionSource(reviewed?.comparison, selected.proposal_id, "method_dispositions", leadReviewField);
  const successor = selected && !catalogMethod ? successorMethodForProposal(selected, methods) : null;
  const currentProposal = successor ? proposals.find((proposal) => sameMethodIdentity(proposal.method?.identity, successor.identity || successor.current_identity)) : null;
  const methodBranch = catalogMethod?.branch_id || methodId;
  const requests = methodRequests(attentionItems, methodId, methodBranch, { modelRef: method.identity });
  const answers = methodAnswers([...researcherAnswers, ...Object.values(savedAnswers)], methodId, methodBranch, { modelRef: method.identity });
  const profile = selected?.computational_profile;
  const options = selected ? modificationOptionsFor(reviewed?.comparison, selected.proposal_id) : [];
  const audits = selected ? proposalReviews(selected, reviews) : [];
  const specialists = audits.filter((audit) => ["theorist", "data_analyst"].includes(audit.role) && audit.applicability_markdown);
  const staleOutputs = (catalogMethod?.dependent_outputs || []).filter((output) => output.status && output.status !== "current");
  const choose = (key) => { if (proposals.some((proposal) => proposalKey(proposal) === key) || catalogOnly.some((method) => catalogSelectionKey(method) === key)) { setPick(key); setSharedPreparation(false); onPick?.(key); } };
  const viewCurrent = successor ? () => choose(currentProposal ? proposalKey(currentProposal) : catalogSelectionKey(successor)) : null;
  const statusNote = reviewed?.disposition.status === "retain" ? "Retained candidate" : reviewed?.disposition.status === "exclude" ? "Excluded from this catalog update" : selected ? "Proposed model" : humanLabel(catalogMethod.status || "Recorded model");
  const proposedWork = selected && <ReaderSection title="Proposed theory and experiment work" author={author}><p className="note">These are proposed steps, not completed proofs or simulations.</p><ResearchDocument text={selected.proposed_evaluation_markdown} /><div className="p2-reader-sources"><SourceRef reference={source} onOpen={onSource} label="Proposed work source" /></div></ReaderSection>;
  const modificationOptions = selected && <ReaderSection title={`The lead's modification options${options.length ? ` (${options.length})` : ""}`} author="Research Lead">
    {!reviewed ? <p className="note">No lead assessment is linked to this exact proposal run.</p>
      : !Array.isArray(reviewed.comparison.modification_options) ? <p className="note">This earlier assessment did not record separate modification options.</p>
      : options.length ? <>{options.map((option, i) => <div className="modification-option" key={option.option_id || i}>
        <h4>{option.title || `Modification option ${i + 1}`}</h4>
        {option.what_changes_markdown && <><h4>What changes mathematically</h4><ResearchDocument text={option.what_changes_markdown} /></>}
        {option.when_preferable_markdown && <><h4>When it is preferable</h4><ResearchDocument text={option.when_preferable_markdown} /></>}
        {!option.what_changes_markdown && !option.when_preferable_markdown && <p className="note">No details were recorded for this modification option.</p>}
      </div>)}<div className="p2-reader-sources"><SourceRef reference={reviewed.comparison.generation_ref} onOpen={onSource} label="Lead assessment source" /></div></>
      : <p className="note">The lead recorded no modification options for this proposal.</p>}
  </ReaderSection>;
  const context = { proposal: selected, method, methodId, methodBranch, catalogMethod, reviewed, requests, answers, projectId, phases: methodPhases, emptyState: false, sharedPreparation,
    draftStore: clarificationDrafts.current, onResolved, onAnswerSaved: (answer) => setSavedAnswers((currentAnswers) => ({ ...currentAnswers, [answer.attention_id || answer.attention.attention_id]: answer })), proposedWork, modificationOptions, modelHistory };
  const disclosure = (name, title, children) => <MethodReaderDisclosure name={name} title={title} modelKey={selectedKey} open={Boolean(openSections[name])} onToggle={(open) => toggleSection(name, open)}>{children}</MethodReaderDisclosure>;
  return <><section className="card p2-landscape p2-models-card" data-card-role="research" aria-labelledby={`${id}-landscape`}>
    <div className="card-heading"><h2 id={`${id}-landscape`}>Proposed Methods</h2></div><div className="body">
      <MethodComparison comparison={comparison} proposals={proposals} reviews={reviews} onSource={onSource} />{progress}
    </div>
  </section><section className="card p2-models-card" data-card-role="research" aria-labelledby={`${id}-models`}>
    <div className="card-heading"><h2 id={`${id}-models`}>Select a Method to Explore</h2></div><div className="body">
      <MethodPicker id={`${id}-method`} describedBy={`${id}-branch-note`} controls={`${id}-explore`} proposals={proposals} methods={methods} comparisons={comparisons} value={selectedKey} onSelect={choose} />
      <p className="note" id={`${id}-branch-note`}>Choose a method to read its exact version. Its questions and further work follow below.</p>
      {sharedPreparation && catalogMethod && <div className="btnrow"><ActionButton action="edit" uiRole="research" onClick={() => { focusPreparation.current = true; choose(selectedKey); }}>Prepare work on this method</ActionButton><span className="note">Shared proposal instructions remain below until you choose a method for this work.</span></div>}
      <div className="p2-deep-dive" id={`${id}-explore`} key={selectedKey} data-reading-anchor="p2-selected-model" tabIndex={-1}>
        <header className="p2-method-heading"><div><h3>{method.title}</h3>
          <p className="note">{selected ? `Proposed by ${author}` : author}{selected?.researcher_origin && (startingPoint ? " · From a selected model starting point" : " · From your idea")}{catalogMethod?.registered && " · Selected"}</p>
          <p className="note">{statusNote}{method.identity?.version != null && ` · Version ${method.identity.version}`}{selected?.is_current_package === false && (catalogMethod ? " · Retained from an earlier run" : successor ? " · Superseded version" : " · Earlier proposal")}</p>
        </div><div className="p2-model-continuation"><ExploreActions catalogMethod={catalogMethod} busy={busy} onContinue={onContinue} /></div></header>
        {successor && <SupersededNote successor={successor} onViewCurrent={viewCurrent} />}
        {selected && !catalogMethod && !successor && <p className="note context-note">{reviewed?.disposition.status === "exclude" ? "The lead did not retain this proposal in the catalog, so it cannot be selected for further work. It remains readable here as proposed." : "This exact proposal is not the current catalog definition. Explore the current retained definition to answer questions or continue this model."}</p>}
        {staleOutputs.map((output) => <div className="method-dependent-status" key={output.phase}><p className="note">{phaseLabel(output.phase)} results for this method</p><MethodStatusNote status={output} onOpen={onSource} /></div>)}
        <ReaderSection title="Methodological account" author={conciseLead ? "Research Lead" : author}>
          <ResearchDocument text={summaryForDisplay(conciseLead ? reviewed.disposition.method_summary_markdown : method.summary || method.scientific_question || method.rationale)} renderInternalLink={conciseLead ? leadInternalLink : undefined} />
          <NotationLookup record={conciseLead ? reviewed.comparison : selected || catalogMethod} methodScope={method.identity} onSource={onSource} />
          {!conciseLead && selected && <p className="note">The original proposal summary is shown in full. This saved record has no verified concise Lead account. Read its complete mathematics under Computation and full formulation.</p>}
          <div className="p2-reader-sources"><SourceRef reference={conciseLead ? leadSummarySource : source} onOpen={onSource} label={conciseLead ? "Lead methodological account source" : selected ? "Original proposal summary source" : "Catalog definition source"} /></div>
        </ReaderSection>
        {disclosure("assumptions", "Assumptions and limitations", <>
          {specialists.length > 0 && <ReaderSection title="When this model applies">{specialists.map((audit, index) => <section className="p2-specialist-applicability" key={index}><h4>{perspective(audit)}</h4><ResearchDocument text={audit.applicability_markdown} /><div className="p2-reader-sources"><SourceRef reference={audit.applicability_ref} onOpen={onSource} label={`${perspective(audit)} applicability source`} /></div></section>)}</ReaderSection>}
          <ReaderSection title="Original assumptions and limitations" author={author}><ResearchDocument text={{ assumptions: method.assumptions, limitations: method.limitations }} /><SourceRef reference={source} onOpen={onSource} label="Original assumptions source" /></ReaderSection>
        </>)}
        {disclosure("computation", "Computation and full formulation", <>
          <p className="note">These are proposed computational requirements. Measured performance belongs to computational evaluation.</p>
          <ReaderSection title="Computational profile" author={author}>{profile ? <>
            {profile.per_iteration_markdown && <><h4>Cost per iteration</h4><ResearchDocument text={profile.per_iteration_markdown} /></>}
            {profile.memory_markdown && <><h4>Memory footprint</h4><ResearchDocument text={profile.memory_markdown} /></>}
            {profile.scaling_markdown && <><h4>Scaling with problem size</h4><ResearchDocument text={profile.scaling_markdown} /></>}
            {!profile.per_iteration_markdown && !profile.memory_markdown && !profile.scaling_markdown && <p className="note">The recorded computational profile has no readable entries.</p>}
            <SourceRef reference={source} onOpen={onSource} label="Computational profile source" />
          </> : <p className="note">No computational profile was recorded for this {selected ? "proposal" : "catalog definition"}.</p>}</ReaderSection>
          {selected && <ReaderSection title="Data requirements" author={author}>{selected.data_requirements_markdown ? <ResearchDocument text={selected.data_requirements_markdown} /> : <p className="note">No separate data requirements were recorded.</p>}</ReaderSection>}
          <ReaderSection title="Full original formulation and algorithm" author={author}>
            <NotationLookup record={selected || catalogMethod} methodScope={method.identity} onSource={onSource} />
            <ResearchDocument text={method.scientific_question} /><CompleteFormulation definition={method.mathematical_definition} /><SourceRef reference={source} onOpen={onSource} label="Original formulation source" />
          </ReaderSection>
          {selected?.researcher_origin && <ReaderSection title={startingPoint ? "Selected model starting point and source" : "Your supplied method and source"} className={startingPoint ? "" : "contribution-surface"}>
            {startingPoint ? <><p className="note">Version {startingPoint.method_identity?.version} supplied the lead's starting point. Its original authorship and definition remain in the recorded sources.</p>
              <details className="research-details"><summary>Original starting formulation</summary><ResearchDocument text={selected.researcher_origin.specification_markdown || selected.researcher_origin.original_text || selected.researcher_origin} /></details>
              <SourceRef reference={startingPoint.catalog_ref} onOpen={onSource} label="Starting catalog definition source" /><SourceRef reference={startingPoint.proposal_ref} onOpen={onSource} label="Starting original proposal source" />
            </> : <ResearchDocument text={selected.researcher_origin.specification_markdown || selected.researcher_origin.original_text || selected.researcher_origin} />}
            {selected.researcher_origin.source_reference && <details className="research-details"><summary>Supplied source reference</summary><p className="note">{selected.researcher_origin.source_reference}</p></details>}
          </ReaderSection>}
        </>)}
        {disclosure("review", "Reviews and scientific sources", <>
          {!conciseLead && reviewed?.disposition.method_summary_markdown && <details className="research-details p2-historical-account"><summary>Full historical Lead procedural account</summary><p className="note">This account retains the writing contract of its original producing run.</p><ResearchDocument text={summaryForDisplay(reviewed.disposition.method_summary_markdown)} renderInternalLink={leadInternalLink} /><SourceRef reference={leadSummarySource} onOpen={onSource} label="Historical Lead account source" /></details>}
          {conciseLead && method.summary && <ReaderSection title="Proposer's original summary" author={author}><ResearchDocument text={summaryForDisplay(method.summary)} /><SourceRef reference={source} onOpen={onSource} label="Original proposal summary source" /></ReaderSection>}
          {selected && <ReaderSection title="Rationale and critical assessment" author="Research Lead">{reviewed ? <><ResearchDocument text={reviewed.disposition.rationale || reviewed.disposition.rationale_markdown || reviewed.disposition.reason_markdown} /><SourceRef reference={leadReviewSource || reviewed.comparison.generation_ref} onOpen={onSource} label="Lead assessment source" /></> : <p className="note">No lead assessment is linked to this exact proposal run.</p>}</ReaderSection>}
          {selected && <ReaderSection title={`Specialist reviews (${audits.length})`}><MethodAudits proposal={selected} reviews={reviews} onSource={onSource} /></ReaderSection>}
          {method.rationale && <ReaderSection title="Proposer rationale" author={author}><ResearchDocument text={method.rationale} /></ReaderSection>}
          {method.literature_provenance?.length > 0 && <ReaderSection title="Relation to the literature" author={author}>{method.literature_provenance.map((entry, i) => {
            const citation = literatureSources.find((source) => source.source_id === entry.citation_id || source.source_aliases?.includes(entry.citation_id) || source.source_ids?.includes(entry.citation_id));
            return <section key={i}><h4>{citation?.title || entry.citation_id || "Referenced publication"}</h4><p className="note">{humanLabel(entry.relation)}</p><ResearchDocument text={entry.contribution} />{citation && <div className="p2-reader-sources">{citationLinks(citation).map((link) => <a key={link.href} className="source-link ui-action" data-action="source" data-ui-role="system" href={link.href} target="_blank" rel="noreferrer"><ActionIcon name="source" />{link.label}</a>)}</div>}</section>;
          })}<SourceRef reference={source} onOpen={onSource} label="Scientific source record" /></ReaderSection>}
        </>)}
      </div>
    </div>
  </section>{renderSlot(issues, context)}{renderSlot(furtherWork, context)}</>;
}

function CatalogDiagnostics({ diagnostics = [], onSource }) {
  if (!diagnostics.length) return null;
  return <div className="catalog-diagnostics">
    <h4>Catalog diagnostics</h4>
    {diagnostics.map((diagnostic, i) => <div className="catalog-diagnostic" key={`${diagnostic.stable_id || "entry"}-${i}`}>
      <p className="note"><b>Catalog diagnostic:</b> {diagnostic.message}{diagnostic.detail ? ` Recorded problem: ${diagnostic.detail}.` : ""}{diagnostic.stable_id ? ` Model: ${diagnostic.stable_id}.` : ""}{diagnostic.shadowed ? " This malformed entry shadows an earlier valid record for the same method." : ""} The entry stays visible here but cannot be selected or run.</p>
      <SourceRef reference={diagnostic.source_ref} onOpen={onSource} label="Open the catalog source record" />
    </div>)}
  </div>;
}

function CatalogRecords({ methods = [], cards = [], onSource, onContinue, busy, compact = false }) {
  const retained = methods.filter((method) => !cards.some((card) => card.subject_ref === method.method_id));
  if (!cards.length && !retained.length) return null;
  return <section className="method-source-records"><h3>Model proposals and retained definitions</h3><p className="note">Earlier models remain available when a later run develops other proposals.</p><div className="method-proposals-grid">
    {cards.map((card, i) => <article className="t1card" key={card.card_id || i}><ResearchDocument text={card} /><SourceRef reference={card.generation_ref} onOpen={onSource} /></article>)}
    {retained.map((method) => { const definition = method.definition || {}; return <article className="t1card" key={method.method_id}><div className="section-heading"><h3 className="t1title">{method.title || method.name}</h3><span className="pill mut">{humanLabel(method.status || "Recorded")}</span></div>
      <p className="note">Current catalog definition{method.version ? ` · Version ${method.version}` : ""}</p>
      {compact ? <SourceRef reference={method.source_ref} onOpen={onSource} label="Original catalog definition" /> : <>
        <ResearchDocument text={definition.summary || definition.scientific_question || definition.rationale} />
        {definition.limitations?.length > 0 && <><h4>Limitations</h4><ResearchDocument text={definition.limitations} /></>}
        <details className="research-details"><summary>Read the model definition</summary><ResearchDocument text={definition} /><SourceRef reference={method.source_ref} onOpen={onSource} /></details>
      </>}
      {onContinue && ["active", "proposed"].includes(method.status) && <ActionButton action="details" disabled={busy} onClick={() => onContinue(method, "P3")}>Go to {phaseLabel("P3")}</ActionButton>}
    </article>; })}
  </div></section>;
}

// Neutral, collapsed home for run-level history: identifiers and hashes, the
// recorded selection, earlier comparisons and records, legacy scores, and the
// catalog diagnostics. None of this competes with the decision surface above.
function MethodHistory({ methods = [], cards = [], proposals = [], leadResponses = [], comparisons = [], comparison, diagnostics = [], legacyScores = [], publicationHistory = [], onSource, onOpenRun, onContinue, busy }) {
  const selections = recordedSelections(proposals, methods);
  const earlierComparisons = comparisons.filter((item) => item !== comparison);
  const retained = methods.filter((method) => !cards.some((card) => card.subject_ref === method.method_id));
  if (!comparison?.overview_markdown && !diagnostics.length && !selections.length && !leadResponses.length && !earlierComparisons.length && !legacyScores.length && !retained.length && !cards.length && !publicationHistory.length) return null;
  return <section className="p2-history" aria-label="Model versions and comparisons"><h3>Model versions and comparisons</h3>
    <p className="note">Earlier runs, original records, identifiers and catalog checks.</p>
    {comparison?.overview_markdown && <section><h4>Lead's full comparison</h4><ResearchDocument text={comparison.comparison_markdown} /><SourceRef reference={comparison.generation_ref} onOpen={onSource} label="Full comparison source" /></section>}
    {publicationHistory.length > 0 && <section aria-label="Publication history">
      <h4>Publication history</h4>
      <p className="note">These counts describe artifact checks and corrections before publication, not scientific validation.</p>
      {publicationHistory.map((item, index) => <div key={item.package_id || item.run_id || index}>
        <p className="note"><b>{item.is_current_package ? "Current publication" : "Earlier publication"}</b>{item.published_at && ` · ${item.published_at.slice(0, 16).replace("T", " ")}`}
          {` · Mechanical repair rounds: ${item.mechanical_repair_rounds ?? "unavailable"} · Researcher-authorized correction attempts: ${item.researcher_correction_attempts ?? "unavailable"}`}</p>
        <p className="note">Receipt: {item.receipt_id ? <span className="identity-line">{item.receipt_id}</span> : "unavailable"}
          {item.run_id && onOpenRun && <> · <ActionButton action="details" variant="link" data-run-origin={`MethodProposals:${item.package_id || item.receipt_id || index}:${item.run_id}`} onClick={(event) => onOpenRun(item.run_id, event.currentTarget)}>Open producing run</ActionButton></>}</p>
      </div>)}
    </section>}
    <CatalogDiagnostics diagnostics={diagnostics} onSource={onSource} />
    {selections.length > 0 && <div className="p2-selection-record">
      <h4>Recorded model selection</h4>
      {selections.map((method) => { const identity = method.selected_identity || method.identity || method.current_identity || {};
        return <p className="note" key={method.method_id}><b>{method.title || method.name || method.method_id}</b>{identity.version != null && ` · Version ${identity.version}`}{identity.stable_id && <> · <span className="identity-line">{identity.stable_id}</span></>}{identity.definition_sha256 && <> · definition <span className="identity-line">{identity.definition_sha256}</span></>}{method.aligned === false && " · the catalog now holds a different definition of this model"}</p>; })}
    </div>}
    <LeadResponses responses={leadResponses} onSource={onSource} />
    {earlierComparisons.length > 0 && <details className="research-details"><summary>Earlier lead comparisons</summary>{earlierComparisons.map((item, i) => <details className="research-details" key={i}><summary>{item.title || "Earlier comparison"}</summary><ResearchDocument text={item.comparison_markdown} /><SourceRef reference={item.generation_ref} onOpen={onSource} /></details>)}</details>}
    {(retained.length > 0 || cards.length > 0) && <details className="research-details"><summary>Published catalog definitions and earlier model records</summary><CatalogRecords methods={methods} cards={cards} onSource={onSource} compact /></details>}
    {legacyScores.length > 0 && <details className="research-details"><summary>Earlier recorded model scores</summary><p className="note">These earlier scores have no declared scale. Read their reasoning; the numbers alone do not establish a model's quality or suitability.</p>{legacyScores.map((score, i) => <div key={i}><h4>{methods.find((method) => method.method_id === score.method_ref)?.title || humanLabel(score.method_ref)}</h4><p className="note">Recorded score: {score.score}</p><ResearchDocument text={score.rationale} /></div>)}</details>}
  </section>;
}

function DirectProposals({ methods, cards, proposals, leadResponses, reviews, comparisons, literatureSources, diagnostics, legacyScores, publicationHistory, onSource, onOpenRun, ...workspace }) {
  const comparison = comparisons.find((item) => item.is_current_package !== false) || comparisons[0];
  return <div className="phase-two-workspace">
    <ExploreMethod methods={methods} cards={cards} proposals={proposals} reviews={reviews} comparisons={comparisons} comparison={comparison} literatureSources={literatureSources} onSource={onSource} {...workspace}
      modelHistory={<MethodHistory methods={methods} cards={cards} proposals={proposals} leadResponses={leadResponses} comparisons={comparisons} comparison={comparison} diagnostics={diagnostics} legacyScores={legacyScores} publicationHistory={publicationHistory} onSource={onSource} onOpenRun={onOpenRun} />} />
  </div>;
}

export default function MethodProposals({ methods = [], cards = [], proposals = [], reviews = [], comparisons = [], literatureSources = [], diagnostics = [], legacyScores = [], publicationHistory = [], onSource, onOpenRun, ...workspace }) {
  const direct = proposals.filter((proposal) => proposal.method && !proposal.no_method_proposed);
  const leadResponses = proposals.filter((proposal) => proposal.no_method_proposed === true);
  return <DirectProposals methods={methods} cards={cards} proposals={direct} leadResponses={leadResponses} reviews={reviews} comparisons={comparisons} literatureSources={literatureSources} diagnostics={diagnostics} legacyScores={legacyScores} publicationHistory={publicationHistory} onSource={onSource} onOpenRun={onOpenRun} {...workspace} />;
}
