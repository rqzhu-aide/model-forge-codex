import { explanationRun, empiricalReaderProps } from "../phaseWorkflow";
import { methodStartingPoint } from "../methodSeed";
import ResearcherDialogue from "./ResearcherDialogue";
import ResearchGoalEditor from "./ResearchGoalEditor";
import IssuesCard from "./IssuesCard";
import { goalContextTarget, goalCorrections, goalSource } from "../phaseOneReader";
import FurtherWorkCard from "./FurtherWorkCard";
import { PhaseOverview, TheoryReading, ManuscriptReading, ScientificDocuments } from "./PhaseReading";
import TechnicalReportReading, { TechnicalReportDocument } from "./TechnicalReportReading";
import ResearcherPause from "./ResearcherPause";
import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import { api } from "../api";
import { PHASES, TERMINAL, humanLabel, modeLabel, phaseLabel, scoped, phaseOutputStatus } from "../research";
import { Dialog, ResearchDocument, RunState, SourceRef, MethodStatusNote } from "./Shared";
import { ActionButton } from "./Visuals";
import LaunchRun from "./LaunchRun";
import AssumptionConversations from "./AssumptionConversations";
import EmpiricalWorkbench, { EmpiricalEvaluationHistory } from "./EmpiricalWorkbench";
import { EmpiricalPause, EmpiricalSavedDecisions, EmpiricalProgressCard, EmpiricalExecutionHistory } from "./EmpiricalProgress";
import Assessments, { assessmentRepairRequest } from "./Assessments";
import { empiricalFollowupRequest, isEmpiricalTarget, theoryComponentRequest, theoryLinkDestination } from "../runRequests";
import TestedTheorySource from "./TestedTheorySource";
import PhaseOneWorkspace from "./PhaseOneWorkspace";
import { LiteratureHistory } from "./LiteratureWorkspace";
import MethodProposals from "./MethodProposals";
import { EarlierOpenQuestions } from "./ContextualRequests";
import { currentCorrectionsForScope } from "../contextualRequests";
import { selectResearchDocuments, sourceEntry } from "../researchContent";
import { activePhaseRun, latestScientificAttempt, methodPhaseContexts, phaseNavigationState, singleEvaluatedMethod } from "../phaseUiState";
import { empiricalDialogueItems, savedDecisionHistory } from "../empiricalProgress";
import ResearchProgress from "./ResearchProgress";
import { restoreReadingPosition } from "../readingPosition";

const sourceDocumentFamilies = new Set(["manuscript", "manuscript_candidate", "technical_report", "technical_report_candidate", "implementation_record", "implementation_record_candidate"]);

const evidenceContextLabel = (state) => ({
  current: "Recorded theory context", unchanged: "Linked theory is unchanged",
  affected: "Some linked theory needs reassessment", early_exploration: "Evidence from early exploration",
  theory_changed: "Theory has changed since this evaluation", method_changed: "Method has changed since this evaluation",
}[state] || "Evidence basis needs assessment");

