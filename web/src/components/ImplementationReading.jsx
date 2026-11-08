import React from "react";
import { hasExactRef, humanLabel } from "../research";
import { SourceRef } from "./Shared";
import ResearchDocument from "./EmpiricalDocument";
import { ActionButton, ActionIcon } from "./Visuals";
import EmpiricalReadingButton, { empiricalReadingSize } from "./EmpiricalReading";
import ResearchCardLayout from "./ResearchCardLayout";

const AUTHORS = { data_analyst: "Data Analyst", research_lead: "Research Lead", theorist: "Theorist" };

function DeliveryFiles({ record }) {
  const entries = [["model_entrypoint", "Model entrypoint"], ["example_generator", "Synthetic generator"], ["example_runner", "Example runner"], ["readme", "Execution instructions"]];
  return <dl className="empirical-setup-fields">{entries.map(([key, label]) => { const pointer = record.reproduction?.[key]?.artifact; const file = pointer && record.files?.find((item) => item.path === pointer.path && (!pointer.sha256 || item.sha256 === pointer.sha256)); return <div key={key}><dt>{label}</dt><dd>{pointer ? <><code>{pointer.path}</code>{file?.source_verified === true && file.artifact_url ? <span className="btnrow"><a className="source-link ui-action" data-action="source" data-ui-role="system" href={file.artifact_url} target="_blank" rel="noreferrer"><ActionIcon name="source" />Inspect {label.toLowerCase()}</a>{file.download_url && <a className="source-link ui-action" data-action="source" data-ui-role="system" href={file.download_url}><ActionIcon name="source" />Download {label.toLowerCase()}</a>}</span> : <p className="note warn">{file?.source_error || "This retained file could not be verified."}</p>}</> : <span className="note">Unavailable in this record.</span>}</dd></div>; })}</dl>;
}

function AuthoredAccount({ record, review = false }) {
  const sections = record.sections || []; const Heading = review ? "h5" : "h4";
  // Keep the separately authored account, including unique qualifications. Only
  // an exact repeated passage within this one author's record is shown once.
  const body = typeof record.body_md === "string" ? record.body_md : "";
  const repeated = body && sections.some((section) => section.body_md?.trim() === body.trim());
  return <>{body && !repeated && <ResearchDocument text={body} />}{sections.map((section) => <section key={section.key}><Heading>{section.title || humanLabel(section.key)}</Heading>{section.status && <p className="note">{humanLabel(section.status)}</p>}<ResearchDocument text={section.body_md} /></section>)}{!body && !sections.length && (review ? <ResearchDocument text={record.structured} /> : <p className="note">A separate explanation of the implemented procedure, choices and departures was not recorded.</p>)}</>;
}

export function ImplementationDetails({ record, strategy, strategySource, onSource }) {
  const reproduction = record.reproduction;
  return <div className="empirical-implementation-details">
    {(strategy?.route || strategy?.route_rationale) && <section className="implementation-route"><h3>{{ package_reuse: "Use a package", package_adaptation: "Adapt a package", custom_implementation: "Custom implementation" }[strategy.route] || humanLabel(strategy.route || "Implementation route")}</h3><ResearchDocument text={strategy.route_rationale} /><SourceRef reference={strategySource} onOpen={onSource} label="Implementation route source" /></section>}
    <AuthoredAccount record={record} />
    {reproduction && <section className="implementation-reproduction"><h3>Model code and synthetic example</h3><DeliveryFiles record={record} /><ResearchDocument text={reproduction.invocation} />{reproduction.runtime_identity && <><h4>Shared runtime</h4><ResearchDocument text={reproduction.runtime_identity} /></>}{reproduction.dependencies?.length > 0 && <><h4>Dependencies</h4><ul>{reproduction.dependencies.map((item, index) => <li key={index}>{item.name} {item.version}{item.source && <> · <ResearchDocument text={item.source} /></>}</li>)}</ul></>}</section>}
    <SourceRef reference={record.generation_ref} onOpen={onSource} label="Implementation source" />
  </div>;
}

