# Phase 3: Theory Development

Contract version: 2.13.2. Catalog: 1.30.2.

## 1. Purpose

Phase 3 develops the complete current theoretical account for one user-selected method. It states the estimand or target, assumptions, formal claims, proofs or proof obligations, limitations, and connections between the mathematical definition and later empirical work.

Phase 3 is parallel in pipeline status to Phase 4. It may run before or after Phase 4 and does not require Phase 4 to have run. The phase enables the user to judge what is theoretically established, what remains conditional or unresolved, and what theoretical question a rerun should address.

## 2. User choices

Before launch, the user chooses:

- One active method and its exact current version
- Establish-theory mode, which constructs the complete theory account for the authorized scope, or revise-theory mode, which revises the current theory statement by statement: repairing gaps where possible and weakening, narrowing, conditioning, or retracting claims when that is the more defensible result
- Additional theoretical or scientific instructions
- Optional current project context
- Whether to include selected historical Phase 3, Phase 4, or other run material

The Phase 3 method list is read-only. Editing or retiring methods belongs to Phase 2 or an explicit catalog action. Current aligned records are included by default. Historical records are excluded unless selected, and the history control is disabled when no history exists. After completion, the user decides whether to rerun Phase 3, run Phase 4, return to Phase 2, defer, or proceed when Phase 5 is eligible.

## 3. Prerequisites

### Targeted assessment is separate from revision

"Take another look" freezes the selected method, theory generation and
component IDs, then returns an assessment, limitations and possible next
actions using `assessment.schema.json`. The response is saved outside the
formal current theory package. It cannot alter the theory, current slots,
method definition, or start another run. A researcher may subsequently
authorize `p3.theory_revision` with the chosen instruction and exact targets.
That revision retains the full theorist, analyst audit and lead sequence.
Labels, formulas and graph dependencies resolve to the canonical statement
registry; a graph is a display projection, not a second scientific authority.

A run requires:

- A current project research brief
- A validated current Phase 1 literature basis
- A current Phase 2 method catalog
- One active selected method with an exact stable ID, version, and mathematical-definition digest

A Phase 4 record is optional. A prior Phase 3 record is optional for the first run and required as current context for a rerun when one exists. A negative or partial prior scientific outcome does not block a rerun. A retired or noncurrent method selection blocks preparation, and an older method version cannot be selected as the current target.

## 4. Frozen inputs

The run basis freezes:

