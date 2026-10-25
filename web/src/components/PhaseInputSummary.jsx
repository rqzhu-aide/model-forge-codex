import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { phaseInputSummary } from "../phaseInputSummary";
import { navigatePhaseInput } from "../phaseInputNavigation";
import { readConversationDraft, subscribeConversationDrafts } from "../assumptionConversations";
import { ActionButton, ActionIcon } from "./Visuals";

function Count({ count, label, state, onClick }) {
  const content = <><span className={`input-status-symbol ${state}`} aria-hidden="true"><svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="8" cy="8" r="6" />{state === "saved" ? <path d="m4.5 8 2.2 2.2 4.8-4.7" /> : state === "unknown" ? <path d="M6.2 5.5c0-2 4-2 4 .5 0 1.2-2.2 1.5-2.2 3M8 10.5v1" /> : <path d="M8 4.5v4M8 10.5v1" />}</svg></span><b>{count}</b> {label}</>;
  return count ? <button type="button" className="input-summary-count" data-ui-role="research" onClick={onClick}>{content}</button> : <span className="input-summary-count empty">{content}</span>;
}

export default function PhaseInputSummary({ context, phase, scope, preparation, preparationStatus, activeRun, showSummary = true, status, navigationRequest, children }) {
  const title = !showSummary ? "Instructions and run settings" : phase === "P5" ? "Revise report" : "Revise and rerun";
  const [, setDraftRevision] = useState(0);
  const [session, setSession] = useState(null);
  const sessionRef = useRef(null);
  const scopeRef = useRef(scope); scopeRef.current = scope;
  const [notice, setNotice] = useState(null);
  useEffect(() => subscribeConversationDrafts(() => setDraftRevision(value => value + 1)), []);
  useLayoutEffect(() => {
    sessionRef.current?.dispose(); sessionRef.current = null; setSession(null); setNotice(null);
    return () => sessionRef.current?.dispose();
  }, [scope]);
  const summary = phaseInputSummary({ ...context, getDraft: readConversationDraft });
  const questions = summary.questions;
  const understanding = summary.understanding;
  const visit = (origin, anchor, returnLabel = "Back to rerun summary") => {
    const root = origin.closest('[data-reader-ready]');
    sessionRef.current?.dispose(); setSession(null); setNotice(null);
    const next = navigatePhaseInput({ root, origin, anchor, scope, currentScope: () => scopeRef.current,
      onUnavailable: () => { setSession(null); setNotice("This item has changed or is no longer displayed. Review the current section and try again."); } });
    sessionRef.current = next; setSession(next ? { navigation: next, returnLabel } : null);
  };
  useEffect(() => {
    if (navigationRequest?.origin) visit(navigationRequest.origin, "further-work", navigationRequest.returnLabel);
  }, [navigationRequest]);
  const back = () => { sessionRef.current?.back({ currentScope: () => scopeRef.current }); setSession(null); };
  const first = state => questions.items.find(item => item.state === state)?.anchor;
  const instructionState = !preparation.loaded ? preparation.error ? "Instructions unavailable" : "Loading instructions" : preparation.instructionsChanged ? "Unsaved instructions" : preparation.hasInstructions ? "Instructions saved" : "No added instructions";
  const inputState = activeRun ? activeRun.state === "awaiting_user" ? "Work waiting for input" : "Work in progress"
    : !preparation.loaded && preparation.error ? "Input check unavailable"
    : !preparationStatus || preparationStatus.loading ? "Checking inputs"
    : preparationStatus.error ? "Input check unavailable"
    : preparationStatus.importing ? "Importing files"
    : preparationStatus.invalidBudget || preparationStatus.invalidInputs ? "Check settings"
    : !preparationStatus.selected ? "Choose work"
    : preparationStatus.inputsReady ? "Inputs available" : "Inputs need attention";
  return <>
    <section className={`card run-preparation-card${showSummary ? " phase-input-summary" : ""}`} data-card-role={showSummary ? "attention" : "action"} data-reading-anchor="rerun-summary" aria-label={title}>
      <div className="card-heading"><h2>{title}</h2>{status}</div>
      <div className="body">
        {showSummary && <>
        {phase !== "P5" && <>
          <div className="input-summary-row" data-reading-anchor="rerun-questions">
            <button className="input-summary-label" type="button" data-ui-role="research" onClick={event => visit(event.currentTarget, "phase-decisions")}>Research questions<ActionIcon name="details" /></button>
            <div className="input-summary-statuses">
              <Count count={questions.answered} label="answered" state="saved" onClick={event => visit(event.currentTarget, first("answered"))} />
              <Count count={questions.unanswered} label="unanswered" state="pending" onClick={event => visit(event.currentTarget, first("unanswered"))} />
              <Count count={questions.unknown} label="unknown" state="unknown" onClick={event => visit(event.currentTarget, first("unknown"))} />
              {questions.unsaved > 0 && <button type="button" className="input-summary-count" data-ui-role="research" onClick={event => visit(event.currentTarget, questions.items.find(item => item.unsaved)?.anchor)}>{questions.unsaved} unsaved {questions.unsaved === 1 ? "edit" : "edits"}</button>}
            </div>
          </div>
          <div className="input-summary-row" data-reading-anchor="rerun-understanding">
            <button className="input-summary-label" type="button" data-ui-role="research" onClick={event => visit(event.currentTarget, "researcher-dialogue")}>Study understanding<ActionIcon name="details" /></button>
            <div className="input-summary-statuses">
              <Count count={understanding.saved} label="saved" state="saved" onClick={event => visit(event.currentTarget, understanding.items[0]?.anchor)} />
              <Count count={understanding.pending} label="to confirm" state="pending" onClick={event => visit(event.currentTarget, understanding.proposals[0]?.anchor)} />
            </div>
          </div>
        </>}
        <div className="input-summary-row preparation" data-reading-anchor="rerun-preparation">
          <button className="input-summary-label" type="button" data-ui-role="system" onClick={event => visit(event.currentTarget, "further-work")}>Run preparation<ActionIcon name="details" /></button>
          <div className="input-summary-statuses"><span>{instructionState}</span><span>{inputState}</span>{phase === "P4" && <span>{preparation.inputCount} files selected{preparation.inputsChanged ? " · unsaved" : ""}</span>}</div>
        </div>
        {context?.activePause && <ActionButton action="details" uiRole="research" onClick={event => visit(event.currentTarget, phase === "P5" ? "further-work" : "phase-decisions")}>Review the current pause</ActionButton>}
        <p className="note input-summary-hint">{phase === "P5" ? "Section discussions stay with the report." : "Counts reflect saved responses, not scientific readiness."} Review instructions and settings before starting.</p>
        {notice && <p className="note" role="status">{notice}</p>}
        </>}
        {children}
      </div>
    </section>
    {session && typeof document !== "undefined" && createPortal(<div className="input-summary-return"><ActionButton action="back" onClick={back}>{session.returnLabel}</ActionButton></div>, document.body)}
  </>;
}