export default function ProjectView({ projectId, context, reading = {}, onReadingChange, restorationKey = 0, focusReading = false, runReturn, returnScope, onReadingRestored, onContextChange, onOpenRun, onProjectUpdated }) {
  const { branch = "trunk", phase = "P1" } = context;
  const selectedNode = reading.selectedNode || null;
  const readerRoot = useRef(null); const readingRef = useRef(reading); readingRef.current = reading;
  const scopeBranch = phase === "P1" || phase === "P2" ? "trunk" : branch;
  const scope = `${projectId}:${scopeBranch}:${phase}`;
  const [snapshot, setSnapshot] = useState(null); const [error, setError] = useState(null); const [loading, setLoading] = useState(true);
  const [actionError, setActionError] = useState(null);
  const [reload, setReload] = useState(0); const [request, setRequest] = useState(null); const [source, setSource] = useState(null);
  const [conversationTarget, setConversationTarget] = useState(null);
  const [goalEdit, setGoalEdit] = useState(null);
  const [preparedIssue, setPreparedIssue] = useState(null);
  useEffect(() => { setConversationTarget(null); setGoalEdit(null); }, [scope, context.p2ProposalKey]);
  const [busy, setBusy] = useState(false); const actionLock = useRef(false);
  const [notice, setNotice] = useState(null); const [requestedRunId, setRequestedRunId] = useState(null); const sourceRequest = useRef(0);
  useEffect(() => { setNotice(null); }, [scope]);
  const refresh = () => setReload((n) => n + 1);
  // Cross-phase launch dialogs keep this view open, so follow their exact
  // inputs until they close instead of polling only the underlying phase.
  const readinessBranch = request?.branch || scopeBranch; const readinessPhase = request?.phase || phase;
  useEffect(() => {
    let active = true; let pending = false;
    const read = async () => {
      if (pending) return; pending = true;
      try {
        const [project, branches, runs, artifacts, attention, readiness, records, assessments, methods] = await Promise.all([
          api.project(projectId), api.branches(projectId), api.listRuns(projectId), api.artifacts(projectId, scopeBranch), api.decisionsPending(projectId),
          api.readiness(projectId, readinessBranch, readinessPhase), api.records(projectId, scopeBranch, phase), api.assessments(projectId, scopeBranch), api.methods(projectId),
        ]);
        const newest = latestScientificAttempt(runs.runs || [], phase, scopeBranch);
        const progressRun = newest && (phase === "P4" || newest.state === "awaiting_user") ? await api.run(projectId, newest.run_id).catch(() => null) : null;
        if (active) { setSnapshot({ scope, progressRun, project, branches: branches.branches || [], runs: runs.runs || [], artifacts, pending: attention, readiness, records: records.records || [], assessments: assessments.assessments || [], methods: methods.methods || [], methodDiagnostics: methods.diagnostics || [] }); setError(null); }
      } catch (e) { if (active) setError(e.message); } finally { pending = false; if (active) setLoading(false); }
    };
    setLoading(true); read();
    const timer = setInterval(read, 5000); const visible = () => { if (!document.hidden) read(); };
    window.addEventListener("focus", visible); document.addEventListener("visibilitychange", visible);
    return () => { active = false; clearInterval(timer); window.removeEventListener("focus", visible); document.removeEventListener("visibilitychange", visible); };
  }, [projectId, scopeBranch, phase, reload, readinessBranch, readinessPhase]);
  useEffect(() => {
    if (requestedRunId && snapshot?.runs.some((run) => run.run_id === requestedRunId && TERMINAL.has(run.state))) { setNotice(null); setRequestedRunId(null); }
  }, [snapshot, requestedRunId]);
  const data = snapshot?.scope === scope ? snapshot : null;
  const p4Visited = useRef(new Set());
  useEffect(() => {
    if (phase !== "P4" || !data || p4Visited.current.has(projectId)) return;
    p4Visited.current.add(projectId);
    if (branch === "trunk") { const selected = singleEvaluatedMethod(data); if (selected) onContextChange({ branch: selected }); }
  }, [phase, projectId, branch, Boolean(data)]);
  useLayoutEffect(() => {
    if (!data || !readerRoot.current) return;
    runReturn?.prepare(readerRoot.current, returnScope);
    return restoreReadingPosition(readerRoot.current, readingRef.current.position, focusReading, (root) => { runReturn?.finish(root, returnScope); onReadingRestored?.(); });
  }, [scope, Boolean(data), restorationKey]);
  if (!data) return <div>{error ? <div className="error" role="alert">Could not load this research context: {error} <ActionButton action="retry" onClick={refresh}>Retry</ActionButton></div> : <p className="note" role="status">Loading research context…</p>}</div>;
  const { project, branches, runs, artifacts, pending, readiness, records, assessments, methods, methodDiagnostics } = data;
  // Polling replaces objects even when inputs are unchanged. Refresh launch
  // readiness only when their contents change, without remounting draft forms.
  const readinessRevision = JSON.stringify(readiness);
  const needsMethod = !["P1", "P2"].includes(phase) && branch === "trunk";
  const methodContexts = methodPhaseContexts({ branches, methods, runs });
  const method = methods.find((m) => m.branch_id === branch || m.method_id === branch);
  const methodLabel = branch === "trunk" ? "Shared project basis" : method?.title || method?.name || branches.find((b) => b.branch_id === branch)?.method?.title || humanLabel(branch);
  const outputStatus = !["P1", "P2"].includes(phase) ? phaseOutputStatus(method, phase) : null;
  const outputStatuses = methods.flatMap((item) => item.dependent_outputs || []);
  const branchRuns = runs.filter((r) => r.branch_id === scopeBranch && r.phase === phase);
  const decision = scoped(artifacts.decisions, scopeBranch, phase).sort((a, b) => String(b.published_at || "").localeCompare(String(a.published_at || "")))[0];
  const activeRuns = runs.filter((r) => r.branch_id === scopeBranch && r.phase === phase && !explanationRun(r) && !TERMINAL.has(r.state));
  const cards = scoped(artifacts.cards, scopeBranch, phase); const summaries = scoped(artifacts.summaries, scopeBranch, phase);
  const scores = scoped(artifacts.scores, "trunk", "P2").slice().sort((a, b) => (Number(b.score) || 0) - (Number(a.score) || 0));
  const documents = selectResearchDocuments(scoped(artifacts.documents, scopeBranch, phase).filter((doc) => !(phase === "P1" && ((doc.kind === "literature_synthesis" && artifacts.literature_syntheses?.length) || (doc.kind === "literature_coverage" && artifacts.literature_coverage?.length))) && !(phase === "P2" && doc.kind === "method_catalog" && methods.length)));
  const currentMap = scoped(artifacts.claim_maps, scopeBranch, "P3")[0];
  const currentTheoryRef = currentMap?.theory_generation_ref || currentMap?.generation_ref;
  const launch = (p = phase, options = {}) => setRequest({ technicalReport: Boolean(project.workflow_capabilities?.technical_report), phase: p, branch: ["P1", "P2"].includes(p) ? "trunk" : branch, methodLabel, ...options });
  const started = (run) => { setSnapshot((current) => current ? { ...current, runs: [run, ...current.runs.filter((item) => item.run_id !== run.run_id)] } : current); setRequest(null); setRequestedRunId(run.run_id); setNotice(`${run.intent === "assessment" || run.mode === "p3.assessment" ? "Assessment" : "Work"} requested. Your research context stays open.`); refresh(); };
  const requestComponent = (intent, target, label) => { const options = theoryComponentRequest(intent, target, label); if (options) launch("P3", options); };
  const openSource = async (reference, componentId = null) => {
    const seq = ++sourceRequest.current; setSource({ reference, componentId, loading: true });
    const document = sourceDocumentFamilies.has(reference.family) && !componentId && !reference.entry_pointer && !reference.card_id;
    try { const body = document ? await api.recordDocument(projectId, reference) : await api.recordBody(projectId, reference.branch, reference.phase, reference.family, reference.generation_id); if (seq === sourceRequest.current) setSource({ reference, componentId, body }); }
    catch (e) { if (seq === sourceRequest.current) setSource({ reference, componentId, error: e.message }); }
  };
  const openTestedTheory = (id, reference) => {
    const destination = theoryLinkDestination(reference, currentTheoryRef);
    if (destination === "current_graph") onContextChange({ phase: "P3", readerJump: { node: id } });
    else if (destination === "inspected_source") openSource(reference, id);
  };
  const requestQuestion = (question) => {
    const options = empiricalFollowupRequest(question);
    if (options) launch("P4", options);
  };
  const continueMethod = async (selected, destination, { prepareRun = false } = {}) => {
    const invoker = document.activeElement;
    if (actionLock.current || !selected?.method_id) return; actionLock.current = true; setBusy(true); setActionError(null);
    try {
      const result = await api.activateMethod(projectId, selected.method_id, selected.identity || selected.current_identity);
      const selectedBranch = result.branch_id || result.branch?.branch_id || selected.branch_id || selected.method_id;
      if (prepareRun) {
        const version = (selected.identity || selected.current_identity)?.version || selected.version;
        const title = selected.title || selected.name || selected.definition?.title || selected.method_id;
        launch(destination, { branch: selectedBranch, methodLabel: `${title}${version != null ? ` · Version ${version}` : ""}`, title: `Run this Method in ${phaseLabel(destination)}`, returnFocus: () => invoker?.isConnected && invoker !== document.body ? invoker : readerRoot.current?.querySelector('[data-reading-anchor="p2-selected-model"]') });
      } else {
        onContextChange({ branch: selectedBranch, phase: destination });
        setNotice(`${phaseLabel(destination)} is open for ${selected.title}.`);
      }
      refresh();
    } catch (e) { setActionError(`${e.message} Refresh the available methods and inspect the intended version again.`); refresh(); }
    finally { actionLock.current = false; setBusy(false); }
  };
  const researchBasis = scoped(artifacts.research_bases, "trunk", "P1")[0];
  const goalTarget = goalContextTarget(project.problem_context, researchBasis);
  const openGoal = goalTarget ? () => setGoalEdit({ target: goalTarget, context: structuredClone(project.problem_context), paragraph: researchBasis.research_setting.research_goal_markdown }) : undefined;
  const prepareIssue = (issue) => phase === "P1" && issue ? setPreparedIssue(issue) : launch(phase, { context_refs: issue?.explanation_target ? [issue.explanation_target] : [], instructions: issue ? `Investigate this recorded issue: ${issue.question || issue.title || "Research question"}` : "" });
  const projectSaved = (updated) => { setSnapshot((current) => current ? { ...current, project: { ...current.project, project: updated } } : current); onProjectUpdated?.(updated); refresh(); };
  const explain = (target) => setConversationTarget({ ...target, methodLabel, methodVersion: method?.version });
  const navigate = (destination) => {
    const proposal = destination === "P2" && method ? (artifacts.method_proposals || []).find((item) => item.method?.identity?.stable_id === method.method_id && item.method?.identity?.version === (method.identity?.version || method.version)) : null;
    onContextChange({ phase: destination, ...(proposal ? { p2ProposalKey: (proposal.generation_ref?.run_id || "") + ":" + proposal.proposal_id } : {}) });
  };
  const progressRun = data.progressRun;
  const activePause = phase === "P4" && progressRun?.state === "awaiting_user" && Boolean(progressRun.p4_progress?.pause_request);
  const sequentialPause = phase !== "P4" && progressRun?.state === "awaiting_user" && Boolean(progressRun.researcher_pause?.pending_request);
  const savedPauseCount = phase === "P4" ? savedDecisionHistory(progressRun?.p4_progress, activePause).length : 0;
  const dialogueItems = phase === "P4" ? empiricalDialogueItems(progressRun, pending.attention || [], pending.researcher_answers || []) : { attention: pending.attention || [], answers: pending.researcher_answers || [] };
  const showIssues = () => { const recovery = phase === "P5" || ["P1", "P2"].includes(phase) && !activePause && !sequentialPause; if (recovery) { const card = document.getElementById(`${phase.toLowerCase()}-additional-work`); if (card) card.open = true; } const target = document.getElementById(recovery ? `${phase.toLowerCase()}-recovery` : "phase-issues"); target?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth", block: "start" }); target?.focus({ preventScroll: true }); };
  const correctionRows = currentCorrectionsForScope(pending.runs_needing_correction, runs, scopeBranch, phase);
  const corrections = correctionRows.length > 0 && <div className="execution-concerns" id={["P1", "P2"].includes(phase) ? `${phase.toLowerCase()}-recovery` : undefined} tabIndex={-1}><h3>Work that could not be completed</h3>{correctionRows.map((run) => <div className="inbox-row" key={run.run_id}><span>{modeLabel(run.mode)}</span><ActionButton action="details" data-run-origin={`ProjectView:1:${run.run_id}`} onClick={(event) => onOpenRun(run.run_id, event.currentTarget)}>Review what happened</ActionButton></div>)}</div>;
  const selectionIssues = (selection = {}) => ({
    issues: (artifacts.issues || []).filter((issue) => !selection.proposal || selection.catalogMethod || issue.generation_ref?.run_id === selection.proposal.generation_ref?.run_id),
    attention: dialogueItems.attention.filter((issue) => !selection.proposal || selection.catalogMethod || issue.generation_ref?.run_id === selection.proposal.generation_ref?.run_id),
    answers: dialogueItems.answers.filter((answer) => !selection.proposal || selection.catalogMethod || answer.attention?.generation_ref?.run_id === selection.proposal.generation_ref?.run_id),
  });
  const explainSelection = (selection, target) => setConversationTarget({ ...target, assessmentPurpose: target.assessmentPurpose || (project.workflow_capabilities?.researcher_dialogue && target.kind === "phase_issue" ? "model_dialogue" : undefined), methodLabel: selection.method?.title || methodLabel, methodVersion: selection.method?.identity?.version || method?.version });
  const researcherPause = sequentialPause ? <ResearcherPause key={progressRun.run_id + ":" + progressRun.researcher_pause.pending_request.request_id + ":" + progressRun.researcher_pause.pending_request.revision} projectId={projectId} run={progressRun} onSaved={refresh} onDiscuss={explain} onPrepare={() => launch(phase)} onSource={openSource} /> : null;
  const issues = (selection = {}) => <ResearcherDialogue problemContext={project.problem_context} project={project.project || project} catalogPreview={project.catalog} conversations={assessments} activeWork={runs.some((run) => !explanationRun(run) && !TERMINAL.has(run.state))} onDiscuss={setConversationTarget} modelRef={selection.method?.identity || method?.identity || method?.current_identity} onPrepare={prepareIssue} goalReference={goalSource(researchBasis)} projectId={projectId} phase={phase} branch={selection.methodBranch || scopeBranch} methodId={selection.methodId || (phase === "P2" ? undefined : method?.method_id)} methodLabel={selection.method?.title || (phase === "P1" ? null : methodLabel)} {...selectionIssues(selection)} onSaved={refresh} onSource={openSource} onExplain={(target) => explainSelection(selection, target)} corrections={["P1", "P2"].includes(phase) ? undefined : corrections} correctionCount={["P1", "P2"].includes(phase) ? 0 : correctionRows.length} activePause={activePause || sequentialPause} activePauseKind={sequentialPause ? "researcher" : progressRun?.p4_progress?.attention_kind} savedPauseCount={savedPauseCount} onNavigate={navigate}
    pause={researcherPause || (activePause || savedPauseCount ? <>{activePause ? <EmpiricalPause key={progressRun.p4_progress.pause_request.request_id + ":" + progressRun.p4_progress.pause_request.revision} projectId={projectId} run={progressRun} request={progressRun.p4_progress.pause_request} onChanged={refresh} onNavigate={navigate} onSource={openSource} onExplain={explain} /> : null}<EmpiricalSavedDecisions projectId={projectId} run={progressRun} onChanged={refresh} onNavigate={navigate} onSource={openSource} onExplain={explain} /></> : null)} />;
  const p1WorkDetails = phase === "P1" && <><details className="research-details" data-reading-anchor="team-work"><summary>Team work and scientific review</summary><IssuesCard embedded workOnly title="Team work" projectId={projectId} phase="P1" branch="trunk" issues={artifacts.issues || []} attention={dialogueItems.attention} answers={dialogueItems.answers} onSaved={refresh} onSource={openSource} onExplain={explain} onPrepare={prepareIssue} /></details>{corrections}</>;
  const p5WorkDetails = phase === "P5" && (sequentialPause || correctionRows.length > 0) && <div id="p5-recovery" tabIndex={-1}>{researcherPause}{corrections}</div>;
  const furtherWork = (selection = {}) => {
    const selected = selection.catalogMethod ? selection.method : null;
    const seed = selected ? methodStartingPoint(selected, selection.proposal, selection.catalogMethod) : researchBasis?.phase2_preparation?.supplied_method;
    const suggestions = phase === "P2" ? null
      : phase !== "P4" && decision?.available_actions?.length ? decision.available_actions
      : phase === "P4" ? [
        { title: "Lead's recommendation", text: scoped(artifacts.empirical_summaries, scopeBranch, "P4")[0]?.decision_summary?.recommendation_markdown },
        ...(artifacts.questions || artifacts.p4_questions || []).filter((item) => item.branch === scopeBranch).map((item) => ({
          title: item.title, body: [
            { title: "Research Lead", text: item.review?.next_steps_markdown },
            { title: "Data Analyst", text: item.result?.next_steps_markdown },
          ].filter((part) => part.text),
        }))].filter((item) => item.text || item.body?.length) : null;
    const p2WorkDetails = phase === "P2" && <><details className="research-details" data-reading-anchor="team-work"><summary>Team work and scientific review</summary><IssuesCard embedded workOnly title="Team work" projectId={projectId} phase="P2" branch={selection.methodBranch || scopeBranch} methodId={selection.methodId} modelRef={selection.method?.identity} methodLabel={selection.method?.title} {...selectionIssues(selection)} onSaved={refresh} onSource={openSource} onExplain={(target) => explainSelection(selection, target)} onPrepare={prepareIssue} onNavigate={navigate} /></details>{corrections}</>;
    return <FurtherWorkCard defaultOpen={phase === "P2" && selection.emptyState} preparedIssue={phase === "P1" ? preparedIssue : undefined} onPrepared={() => setPreparedIssue(null)} history={phase === "P1" ? history() : phase === "P2" ? history(selection.modelHistory) : phase === "P4" ? history() : undefined} workDetails={phase === "P2" ? p2WorkDetails : p1WorkDetails} status={phase === "P1" && latestScientificAttempt(runs, "P1", "trunk") ? <RunState state={latestScientificAttempt(runs, "P1", "trunk").state} /> : undefined} workflowRevision={project.catalog?.version} readinessRevision={readinessRevision} technicalReport={Boolean(project.workflow_capabilities?.technical_report)} projectId={projectId} phase={phase} branch={phase === "P2" && !selected ? "trunk" : selection.methodBranch || scopeBranch} methodId={(selected ? selection.methodId : undefined) || (phase === "P2" ? undefined : method?.method_id)} modelRef={selected?.identity || method?.identity || method?.current_identity} methodLabel={selected?.title || (phase === "P1" ? null : phase === "P2" ? "New model proposals" : methodLabel)} suppliedMethod={seed} onSource={openSource} issues={artifacts.issues || []} recommendations={suggestions?.length ? suggestions : null} onStarted={started} onNavigate={navigate} activeRun={activePhaseRun(runs, phase, scopeBranch)}>
      {p5WorkDetails}
      {phase === "P2" && (selection.modificationOptions || selection.proposedWork) ? <details className="research-details" data-reading-anchor="proposed-next-work"><summary>Modification options and proposed next work</summary>{selection.modificationOptions}{selection.proposedWork}</details> : <>{selection.modificationOptions}{selection.proposedWork}{selection.exploreActions}</>}
      {phase === "P2" && !selected && researchBasis?.phase2_preparation && <details className="research-details"><summary>Ideas carried from the literature study</summary><ResearchDocument text={researchBasis.phase2_preparation} /><SourceRef reference={researchBasis.generation_ref} onOpen={openSource} /></details>}
    </FurtherWorkCard>;
  };
  const empiricalProps = { implementations: artifacts.implementations, summaries: artifacts.empirical_summaries, loadErrors: artifacts.load_errors, diagnostics: artifacts.diagnostics, exhibits: artifacts.exhibits, questions: artifacts.questions || artifacts.p4_questions,
    cases: artifacts.cases || (artifacts.case_manifests || []).flatMap((manifest) => (manifest.cases || []).map((item) => ({ ...item, branch: manifest.branch, generation_ref: manifest.generation_ref }))), protocols: artifacts.protocols, branch: scopeBranch, onSource: openSource, onTheory: openTestedTheory, onRequest: requestQuestion };
  const progress = <ResearchProgress runs={runs} run={phase === "P4" ? progressRun : undefined} phase={phase} branch={scopeBranch} retained={Boolean(records.length)} correctionCount={correctionRows.length} onOpenRun={onOpenRun} onShowIssues={activePause || sequentialPause || correctionRows.length ? showIssues : undefined}>{phase === "P4" && progressRun && <EmpiricalProgressCard projectId={projectId} run={progressRun} onChanged={refresh} onOpenRun={onOpenRun} onShowIssues={activePause ? showIssues : undefined} />}</ResearchProgress>;
  const history = (modelHistory) => <details className="research-details run-history" data-card-role="history" data-reading-anchor="research-history"><summary>{["P1", "P2"].includes(phase) ? "Phase run history" : "Research history and sources"}</summary>
      {phase === "P4" && <><EmpiricalExecutionHistory run={progressRun} /><EmpiricalEvaluationHistory {...empiricalProps} />{scoped(artifacts.evidence_status, scopeBranch, "P4").map((status, index) => <div key={index}><b>{evidenceContextLabel(status.state)}</b><p>{status.message}</p><SourceRef reference={status.generation_ref} onOpen={openSource} /></div>)}{scoped(artifacts.prior_evaluations, scopeBranch, "P4").map((evaluation, index) => <details className="research-details" key={evaluation.run_id || index} data-reading-anchor={evaluation.run_id ? `earlier-evaluation:${evaluation.run_id}` : undefined}><summary>Earlier evaluation · {(evaluation.published_at || "").slice(0, 10)}</summary>{evaluation.artifacts ? <><EmpiricalWorkbench {...empiricalReaderProps(evaluation.artifacts)} branch={scopeBranch} onSource={openSource} onTheory={openTestedTheory} onRequest={requestQuestion} /><EmpiricalEvaluationHistory {...empiricalReaderProps(evaluation.artifacts)} branch={scopeBranch} onSource={openSource} /></> : <ResearchDocument text={evaluation.description || "The earlier sources remain available in the producing work."} />}{evaluation.run_id && <ActionButton action="details" data-run-origin={`ProjectView:2:${evaluation.run_id}`} onClick={(event) => onOpenRun(evaluation.run_id, event.currentTarget)}>Open earlier work</ActionButton>}</details>)}</>}
      <div className="table-scroll"><table><thead><tr><th>Started</th><th>Work</th><th>Progress</th><th></th></tr></thead><tbody>{branchRuns.map((run) => <tr key={run.run_id}><td>{(run.created_at || run.requested_at || "").slice(0, 16).replace("T", " ")}</td><td>{run.assessment_purpose === "issue_suggestions" ? "Lead suggestions" : explanationRun(run) ? "Explanation conversation" : modeLabel(run.mode)}</td><td><RunState state={run.state} /></td><td><ActionButton action="details" data-run-origin={`ProjectView:3:${run.run_id}`} onClick={(event) => onOpenRun(run.run_id, event.currentTarget)}>Open history</ActionButton></td></tr>)}</tbody></table></div>
      {!branchRuns.length && <p className="note">No work has been started for this phase and method yet.</p>}
      {phase === "P1" && <><LiteratureHistory collections={artifacts.literature_collections} coverage={artifacts.literature_coverage?.filter((record) => !record.derived)} bases={artifacts.research_bases} displayedBasis={researchBasis} libraries={artifacts.literature_libraries} cards={cards} syntheses={artifacts.literature_syntheses?.filter((record) => !record.derived)} onSource={openSource} /><ScientificDocuments documents={documents} onSource={openSource} empty="Earlier research documents, when available, appear here." /></>}
      <EarlierOpenQuestions items={pending.attention} answers={pending.researcher_answers} branch={scopeBranch} phase={phase} onSource={openSource} settingQuestions={phase === "P1" ? researchBasis?.research_setting?.clarification_questions : undefined} settingReference={phase === "P1" ? researchBasis?.generation_ref : undefined} />
      {modelHistory}
      <h3>Original research sources</h3>{records.map((record) => <div key={record.family} className="inbox-row"><span className="inbox-q">{humanLabel(record.family)}</span><ActionButton action="source" onClick={() => openSource({ branch: scopeBranch, phase, family: record.family, ...record.current })}>Read complete source</ActionButton></div>)}
    </details>;
  return <div ref={readerRoot} data-reader-ready="true">
    <header className="page project-toolbar"><h1>{project.project?.name || project.name || projectId}</h1>
    <nav className="phase-ring" aria-label="Research phases">{PHASES.map(([p, label]) => { const status = phaseNavigationState({ phase: p, branch, branches, runs, methods, outputStatuses }); const cue = status.state === "waiting" ? "Needs input" : status.state === "outdated" ? "Outdated" : status.state === "interrupted" ? status.latest_attempt?.state === "failed" ? "Failed" : status.latest_attempt?.state === "cancelled" ? "Stopped" : "Interrupted" : status.state === "running" ? status.latest_attempt?.state === "requested" ? "Queued" : "Running" : null; return <button key={p} className={`phase-tab ${status.state}${p === phase ? " active" : ""}`} data-phase-state={status.state} aria-label={`${label}: ${status.label}`} aria-current={p === phase ? "page" : undefined} onClick={() => navigate(p)}><span className="pname">{label}</span>{cue ? <span className="phase-status-label">{cue}</span> : <span className="sr-only">{status.label}</span>}</button>; })}</nav>
    {!needsMethod && progress}</header>
    {error && <div className="error" role="alert">Updates could not be loaded: {error} <ActionButton action="retry" onClick={refresh}>Retry</ActionButton></div>}
    {actionError && <div className="error" role="alert">{actionError} <ActionButton action="close" variant="link" onClick={() => setActionError(null)}>Dismiss</ActionButton></div>}
    {scoped(artifacts.load_errors, scopeBranch, phase).map((issue, i) => <div className="note warn" role="alert" key={i}>A research source could not be loaded: {issue.message}. Other available evidence remains visible.</div>)}
    {notice && <div className="banner" role="status">{notice} <ActionButton action="close" variant="link" onClick={() => setNotice(null)}>Dismiss</ActionButton></div>}
    {!["P1", "P2"].includes(phase) && <div className="branch-row"><label className="field"><span>Method</span><select value={branch} onChange={(event) => onContextChange({ branch: event.target.value })}><option value="trunk">Choose a method</option>{methodContexts.map((item) => <option key={item.branch} value={item.branch}>{item.label}{phase === "P4" ? ` · ${phaseNavigationState({ phase, branch: item.branch, branches, runs, methods, outputStatuses }).label}` : ""}</option>)}</select></label><ActionButton action="details" onClick={() => navigate("P2")}>Compare methods</ActionButton></div>}
    {needsMethod && <section className="card method-phase-choices" data-card-role="research"><div className="card-heading"><h2>Choose a method to explore</h2></div><div className="body"><p className="note">Theory, numerical evaluation, and reports belong to individual methods. Choose the method whose work you want to inspect.</p>{methodContexts.map((item) => { const status = phaseNavigationState({ phase, branch: item.branch, branches, runs, methods, outputStatuses }); return <div className="method-phase-choice" key={item.branch} data-phase-state={status.state}><div><h3>{item.label}</h3><p className="note">{status.label}</p></div><ActionButton action="details" onClick={() => onContextChange({ branch: item.branch })}>Explore this method</ActionButton></div>; })}{!methodContexts.length && <><p className="note">Choose a proposed method in Phase 2 - Propose Methods to begin this work.</p><ActionButton action="details" onClick={() => navigate("P2")}>Compare methods</ActionButton></>}</div></section>}
    {needsMethod && phase !== "P5" && issues()}
    {!needsMethod && <>
    {outputStatus && <MethodStatusNote status={outputStatus} onOpen={openSource} />}
    {phase === "P1" && <PhaseOneWorkspace onGoal={openGoal} goalCorrectionCount={goalCorrections(project.problem_context, goalSource(researchBasis)).length} key={projectId} project={project.project || project} basis={researchBasis} reading={reading} onReadingChange={onReadingChange} artifacts={artifacts} cards={cards} attentionItems={pending.attention} researcherAnswers={pending.researcher_answers} activeRunCount={activeRuns.length} onSaved={projectSaved} onSource={openSource} issues={issues()} furtherWork={furtherWork()} />}
    {phase === "P2" && <MethodProposals key={projectId} methods={methods} cards={cards} proposals={scoped(artifacts.method_proposals, "trunk", "P2")} reviews={scoped(artifacts.method_reviews, "trunk", "P2")} comparisons={scoped(artifacts.catalog_assessments, "trunk", "P2")} publicationHistory={scoped(artifacts.publication_history, "trunk", "P2")} onOpenRun={onOpenRun} literatureSources={scoped(artifacts.literature_libraries, "trunk", "P1")[0]?.sources || []} diagnostics={methodDiagnostics} legacyScores={scores} onSource={openSource} projectId={projectId} attentionItems={pending.attention || []} researcherAnswers={pending.researcher_answers || []} onResolved={refresh} onContinue={continueMethod} busy={busy} reading={reading} onReadingChange={onReadingChange} initialPick={context.p2ProposalKey} onPick={(p2ProposalKey) => onContextChange({ p2ProposalKey })} issues={issues} furtherWork={furtherWork} />}
    {phase === "P3" && <><PhaseOverview phase={phase} decision={decision} summaries={summaries} methodLabel={methodLabel} onSource={openSource} /><TheoryReading key={scopeBranch} reading={reading} onReadingChange={onReadingChange} claimMaps={artifacts.claim_maps} falsificationLogs={artifacts.falsification_logs} glossaries={artifacts.glossaries} documents={documents} branch={scopeBranch} selected={selectedNode} onSelect={(selectedNode) => onReadingChange?.({ selectedNode })} onRequest={requestComponent} onSource={openSource} conversations={assessments} onAssumptionConversation={explain} assessments={<Assessments embedded projectId={projectId} assessments={assessments.filter((a) => !a.target?.branch || a.target.branch === scopeBranch)} selectedNode={selectedNode} onStarted={started} onSource={openSource} onRepair={(assessment) => launch("P3", assessmentRepairRequest(assessment))} />} />{issues()}{furtherWork()}</>}
    {phase === "P4" && <EmpiricalWorkbench key={scopeBranch} {...empiricalProps} reading={reading} onReadingChange={onReadingChange} awaitingDirection={progressRun?.state === "awaiting_user"} progressData={progressRun?.p4_progress} progressState={progressRun?.state} issues={issues()} furtherWork={furtherWork()} />}
    {phase === "P5" && <><TechnicalReportReading key={scopeBranch} selectedTab={reading.tab} onTabChange={(tab) => onReadingChange?.({ tab })} documents={documents} decision={decision} traceability={scoped(artifacts.claim_traceability, scopeBranch, "P5")} reviewContext={scoped(artifacts.manuscript_review_context, scopeBranch, "P5")} onSource={openSource} onDiscussSection={explain} />{furtherWork()}</>}
    {!["P1", "P2", "P4"].includes(phase) && history()}
    </>}
    {request && <LaunchRun workflowRevision={project.catalog?.version} readinessRevision={readinessRevision} projectId={projectId} onSource={openSource} request={request} activeRun={activePhaseRun(runs, request.phase, request.branch)} currentTargetRef={request.target && !isEmpiricalTarget(request.target) ? currentTheoryRef : null} onClose={() => setRequest(null)} onStarted={started} />}
    {goalEdit && <ResearchGoalEditor projectId={projectId} snapshot={goalEdit} currentContext={project.problem_context} currentGoal={goalSource(researchBasis)} onClose={() => setGoalEdit(null)} onSaved={refresh} onDiscuss={setConversationTarget} onSource={openSource} />}
    {conversationTarget && <AssumptionConversations key={JSON.stringify(conversationTarget)} projectId={projectId} target={conversationTarget} conversations={assessments} onClose={() => setConversationTarget(null)} onSource={openSource} onStarted={refresh} />}
    {source && <Dialog returnFocus={() => readerRoot.current?.querySelector('[data-reading-anchor="p2-selected-model"]') || [...(readerRoot.current?.querySelectorAll('[role="tabpanel"]') || [])].find((panel) => panel.getClientRects().length)} title={source.componentId ? "Theory used by this evaluation" : "Research source"} onClose={() => { sourceRequest.current++; setSource(null); }}>{source.loading ? <p className="note">Loading the source…</p> : source.error ? <div className="error" role="alert">{source.error}<ActionButton action="retry" onClick={() => openSource(source.reference, source.componentId)}>Retry</ActionButton></div> : <>{source.componentId ? <TestedTheorySource document={source.body} componentId={source.componentId} onCurrentTheory={() => { sourceRequest.current++; setSource(null); onContextChange({ phase: "P3", readerJump: { node: source.componentId } }); }} /> : sourceDocumentFamilies.has(source.body?.kind) && source.body?.generation_ref ? ["technical_report", "technical_report_candidate"].includes(source.body.kind) ? <TechnicalReportDocument document={source.body} onSource={openSource} showRecordSource={false} /> : <ScientificDocuments documents={[source.body]} onSource={openSource} showRecordSource={false} /> : <ResearchDocument text={(source.reference.entry_pointer || source.reference.card_id) ? sourceEntry(source.body, source.reference.entry_pointer, source.reference.card_id) : typeof source.body === "string" ? source.body : source.body?.body_md || source.body?.text || source.body} />}<details className="research-details"><summary>Complete record and reference</summary><pre className="record">{JSON.stringify(source.reference, null, 2)}</pre><pre className="record">{typeof source.body === "string" ? source.body : JSON.stringify(source.body?.structured || source.body, null, 2)}</pre></details></>}</Dialog>}
  </div>;
}