- The exact selected method record, stable ID, version, and definition digest
- The current project brief and Phase 1 literature basis
- The current Phase 2 catalog generation and method provenance
- The complete current Phase 3 theory record for this exact method identity, if one exists
- The current Phase 4 evidence index, empirical synthesis, and implementation record for this exact method identity, if they exist
- Current cross-phase alignment, dependency, and unresolved-issue records
- User instructions and optional current context
- Exact historical records selected by the user
- Researcher-supplied supplementary material seeded with the run command (for example the researcher's own derivations or notes), frozen with researcher_seed provenance; additive only and never a substitute for published records
- Role instruction, knowledge, skill, and tool manifests

The run records absent sibling or prior records explicitly. Current records for a different method version are not loaded as current context and may appear only as selected history.

## 5. Role order

The role order is fixed.

1. The theorist performs the primary Phase 3 work and produces a complete candidate theory record, using the frozen current record as the basis on a rerun. In revise-theory mode the theorist revises the current theory statement by statement, repairing gaps where possible and weakening, narrowing, conditioning, or retracting claims when that is the more defensible result.
2. The data analyst receives the frozen basis and theorist output, then examines identifiability, operational meaning, computational implications, empirical testability, boundary cases, and consistency with current Phase 4 evidence when available.
3. The research lead receives the frozen project, literature, method catalog, selected method, prior theory, and available empirical basis together with both role outputs, resolves or exposes disagreements, and produces the candidate formal theory record and user decision summary.

Each handoff states what changed, which claims are supported, which assumptions remain active, which issues remain unresolved, and what the next role must verify. The fixed sequence contains no silent repair loop. If a material problem remains after analyst review, the lead reports it and gives the user an exact rerun question. The outside reviewer does not participate in Phase 3.

Handoffs carry findings, exact references, shared issue objects and next checks.
Complete derivations and repeated statement or assumption inventories remain in
their owned manuscript or audit, accessible through those references.

## 6. Run-local outputs

The active run workspace must contain:

- A complete candidate theory manuscript from the theorist, not only a change note
- A structured statement registry for definitions, assumptions, lemmas, theorems, corollaries, and unresolved proof obligations
- Proof or derivation locations for every formal claim
- A dependency map linking formal statements to the exact method definition and to one another
- The analyst's cross-disciplinary assessment with stable issue IDs
- Explicit consistency findings against available current Phase 4 evidence
- A revision account relative to the prior current theory record, when one exists
- A lead synthesis that states the current theoretical outcome and limitations
- Empirically testable implications and sensitive assumptions stated within the complete candidate theory record
- A structured user decision record with an exact rerun question

Partial or unsuccessful proof work must still produce a complete account of the currently supportable theory, including explicit unresolved obligations. Agents may not edit the formal current theory record directly.

## 7. Machine validation

Before promotion, the system verifies that:

- The required theorist, analyst, and lead outputs exist in the stated order
- Every output names the same frozen stable method ID, version, and definition digest
- The theory manuscript contains all required sections and identifies its scientific scope
- Every structured statement has a stable ID, type, exact wording, assumptions, assessment, and artifact location
- Every claimed proof or derivation link resolves to a run-local artifact
- Unresolved obligations are explicit and are not labeled as established results
- Analyst issues have unique IDs, severity classes, and dispositions or acknowledged unresolved states in the lead synthesis
- Any referenced Phase 4 evidence resolves to the frozen current evidence index
- The candidate current record is complete rather than a patch that depends on a prior manuscript to be readable
- All writes remain inside the active run workspace

Machine validation establishes structural completeness, identity, and traceability. It cannot prove a theorem, detect every hidden assumption, establish novelty, or determine whether the theoretical contribution is important.

## 8. Scientific assessment boundary

Readable assumption summaries and tables must preserve the formal premise's
scope. Measurement accuracy in recorded histories and justified bounds covering
unobserved continuation are different conditions; neither establishes that future
outcomes have been observed. The analyst checks this distinction against the
formal assumptions. An explanatory clarification is not new proof support.

The theorist owns the mathematical construction and first assessment of formal validity. The data analyst independently challenges operational meaning, identifiability, computational implications, and empirical consistency. The research lead owns the integrated scientific assessment, substantive interpretation, scope of claims, and communication of disagreement.

Each statement may be assessed as established, conditional, incomplete, contradicted, retracted, or untested. The overall theory record may be positive, partial, negative, or inconclusive while still being validly promoted. Authority as the current record means it is the latest validated account, not that every theorem is proved.

Under `p3.conservative_assessment_v1`, the Lead preserves the candidate's exact
statement registry, types, mathematical text, quantifiers, regimes, assumptions
and dependencies. Original justifications remain unchanged unless an exact
Analyst issue supplies retained negative support for that component. The Lead
may retain an assessment, withdraw it, qualify an established claim within its
unchanged scope, or mark established, conditional or untested work incomplete.
A newly contradicted claim requires the Analyst's exact counterexample or
empirical evidence with retained artifact bytes. An unreviewed Lead concern
can expose a gap; it cannot establish a contradiction or a new guarantee.
Contradicted or retracted work cannot be rehabilitated by the Lead alone.

Each actual changed assessment is attributed in `decision.assessment_changes`
with an exact component, reason and origin. Analyst origin also names its issue;
a Lead-own reason explicitly identifies the absence of independent Analyst
review. Assumption assessment may change while its wording, scope and use stay
fixed. Active means assumed, not verified in this study. Every Analyst issue
gets a reasoned resolved, contested or unresolved `decision.issue_dispositions`
entry. These responses preserve disagreement and do not imply consensus.

## 9. Promotion rule

After validation, the system atomically replaces the formal current Phase 3 record for the exact selected method identity with the complete candidate record. The promoted unit includes the theory manuscript, statement registry, dependency map, issue record, and user decision record. Role handoffs remain immutable run provenance and do not create an additional current Phase 3 slot.

A supersession event gives the previous complete generation a historical derived position, and the generation remains linked to its immutable source run. No partial merge of old and new theory is permitted. If promotion fails, the earlier complete theory record remains current.

## 10. Formal current record

The formal Phase 3 record for a method consists of:

- The complete current theory manuscript
- Exact method identity and frozen upstream basis
- The current statement and assumption registry
- Proof and derivation map
- Cross-phase dependency links
- Current unresolved issues and their scientific severity
- The current theoretical assessment
- Empirically testable implications and sensitive assumptions within the current theory record
- The current user decision record
- A manifest linking the record to its source run

Downstream work uses this complete formal record, not a collection of incremental proof fragments.

## 11. Invalidation effects

A change to the selected method's mathematical-definition digest leaves the latest Phase 3 generation current in derived position but appends an authority event that sets its derived alignment to `outdated` for the new method version. It remains available for explicit comparison but cannot support claims for the changed model in Phase 5. A successful P3 rerun for the new identity replaces it and then moves the prior generation to history.

A Phase 1 or Phase 4 change does not by itself create method-identity misalignment. It creates research attention when new literature or evidence bears on a theory claim, assumption, or scope. The dependency record identifies the affected statements for the team to assess on a user-started rerun.

Publication of a new Phase 3 record appends an authority event that marks the current Phase 5 technical report under this catalog outdated. It marks Phase 4 for research attention only when changed assumptions, claims, or empirical implications affect recorded evidence interpretation. No rerun is launched automatically.

## 12. UI projection

The theorist's complete record preserves exact statements and arguments.
`justification.summary` explains the central reasoning and remaining gap;
`assumptions[].sensitivity` directly answers what a missing condition changes.
Loss of a guarantee, loss of identification, an undefined calculation and
demonstrated failure remain distinct. An unknown consequence names the next
argument or probe instead of inventing a conclusion.

The analyst reviews operational meaning, testability and the fidelity of these
explanations within the frozen read set. The lead's decision account explains
what is established, conditional, refuted or open and why it matters. The lead
checks its final synthesis without changing unaudited statement wording.

The four reading purposes are the overall theoretical account; scientific
detail in Claims, Assumptions, Arguments and Review; unresolved issues and real
researcher choices; and further theory work. Full proofs and original sources
remain accessible, and a scientific obligation is not automatically a user choice.

The graph, statement inspector, Arguments, Assumptions and support inventory
show the current canonical assessment. When that assessment changed, a
Research Lead assessment explains why and links its exact source. The
Original theorist account is separately attributed and expandable; its proof
label is not presented as current accepted support. This same-run attribution
is separate from a comparison with an earlier published theory generation.
The reader never fabricates a reason when an old record lacks attribution.

The Phase 3 tab displays:

- A read-only list of active feasible methods from Phase 2
- A selected-method panel with purpose, mathematical definition, exact version, assumptions, and provenance
- Whether a current Phase 3 record exists for the exact method identity
- Authority and exact-method alignment
- Theoretical outcome, principal established claims, and unresolved proof obligations
- Research-attention items from new literature or Phase 4 evidence
- What changed in the current theory record
- The exact question a rerun would answer
- Controls for instructions, optional context, and selected history
- A user-controlled Run or Rerun action

Alignment, scientific outcome, and research attention are displayed separately. A partial outcome is not presented as a storage or system failure.

## 13. Acceptance criteria

- Given an active method with no Phase 3 record, when a valid run is promoted, then one complete current theory record is created for that exact method identity.
- Given an existing current theory record, when a rerun is prepared without history selection, then the complete current record is frozen and older run workspaces are excluded.
- Given a valid rerun, when promotion succeeds, then the new complete theory generation replaces the current-index slot and a supersession event gives the previous generation a historical position.
- Given a current aligned Phase 4 record, when Phase 3 runs, then its identity and synthesis are available to the analyst and lead through the frozen basis.
- Given no Phase 4 record, when Phase 3 runs, then preparation succeeds and the missing sibling record is explicit.
- Given a changed method definition, when the catalog version is promoted, then the earlier Phase 3 record cannot satisfy current alignment for the new version.
- Given an incomplete proof, when the record labels the obligation accurately and satisfies the complete-account contract, then it may be promoted with a partial or inconclusive scientific outcome.
- Given a claim labeled established with no proof location, when validation runs, then promotion is rejected.
- Given an interrupted or failed promotion, when the project is read, then the earlier complete theory record remains current.
- Given a successful run, when next actions are displayed, then the system waits for the user's choice and starts no sibling or downstream phase.


## Researcher dialogue

Use only applicable frozen context and exact answered revisions with their sources.
Keep researcher reports, supported observations, assumptions and unknowns distinct.
A confirmed paraphrase or passing diagnostic does not verify a scientific condition.
Shared facts reach applicable roles and P2 additional directions remain Lead-only.
Saved responses do not start work, revise a model or establish a guarantee.

### Consequential input under the revised catalog

Use the catalog's [user-inquiry reference](../references/research-presentation/user-inquiry.md)
for consequential filtering, overlap consolidation, concise mathematical choices,
the new primary inquiry ceilings and suggestion-first options. The reference bytes
are delivered from the frozen catalog; this link is not a substitute for delivery.
The designated Lead consolidates member proposals against open items and exact
applicable saved answers. Keep independently answerable inputs, source history and
one effective-answer location. Zero new inquiries is valid.

New researcher items retain `decision_priority`, `response_kind`, exact scope and
audience. A justified choice suggestion is first, with `recommended_option_id`
bound to its stable option ID and a short reason in `recommendation`; nothing is
preselected. Study facts use free text/unknown without options or recommendation.
The ceilings apply to new inquiry prose only, not scientific accounts, user answers,
requested discussions or old records. Rewrite rather than truncate or split a
decision. Actual run/request state determines optionality and pauses. This adds no
stage, output duty or pause authority.

The Lead owns routine scientific choices, all-attempted accounting and failure
handling within the agreed target and budget. Scientific defects, proofs and
diagnostics remain team work; a researcher cannot verify assumptions by preference.
Preserve the requested claim and applicable saved answers. Useful optional input
can be invited while justified conditional work proceeds.

A separate P3 package is required only for report claims depending on new formal results. Existing results require retained theorist applicability checks; unchecked conditions and nontrivial new arguments remain qualified or route to mathematical work.

Theorist and Analyst nonblocking questions belong in their ordinary handoffs,
with the question, decision value, plausible answers and consequences. The
Lead consolidates them into its owned schema 1.2 attention collection, with
exact scope and audience. Specialists do not author an unassigned attention
artifact. A genuinely blocking missing fact or choice uses the existing
researcher-question.json pause; native host questions are not used. Unknown
facts can remain explicit conditions when work can proceed responsibly.

## Scientific meaning for the intended reader

Apply the [shared question-language guidance](researcher-question-language.md) within this phase's existing output ownership and interaction rules. It refines the existing question, context, option consequences and recommendation; it adds no artifact, questionnaire or question quota.

In P3, connect an assumption to the specific claim it supports and its meaning in the study. Ask for relevant study information, never for permission to treat an assumption as true. Missing proofs and numerical correctness remain team work.

## Writing duties in existing outputs

The executable objectives give the task, shared writing core, owned output duties
and separate scientific/execution constraints. The decision,
`phase_summary.evaluation_markdown` and `theory_compact.summary_markdown` interpret
the supported result and practical boundary in the supplied study. Clearer prose
cannot rewrite audited statement text, quantifiers, assumptions or proof support.
For example, a sufficient finite stationary state keeps those qualifications.
Existing theory summaries and audits explain what is supported and what loses
justification, without turning absence of a proof into demonstrated failure.
Proposed next work remains a conditional recommendation within its stated scope;
prioritization does not authorize or launch another run.

## Shared notation and presentation (catalog 1.30.0)

Theorist and Analyst use the exact method snapshot and retain proof-local definitions. The existing Lead complete theory account adopts recurring account-scoped additions without changing upstream study or method mathematics.

The five neutral presentation references apply through `research_presentation_v2`; shared notation is separately gated by `project_notation_v1`, which requires v2. Keep full measure definitions beside results and actual resource measurements outside mathematical notation. This adds no stage, output family or scientific authority. Retained catalogs preserve their original routing and historical local fields.