export function ImplementationFiles({ record, onSource }) {
  return <div className="implementation-files"><ul>{record.files.map((file, fileIndex) => <li key={`${file.path}:${fileIndex}`}><b>{file.label || humanLabel(file.kind || "Implementation file")}</b>{file.artifact_url && file.source_verified !== false ? <span className="btnrow"><a className="source-link ui-action" data-action="source" data-ui-role="system" href={file.artifact_url} target="_blank" rel="noreferrer"><ActionIcon name="source" />Inspect saved {humanLabel(file.kind || "file").toLowerCase()}</a>{file.download_url && file.source_verified === true && <a className="source-link ui-action" data-action="source" data-ui-role="system" href={file.download_url}><ActionIcon name="source" />Download {file.label || humanLabel(file.kind || "file").toLowerCase()}</a>}</span> : <p className="note warn">{file.source_error || "The saved file could not be verified."}</p>}{file.path && <details className="research-details"><summary>File identity</summary><code>{file.path}</code>{file.sha256 && <p className="note">SHA-256: <code>{file.sha256}</code></p>}</details>}</li>)}</ul><SourceRef reference={record.generation_ref && { ...record.generation_ref, entry_pointer: "/files" }} onOpen={onSource} label="Saved file manifest source" /></div>;
}

export function ImplementationReview({ record, onSource }) {
  return <div className="implementation-review"><p className="note">Independent assessment by Theorist · Same evaluation</p><AuthoredAccount record={record} review /><SourceRef reference={record.generation_ref} onOpen={onSource} label="Theorist assessment source" /></div>;
}

const accountText = (record) => {
  const body = typeof record.body_md === "string" ? record.body_md : "";
  const sections = record.sections || [];
  return [sections.some((section) => section.body_md?.trim() === body.trim()) ? null : body,
    ...sections.map((section) => section.body_md), !body && !sections.length ? record.structured : null];
};

