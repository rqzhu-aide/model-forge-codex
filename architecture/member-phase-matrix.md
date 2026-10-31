# Member × Phase Matrix — what each role produces and reads

The master reference for the harness. Normative together with
`SPEC-context-and-artifacts.md` and `system_artifact_types.md`; decisions
are recorded in [decisions/](decisions). Role responsibilities were reconciled
with catalog 1.16.0 on 2026-10-11; the P1 reader mapping below reflects catalog
1.23.0/P1 3.6.0 on 2026-10-13. The pinned phase contracts define the exact required output IDs.

Every applicable member receives the same frozen effective problem context,
including explicitly authorized continuation amendments. Exact question answers
retain their declared scope and audience. Shared P2 context is distinct from
additional directions or candidate preferences delivered only to the lead.

Under catalog 1.26.0, specialists propose only consequential unresolved researcher
preferences or essential missing study facts. The Lead filters and consolidates
them, preserving established goals and exact saved answers. A choice reaches the
researcher only when scientific judgment within the agreed scope cannot settle it.
The Lead owns routine evaluation and failure reporting. New attention carries
`decision_priority`, `response_kind`, a compact affected-point explanation and
practical consequence. When alternatives are useful, `options` supplies exact
selectable IDs, labels and consequences, and `recommendation` supplies Lead advice.
Study facts receive no invented preference options. P5 retains editorial-only
questions. No extra author, summarizing stage or decision artifact is introduced.

Delivery classes: **I** = inline in brief · **I\*** = mention + instructed
open · **M** = mention (T0) · **N** = never delivered.

## Shared notation and presentation, catalog 1.30.0

