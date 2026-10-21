import React from "react";
import { humanLabel } from "../research";
import { SourceRef } from "./Shared";
import ResearchDocument from "./EmpiricalDocument";
import { ActionIcon } from "./Visuals";

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

export default function ImplementationReading({ records = [], protocols = [], summary, onSource }) {
  const fidelity = summary?.decision_summary?.method_fidelity_markdown;
  return <section className="empirical-implementation">
    {fidelity && <section className="implementation-assessment"><h3>Implementation assessment</h3><ResearchDocument text={fidelity} /><SourceRef reference={summary.generation_ref && { ...summary.generation_ref, entry_pointer: "/decision_summary/method_fidelity_markdown" }} onOpen={onSource} label="Assessment source" /></section>}
    {!records.length && <p className="note">No separate implementation record is available for this evaluation. Code correspondence and retained checks cannot be established from successful execution alone.</p>}
    {records.map((record, index) => {
      const reproduction = record.reproduction;
      const strategy = record.implementation_strategy || (record.generation_ref?.run_id && record.generation_ref?.package_id && protocols.find((protocol) => protocol.generation_ref?.run_id === record.generation_ref.run_id && protocol.generation_ref?.package_id === record.generation_ref.package_id)?.implementation_strategy);
      const sections = record.sections || [];
      const assessment = !fidelity && sections.find((section) => ["correspondence", "fidelity", "rule"].includes(section.key));
      const issues = !fidelity && sections.find((section) => section.key === "limitations");
      return <article className="scientific-block" key={record.generation_ref?.generation_id || index}>
        <p className="note">{AUTHORS[record.producer_role] ? `Implementation account by ${AUTHORS[record.producer_role]}` : "Implementation account author is not recorded"}</p>
        {record.evaluation_source_error && <p className="note warn" role="alert">{record.evaluation_source_error}</p>}
        {assessment && <AuthoredAccount record={{ sections: [assessment] }} />}
        {issues && issues !== assessment && <AuthoredAccount record={{ sections: [issues] }} />}
        {!fidelity && !assessment && <p className="note">Implementation fidelity was not separately summarized in this saved account. Successful execution alone does not establish correctness.</p>}
        <div className="implementation-delivery">
          {record.bundle_error ? <p className="note warn" role="alert">The source bundle is unavailable: {record.bundle_error}</p> : record.bundle_url && reproduction?.status === "available" ? <a className="btn ui-action" data-ui-role="system" data-action="source" href={record.bundle_url}><ActionIcon name="source" />Download code and example bundle</a> : <p className="note">{reproduction?.status === "unavailable" ? "Portable delivery is unavailable." : "No verified code and example bundle is available in this record."}</p>}
        </div>
        <details className="research-details empirical-implementation-details"><summary>Full implementation, verification and dependencies</summary>
          {strategy?.route && <section className="implementation-route"><h3>{{ package_reuse: "Use a package", package_adaptation: "Adapt a package", custom_implementation: "Custom implementation" }[strategy.route] || humanLabel(strategy.route)}</h3><ResearchDocument text={strategy.route_rationale} /></section>}
          <AuthoredAccount record={{ ...record, body_md: [assessment, issues].some((section) => section?.body_md?.trim() === record.body_md?.trim()) ? "" : record.body_md, sections: sections.filter((section) => section !== assessment && section !== issues) }} />
          {reproduction && <section className="implementation-reproduction"><h3>Model code and synthetic example</h3><DeliveryFiles record={record} /><ResearchDocument text={reproduction.invocation} />{reproduction.runtime_identity && <><h4>Shared runtime</h4><ResearchDocument text={reproduction.runtime_identity} /></>}{reproduction.dependencies?.length > 0 && <><h4>Dependencies</h4><ul>{reproduction.dependencies.map((item, dependencyIndex) => <li key={dependencyIndex}>{item.name} {item.version}{item.source && <> · <ResearchDocument text={item.source} /></>}</li>)}</ul></>}</section>}
        </details>
        <details className="research-details implementation-files"><summary>All saved files and checks</summary>{record.files?.length ? <ul>{record.files.map((file, fileIndex) => <li key={`${file.path}:${fileIndex}`}><b>{file.label || humanLabel(file.kind || "Implementation file")}</b>{file.artifact_url && file.source_verified !== false ? <span className="btnrow"><a className="source-link ui-action" data-action="source" data-ui-role="system" href={file.artifact_url} target="_blank" rel="noreferrer"><ActionIcon name="source" />Inspect saved {humanLabel(file.kind || "file").toLowerCase()}</a>{file.download_url && file.source_verified === true && <a className="source-link ui-action" data-action="source" data-ui-role="system" href={file.download_url}><ActionIcon name="source" />Download {file.label || humanLabel(file.kind || "file").toLowerCase()}</a>}</span> : <p className="note warn">{file.source_error || "The saved file could not be verified."}</p>}{file.path && <details className="research-details"><summary>File identity</summary><code>{file.path}</code>{file.sha256 && <p className="note">SHA-256: <code>{file.sha256}</code></p>}</details>}</li>)}</ul> : <p className="note">No verified code, configuration, environment or check files are linked in this record.</p>}</details>
        <details className="research-details implementation-review"><summary>Theorist assessment</summary>{record.theorist_review ? <><p className="note">Independent assessment by Theorist · Same evaluation</p><AuthoredAccount record={record.theorist_review} review /><SourceRef reference={record.theorist_review.generation_ref} onOpen={onSource} label="Theorist assessment source" /></> : <p className="note">No theorist assessment is linked to this exact evaluation.</p>}</details>
        <SourceRef reference={record.generation_ref} onOpen={onSource} label="Implementation source" />
      </article>;
    })}
  </section>;
}