export default function ImplementationReading({ records = [], protocols = [], summary, hasNotation = false, onNotation, onSource }) {
  const fidelity = summary?.decision_summary?.method_fidelity_markdown;
  const fidelitySource = fidelity && <SourceRef reference={summary.generation_ref && { ...summary.generation_ref, entry_pointer: "/decision_summary/method_fidelity_markdown" }} onOpen={onSource} label="Assessment source" />;
  const fidelityAccount = fidelity && <section className="implementation-assessment"><h3>Implementation assessment</h3><ResearchDocument text={fidelity} />{!records.length && fidelitySource}</section>;
  return <section className="empirical-implementation">
    {!records.length && fidelityAccount}
    {!records.length && <p className="note">No separate implementation record is available for this evaluation. Code correspondence and retained checks cannot be established from successful execution alone.</p>}
    {records.map((record, index) => {
      const reproduction = record.reproduction;
      const strategyProtocol = record.generation_ref?.run_id && record.generation_ref?.package_id && protocols.find((protocol) => protocol.generation_ref?.run_id === record.generation_ref.run_id && protocol.generation_ref?.package_id === record.generation_ref.package_id);
      const strategy = record.implementation_strategy || strategyProtocol?.implementation_strategy;
      const strategyReference = record.implementation_strategy ? record.generation_ref : strategyProtocol?.generation_ref;
      const strategySource = strategyReference && { ...strategyReference, entry_pointer: "/implementation_strategy" };
      const sections = record.sections || [];
      const assessment = !fidelity && sections.find((section) => ["correspondence", "fidelity", "rule"].includes(section.key));
      const issues = !fidelity && sections.find((section) => section.key === "limitations");
      const detailsRecord = { ...record, body_md: [assessment, issues].some((section) => section?.body_md?.trim() === record.body_md?.trim()) ? "" : record.body_md, sections: sections.filter((section) => section !== assessment && section !== issues) };
      const roleCount = ["model_entrypoint", "example_generator", "example_runner", "readme"].filter((key) => reproduction?.[key]?.artifact).length;
      const detailSize = empiricalReadingSize([strategy?.route_rationale, ...accountText(detailsRecord), reproduction?.invocation, reproduction?.runtime_identity, ...(reproduction?.dependencies || []).flatMap((item) => [item.name, item.version, item.source])], roleCount ? [`${roleCount} reproduction ${roleCount === 1 ? "file role" : "file roles"}`] : []);
      const hasDetails = Boolean(detailSize || strategy?.route || detailsRecord.sections.length);
      const reviewSize = record.theorist_review && empiricalReadingSize(accountText(record.theorist_review));
      const hasReview = Boolean(reviewSize || record.theorist_review?.sections?.length);
      const hasActions = Boolean(record.bundle_error || record.bundle_url && reproduction?.status === "available" || reproduction?.status === "unavailable");
      const hasResources = Boolean(hasDetails || record.files?.length || hasReview || hasExactRef(record.generation_ref) || hasExactRef(record.theorist_review?.generation_ref) || index === 0 && fidelity && hasExactRef(summary.generation_ref) || index === 0 && hasNotation && Boolean(onNotation));
      const delivery = record.bundle_error ? <p className="note warn" role="alert">The source bundle is unavailable: {record.bundle_error}</p> : record.bundle_url && reproduction?.status === "available" ? <a className="btn ui-action" data-ui-role="system" data-action="source" href={record.bundle_url}><ActionIcon name="source" />Download code and example bundle</a> : <p className="note">{reproduction?.status === "unavailable" ? "Portable delivery is unavailable." : "No verified code and example bundle is available in this record."}</p>;
      const actions = <section className="implementation-delivery"><h3>Code files</h3>{delivery}</section>;
      const resources = <>
        {index === 0 && hasNotation && onNotation && <section><h3>Notation</h3><div className="btnrow"><ActionButton action="details" variant="link" aria-haspopup="dialog" onClick={onNotation}>Notation</ActionButton></div></section>}
        {(hasDetails || record.files?.length > 0 || hasReview) && <section><h3>Supporting reading</h3><div className="reading-toolbar empirical-support-toolbar" aria-label="Implementation supporting documents">
          {hasDetails && <EmpiricalReadingButton kind="p4-implementation-details" title="Implementation details" sizeLabel={detailSize} input={{ record: detailsRecord, strategy, strategySource }} renderBody={(input, openSource) => <ImplementationDetails {...input} onSource={openSource} />} onSource={onSource} />}
          {record.files?.length > 0 && <EmpiricalReadingButton kind="p4-implementation-files" title="Saved files and checks" sizeLabel={`${record.files.length} saved ${record.files.length === 1 ? "file" : "files"}`} input={{ record }} renderBody={(input, openSource) => <ImplementationFiles {...input} onSource={openSource} />} onSource={onSource} />}
          {hasReview && <EmpiricalReadingButton kind="p4-implementation-review" title="Theorist assessment" sizeLabel={reviewSize} input={{ record: record.theorist_review }} renderBody={(input, openSource) => <ImplementationReview {...input} onSource={openSource} />} onSource={onSource} />}
        </div></section>}
        {!hasDetails && <p className="note">No separate implementation, verification or dependency details are recorded.</p>}
        {!record.files?.length && <p className="note">No code, configuration, environment or check files are linked in this record.</p>}
        {!hasReview && <><p className="note">{record.theorist_review ? "No readable theorist assessment is retained for this exact evaluation." : "No theorist assessment is linked to this exact evaluation."}</p>{hasExactRef(record.theorist_review?.generation_ref) && <SourceRef reference={record.theorist_review.generation_ref} onOpen={onSource} label="Theorist assessment source" />}</>}
        <div className="btnrow">{index === 0 && fidelitySource}<SourceRef reference={record.generation_ref} onOpen={onSource} label="Implementation source" /></div>
      </>;
      return <article className="scientific-block" key={record.generation_ref?.generation_id || index}>
        <ResearchCardLayout actions={hasActions ? actions : null} resources={hasResources ? resources : null} actionsLabel="Implementation actions" label="Implementation supporting reading">
          {index === 0 && fidelityAccount}
          <p className="note">{AUTHORS[record.producer_role] ? `Implementation account by ${AUTHORS[record.producer_role]}` : "Implementation account author is not recorded"}</p>
          {record.evaluation_source_error && <p className="note warn" role="alert">{record.evaluation_source_error}</p>}
          {assessment && <AuthoredAccount record={{ sections: [assessment] }} />}
          {issues && issues !== assessment && <AuthoredAccount record={{ sections: [issues] }} />}
          {!fidelity && !assessment && <p className="note">Implementation fidelity was not separately summarized in this saved account. Successful execution alone does not establish correctness.</p>}
          {!hasActions && <div className="implementation-delivery">{delivery}</div>}
          {!hasResources && resources}
        </ResearchCardLayout>
      </article>;
    })}
  </section>;
}