The existing five neutral references reach relevant P1-P5 authors through
`research_presentation_v2`, within their current scientific and inquiry duties.
P5 reviewers and the revision Lead read neutral editorial guidance from the
frozen submission packet; report-section discussion gains no upstream inquiry.
The [presentation matrix](research-presentation.md#delivery-and-ownership)
supersedes the earlier v1 P4-only scientific-guidance routing for adopted v2 runs.

`project_notation_v1` requires v2. Members receive the admitted frozen notation
and define additions in existing scientific fields. Only the existing Lead
outputs below adopt `notation_updates`; the harness generates the complete final
lookup and seals its supporting files. No output family or stage is added.

| Existing Lead output | Owned notation |
| --- | --- |
| P1 research basis | Shared study definitions |
| P2 catalog assessment | Exact method/candidate definitions and mappings |
| P3 complete theory | Recurring theory-account definitions, retaining proof-local exceptions |
| P4 empirical synthesis | Evaluation-account additions, retaining method/theory definitions |
| P5 technical report candidate/revision | Report exposition and explicit source-symbol mappings |

P2 keeps independent candidate and Lead-only input boundaries. Later phases do
not rewrite upstream canonical mathematics. Independent reviewers receive the
submitted report's notation only; targeted discussions use the selected source's
final account view. Historical records retain their own local notation. See the
[source and scope design](shared-notation-plan.md).

## P1 literature_update (trunk)

| Stage and role | Produces | Reads |
|---|---|---|
| Discovery: Research Lead | One `p1.lead_literature` collection emphasizing formulations, research traditions and central sources | Same frozen setting, current literature, supplied material and instructions; no current peer collections |
| Discovery: Theorist | One `p1.theory_literature` collection emphasizing exact statements, assumptions and validity conditions | Same frozen inputs; no current peer collections |
| Discovery: Data Analyst | One `p1.empirical_literature` collection emphasizing existing algorithms, information, computation and reported empirical evidence | Same frozen inputs; no current peer collections |
| Reconciliation: Research Lead | One `p1.research_basis`, including scoped scientific review, targeted entry corrections and framework synthesis | Navigation index and exact entry retrieval over all three fixed collections plus the frozen current basis |

Four substantive records. Each paper entry holds its source, exact mathematics,
explanation, relevance, limitations, evidence locations and explicit reading
extent in schema 1.1.0. Search scope and
coverage are recorded once per collection. The research basis supplies the
requested setting, P2 preparation, optional supplied-method seed and cross-paper
landscape. The same fields serve the UI and later members directly, with no
companion T1 card or T2p/T2s rewrite and no T1 formula or byte cap.

The lead may correct affected scientific fields from any current entry in its
ordinary reconciliation turn, including retained prior entries. Each correction
names the original role, family, run, entry and digest. Deterministic application
preserves source/entry IDs, original authorship, unaffected fields and immutable
history, while recording the Research Lead as reviser. No specialist scientific
follow-up is scheduled. Frameworks, variants, relationships and algorithm families
link to the effective corrected entries shared by the UI and P2. Review scope and
uncertainty remain explicit; no model-authored status certifies mathematical truth.

The catalog 1.6 basis represents each setting clarification once in
attention_items as researcher_decision targeted to P1, with the author's exact
mathematical context and sources. Method, proof and simulation work are
research_task items assigned to P2/P3/P4. They are read as frozen context by
the corresponding next user-started run. Every phase authors contextual 1.1.0
attention and records explicit dispositions of existing tasks when warranted;
omission does not resolve them. No additional member turn is introduced.

## P2 method development (trunk)

| Stage and role | Produces | Reads |
|---|---|---|
| Independent proposal: Research Lead | One `p2.lead_proposal`, aligned with the researcher's objective, directions and supplied idea | Shared scientific basis plus exact additional P2 instructions or supplied-method input when present; no current peer proposal |
| Independent proposal: Theorist | One `p2.theory_proposal`, emphasizing mathematical structure, assumptions and guarantees | Frozen P1 setting and relevant literature, shared project instructions and scoped catalog; no additional P2 instructions or raw supplied-method origin |
| Independent proposal: Data Analyst | One `p2.empirical_proposal`, emphasizing estimation, data requirements and practical computation | Same frozen inputs; no current peer proposal |
| Cross-audit: Theorist | One `p2.theory_review` | Analyst's and lead's fixed proposals; frozen scientific basis |
| Cross-audit: Data Analyst | One `p2.empirical_review` | Theorist's and lead's fixed proposals; frozen scientific basis |
| Reconciliation: Research Lead | One `p2.catalog_assessment` | All fixed proposals and audits plus frozen scientific basis and the exact additional P2 instructions |

Six substantive records in all P2 modes: three proposals, two audits and one
catalog assessment. Each proposing member independently develops exactly one
actual method; all proposals remain mathematically specified and operationally
complete despite their different emphases. Each audit contains separate target
assessments for the other specialist and the lead. The lead compares all three
and retains/excludes by proposal ID without rewriting method definitions or
introducing a fourth method. No scoring matrix or duplicate display summary is
required. Historical pins retain the older optional-lead behavior.

The UI offers one "Additional instructions or ideas for Phase 2" field with
explicit save and mathematical preview, and explains that it goes only to the
lead. Its researcher-store draft is distinct from published P1 notes and the
shared setting; the visible text freezes as run instructions on submission.
Specialist views omit P1
`phase2_preparation` and raw `researcher_origin`, preserving exact scientific
content. The typed seed remains a compatibility input. After independent
submissions close, specialists audit the lead's scientific proposal.

The records are shared scientific artifacts. UI renders the same formulation,
data requirements, proposed evaluation, audit findings and comparison that
later scientific consumers read. Focused-method execution remains unavailable. Selecting a method as the lead's
starting point freezes its exact catalog definition and original proposal when
available. It starts a proposal and comparison run with independent specialist
candidates, without promising an identity-preserving method revision.
Run publication and explicit researcher method selection remain separate.

The lead's `overview_markdown` answers what the comparison established;
`method_summary_markdown` explains the procedure and equations, and `rationale`
evaluates innovation and criticism. Specialist `applicability_markdown` explains
conditions, cautions and violation consequences. These fields serve distinct
research questions within the same six records, not additional summaries.

## P3 theory_establishment (method branch)

Reruns freeze the current theory generation. Any aligned current P4 evidence,
synthesis and implementation are available to the relevant specialists and
lead. A graph assessment returns options without changing this generation;
repair requires a separate researcher-authorized theory-revision run.

| Role | Produces | Reads |
|---|---|---|
| theorist | theory candidate (T3m: notation/assumptions/definitions/lemmas/theorems/proofs/validity boundaries/false-as-stated register); claim map; falsification log; theory packet (T2p → lead, analyst); notebook | exact selected proposal and catalog assessment (I\*); current theory and aligned empirical context when present; legacy P2 decision/T2s when the pin requires them; own notebook (I) |
| data_analyst | audit packet (T2p → lead, theorist); audit manuscript (T3m, checking methodology); notebook | theorist's theory packet (I); theory manuscript (I\*); P2 decision (I); own notebook (I) |
| research_lead | complete theory and compact account without unaudited statement changes; **P3 T2s**; decision record; contextual attention | both packets (I); theory + audit manuscripts (I\* at reconcile); exact selected-method basis and available empirical context; own prior synthesis where declared |

The theorist explains each claim's meaning and remaining proof obligation,
and what the absence of each assumption changes. Missing proof does not imply
demonstrated failure. The lead's overview states what is established,
conditional, refuted or open, preserving attributed criticism and uncertainty.

## P4 empirical_evaluation (method branch)

Feasibility checks (`p4.preliminary`) can precede P3 or use incomplete theory.
The P3 inputs below are delivered when present and aligned, not prerequisites.
Both empirical scopes retain analyst, theorist audit, and lead stages.
Reruns include the current cumulative evidence and implementation.

Catalog 1.25 adds an ordered workflow: choose package/adaptation/custom route;
deliver portable model and synthetic example; verify code and exported execution;
evaluate relevant performance and apply to selected local data; independently
audit; consolidate findings and researcher decisions. This reuses the existing
eight analyst and fifteen total outputs. Protocol cases declare source identity
and replication unit; the final actual-data disposition belongs to the analyst.
The lead selects exact headline exhibit IDs for the Numerical Results Summary.

| Role | Produces | Reads |
|---|---|---|
| data_analyst | protocol; evidence; per-replicate rows; diagnostics and exhibits; typed question results in analyst synthesis; implementation account; handoff; retained code, configuration and result files; notebook | exact P2 method and research intent; literature basis; applicable current evidence and implementation; aligned P3 theory and synthesis when available; own notebook |
| theorist | method-fidelity and interpretation audit; handoff; notebook | exact method; analyst implementation account, protocol, evidence, synthesis, rows, diagnostics and exhibits; available aligned theory |
| research_lead | current evidence index; empirical synthesis with `decision_summary` and attributed `question_reviews`; **P4 T2s**; decision record and contextual attention | frozen scientific basis; all analyst outputs and theorist audit; applicable prior empirical records |

Feasibility covers faithful implementation, a small controlled example,
a meaningful baseline comparison and measured cost. Detailed evaluation
(`p4.comprehensive`) first plans comparisons relevant to the intended benefit,
computational cost, tuning, sensitivity, assumptions and reliability. The
analyst saves the protocol, runs bounded comparisons, checks time and results,
and records prospective amendments. Severe validity concerns or consequential
researcher choices pause the run. Reviewers can also request a pause; no member
repairs the mathematical method or automatically starts another phase.

Question results state the direct answer, magnitude and units, uncertainty,
usable repetitions, conditions, limitation and decision implication. A completed
quantitative answer has a verified plot/table or an inline table from checked
diagnostics. Exact numerical values and failed, invalidated or unperformed work
remain available. The lead reports what code ran, its correspondence to P2,
and whether theory was unavailable, available but untested, or specifically
tested. Numerical agreement is not a proof. Finishing with partial evidence
still requires the remaining audit and lead stages.

## P5 technical report (one selected model branch)

Assembly runs the lead only. Review-revision freezes one technical report, runs
the three reviewers in parallel, then gives all fixed reviews to the lead.
T1 cards remain UI-only. The review packet is harness-prepared from the
report and declared scientific support, plus the exact researcher review focus
and submitted problem/model scope. All three reviewers and the revision lead read
these frozen directions. Corrections retain the same packet. The outside reviewer has fresh
context and no internal records, notebooks, handoffs, or earlier reviews.

| Role | Produces | Reads |
|---|---|---|
| research_lead | technical report draft and revisions (`t3m_report`, advisory source size); revision account; decision records | phase accounts; exact selected-model sources and current report; fixed review packets; own notebook |
| theorist | review packet (T2p → lead) | frozen report; selected model, available theory, implementation and literature from the explicit role read set |
| data_analyst | review packet (T2p → lead) | frozen report; selected model, available numerical support, implementation and literature from the explicit role read set |
| outside_reviewer | outside review packet (T2p → lead) | **only the frozen reviewer packet**; no internal project material or memory |

The lead also authors claim traceability, the upstream basis manifest, citation
integrity and limitations records. Readers distinguish the exact reviewed draft
from a later revision and link central claims to frozen support, counterevidence
and assumptions. Reviews explain consequences and resolving work. A TeX source
artifact is not represented as an already rendered report or PDF. Relevant
numerical evidence is necessary for complete status; a separate P3 run is needed
only when the actual mathematical claims require it. Historical manuscript
contracts retain their own declarations in projects that have not adopted 1.16.0.

## Continuous carriers (every stage, every member)

| Carrier | Direction | Type |
|---|---|---|
| notebook update | self, next invocation (per member × branch, D1) | T2p-self (I, always) |
| rotation handoff | own successor thread (once) | T2p-self (I once) |
| attention items | lead, P5, researcher | T2p (structured) |
| Codex native memory | per (member × project) home; harness does not interfere (D10) | Codex-managed |
| per-turn token ceiling | only if the researcher sets it in the UI (D9) | harness control |

## UI rendering summary

P1 uses five cards; P2-P5 retain four reading purposes. Cards use the existing
authors' scientific outputs and researcher controls, not an extra set of member
files. The [UI contract](design/07-ui-contract.md) owns current order and action placement.

| Phase | Overview | Scientific detail | Issues and decisions | Further work |
|---|---|---|---|---|
| P1 | Research Setting, then Main Findings | Explore Individual Papers; full mathematics and notation on demand | Decisions to Discuss, before the paper reader | Additional Runs and History |
| P2 | What the team found | Method, assumptions, computation, review | Choices and unresolved findings for the selected method | Further method development |
| P3 | What is established about this method | Claims, assumptions, arguments, review | Open obligations and researcher direction | Further theory development |
| P4 | Numerical Results Summary | Implementation and Code; Experiments and Results with data selector and criterion strip | Decisions to Discuss, including implementation concerns and paused-run answers | Additional Runs and History |
| P5 | Current report conclusion | Technical report, supporting evidence, reviews, changes | Review concerns, problem understanding and researcher direction | Next revision |

Existing authors write these explanations in their ordinary producing stages;
reviewers check explanatory adequacy within their permitted sources. The
researcher can edit saved answers, use Explain more against exact sources, and
save further-work instructions without starting a run. Historical source and
publication details remain secondary. Missing content stays explicitly missing;
the UI does not reconstruct scientific claims.
