# Phase 2: independent method proposals and cross-audit

Contract version: 3.11.4. Catalog: 1.28.4.

## Scientific purpose

Develop and compare particular methods within the requested mathematical
setting. A method supplied by the researcher receives the same formal proposal
and specialist audit treatment as independent alternatives. Catalog publication
does not select a branch or activate a method for the researcher.

## Current-state semantics

Maintain stable method identity, versioned mathematical definitions and an
attributed proposal/audit history. The current method catalog references retained
original proposal definitions. The lead comparison references proposals and
audits rather than copying or silently repairing their mathematics.

## Researcher choices and entry conditions

Current P1 literature and project instructions must be readable. The researcher
may enter optional additional P2 instructions or ideas in one field and may
select history. That field is addressed only to the Research Lead.

Every mode requires exactly one concrete candidate from each of the Research
Lead, Theorist and Data Analyst, for three candidates in total.

- full_catalog develops three methods from the current setting and literature.
- researcher_proposal additionally delivers the researcher's instructions or
  supplied idea to the lead, whose candidate should best reflect that intent.
- focused_method describes a future selected-identity revision workflow. Launch
  remains blocked because it cannot supply the required exact selected baseline.
  Using an existing method as the lead's starting point uses researcher_proposal;
  it does not activate focused_method or promise a revision of that identity.

Nonblank additional instructions or an explicit supplied-method input normalizes
full_catalog to researcher_proposal before the stage plan is frozen. The typed
supplied_method input remains supported for attribution and existing clients;
its original specification and source are retained exactly. The lead interprets
it during the ordinary proposal turn. With only general guidance or no seed,
the lead still proposes the best-aligned concrete candidate. If new instructions
withdraw an old idea, the lead follows the new direction and explains the
interpretation without attributing a new alternative to the original author.
No classifier or extra writing stage is added.

The selected-method action is labeled "Use this method as the lead's starting
point". It supplies the selected published definition to the lead while the
specialists propose independently. Preserve the exact method identity, catalog
generation and originating proposal reference beside the editable seed text.
Verify tagged selected-source references against committed generations before
any member turn, then freeze those exact source bytes as lead-directed run
inputs. Subsequent execution uses the retained sources rather than a later
catalog or a matching title. An edited seed is researcher direction; it does
not replace its original source or authorize a focused revision.

Shared trunk P2 instructions are saved under researcher/preparation/P2/trunk.json.
When that file is absent, read researcher/p2_preparation.json as the legacy
fallback. Reading does not migrate or merge drafts, and the common file wins
when both exist. The next explicit save writes the common path. Selected-method
drafts have their own preparation/P2/<method_id>.json path and never inherit the
legacy shared draft. Saving instructions does not start a run.

## Inputs and independence

All proposers receive the shared frozen research setting, relevant P1 literature
and scoped catalog. Only the lead receives the new P2 instructions or raw
supplied-method origin. Specialist input views omit P1 phase2_preparation and
researcher_origin fields without rewriting the scientific content. Project-wide
instructions and saved setting amendments remain shared. This is a routing rule
for additional P2 input, not a claim that members have never seen prior material.
The same routing applies to selected history, producing-proposal provenance and
author corrections. Current-stage proposals are not visible to peers before all
submissions close.

Saved answers with an explicit audience reach only the named members, even when
their question originated in P2. This lets shared collection facts reach the
specialists while preserving lead-only choices. Older P2 answers without an
explicit audience retain lead-only delivery. Model and version scope still
govern whether an answer applies; a matching topic never transfers it.

Cross-review gives each specialist the other specialist's exact proposal and
the lead's exact scientific proposal without its raw researcher_origin.
Neither specialist substitutes
self-review. Reviews are independent of each other's current-stage report.
The lead reconciliation receives all fixed proposals and audits, together with
the exact additional P2 instructions, and applies those instructions to its
comparison and next-work recommendations.

## Role sequence and artifacts

| Stage | Theorist | Data Analyst | Research Lead |
|---|---|---|---|
| Independent proposals | p2.theory_proposal | p2.empirical_proposal | p2.lead_proposal |
| Cross-audit | p2.theory_review | p2.empirical_review | No turn |
| Reconciliation | No turn | No turn | p2.catalog_assessment |

There are six substantive records in three stages: three proposals, two
cross-audit reports and one lead comparison. No member proposes more than one
candidate, and the lead does not invent a fourth during reconciliation.

Parallel proposals and reviews identify consequential unanswered questions in
their existing scientific fields. Proposers use assumptions, limitations and
data_requirements_markdown; reviewers use applicability_markdown and findings.
State the question, its premise, why it matters and what changes under plausible
answers, including unknown or no data. These records do not accept attention
items or a separate question artifact. Do not contact the researcher through
native host question tools or request a blocking pause during parallel stages.
The Lead consolidates these concerns into schema_version 1.2.0 attention_items
in the catalog assessment after submissions close, preserving exact proposal
and finding references and distinguishing researcher choices from team work.
Optional unknowns permit conditional work. Only a genuinely blocking question
in the eligible sequential Lead stage uses the existing durable harness pause.

The revised catalog requires the existing no-model native command/write check
for every member before research begins in each P2 stage. A failed check stops
that stage before any of its paid turns. Earlier frozen catalogs retain their
original readiness behavior.

The lead prioritizes the researcher's objective, constraints and supplied idea.
The theorist independently emphasizes principled structure, state and policy
classes, assumptions, operators and intended guarantees. The analyst independently
emphasizes feasible estimation, implementable updates, data and computational
requirements, error sources and a discriminating evaluation plan. All three
provide exact mathematics and distinguish established facts from conjectures.
Every proposer authors the complete computational profile for its own
candidate; the analyst's profile quantifies the cost drivers of the
implementable updates it specified.
P2 records P3 proof obligations and P4 simulation plans but does not execute them.

A method-proposal record has proposal_id, one complete method.schema.json
record, data_requirements_markdown, proposed_evaluation_markdown and a
computational_profile. The profile states the dominant per-iteration cost with
defined symbols, the memory footprint and the scaling with problem dimensions;
stated uncertainty is a legitimate entry, invented precision is not. The lead
proposal also preserves researcher_origin when a method seed is supplied. Authors supply exact definitions,
objectives or operators, algorithms, assumptions, source relations and intended
claims. They distinguish original researcher mathematics from P2 extensions.
No toy examples or separately rewritten display cards are required.

The existing method.summary concisely explains this candidate's purpose and
mechanism, with mathematics when needed to explain its target or mechanism.
Use proper Markdown/LaTeX and define notation where introduced. There is no fixed
sentence, line or equation count. The complete calculation-defining mathematics,
constraints, ordered algorithm and tuning remain in method.mathematical_definition;
keep that canonical definition rigorous and complete. Make the policy or model
class, essential assumptions and any approximation clear in the existing
scientific fields. Do not force a novelty claim or describe an intended guarantee
as proved, certified or solved.

The current lead-proposal schema requires one method-proposal record. Older
catalogs retain their original no-proposal branch under their pinned schema;
historical outputs are not rewritten or revalidated as new proposals.

A new proposal-audit record uses schema_version 1.2.0 and contains a separately
identified assessment for each required proposal target. Each assessment has
a concise headline identifying core support and its principal unresolved issue.
Each assessment also includes applicability_markdown for the attributed
assumptions and limitations account:
begin with when this exact method can be used, whether its conditions are
supported, not yet justified or unknown, and the main caution. For each important
condition, explain what it enables and what changes if it is absent or violated.
Distinguish an undefined procedure, loss of identification, loss of a stated
guarantee and demonstrated method failure only where supported. If the consequence
is unknown, identify what is unknown and the next argument, diagnostic or
experiment that would resolve it. The theorist emphasizes well-definedness,
identification and the scope of proposed guarantees; the analyst emphasizes
data availability, estimability, implementation, practical diagnostics and
observable failure regimes. Distinguish formal assumptions from practical
cautions. Losing a proof condition alone does not establish method failure.
When a caution is developed in a finding, cite its existing finding_id and
briefly explain its consequence for applicability instead of repeating the full
reasoning. Use existing proposal or literature IDs for source claims. Keep a
brief recap where needed for the section to stand alone; preserve independent
authorship and disagreement.
Findings have readable titles and identify the mathematical statement or
algorithm step, reasoning and consequence. Optional statement_refs are exact
JSON Pointers into that assessment's original proposal; preserve its descriptive
statement_reference and do not invent missing anchors. The theorist emphasizes coherence
and guarantees; the analyst emphasizes estimability, data, implementation and
evaluation. Either may raise any substantive issue. Both audit the authored
computational profile; thin or missing cost reasoning is challenged as a
finding. Numeric scores are not a
required artifact and cannot substitute for mathematical analysis.

The new catalog-assessment uses schema_version 1.3.0 and contains a compact
lead-authored overview_markdown, detailed comparison_markdown and one disposition
for every actual proposal_id, with retain/exclude status, method_summary_markdown
and a concise rationale. Each method_summary_markdown supplies the selected
model's concise methodological account: essential inputs, exact target and
model relationships, central estimation criterion or calculation, and returned
estimate, model or decision. Include key defining equations in proper
Markdown/LaTeX with defined symbols, keeping any model-defining constraint beside
its definition. State decisive applicability conditions and the principal
unresolved limitation; distinguish proposed benefits or guarantees from checked
results. Explain the mechanism itself, not only its motivation or a direction
to read the original proposal. Retain the essential sequence where it defines
the method without repeating the complete ordered algorithm, expanded
derivatives, numerical tolerances or full tuning details. Those details remain
in the original method.mathematical_definition, which stays canonical and
complete. No fixed word, line or equation count applies. Preserve the original
mathematics and exact source references; identify missing input facts and
specifications without inventing assumptions or silently completing missing
steps.
The overview leads with the conditional recommendation and its decisive
limitation, explains consequential differences in what the candidates compute,
and identifies the next scientific check or genuinely needed researcher choice.
Show this overview once as a concise conditional comparative conclusion, without
replaying each candidate account. Preserve consequential differences in scientific
targets rather than treating all candidates as interchangeable competitors.
Keep detailed comparison in comparison_markdown. Use human
model names and scientific descriptions in the opening prose; keep internal
record IDs, schema/catalog state and execution language in structured sources.
An overview citation can use a descriptive Markdown label linked to an exact
same-run proposal_id or review_id fragment. Finding-ID fragments do not navigate.
These links do not replace the required structured references or alter the
original sources. Each rationale is the
lead's separate scientific evaluation. Begin with a direct scientific assessment,
including the strongest reason to pursue and principal criticism or limitation.
Evaluate potential innovation relative to specifically cited work, strengths,
unresolved evidence and the next work that would settle the main issue, with
proposal, literature or finding references. A retain/exclude decision alone
does not provide this evaluation. Distinguish claimed novelty from established
differences; if novelty or the main concern cannot yet be assessed, name the
missing evidence and specific next check.
When a criticism is already developed in a specialist finding or the proposal
limitations, cite the existing finding_id or exact proposal reference and explain
how it affects the lead evaluation instead of repeating the full explanation.
Use existing literature IDs for comparisons, preserve specialist attribution and
disagreements, and keep a brief recap where needed for the review to stand alone.
These fields are authored in the existing reconciliation turn.

P2 publishes on trunk, but a model-scoped question uses the model's stable ID
as scope.branch and its complete stable ID, version and definition digest as
scope.model_ref. This applicability scope is valid before model activation;
the producing publication branch is recorded separately. Shared questions
retain project scope and their declared affected method IDs.

The same assessment authors modification_options: at least one option per
retained proposal and at most three per proposal. An excluded proposal may
carry an option when a modification would change its disposition, and if every
proposal is excluded zero options are required. Each option modifies the
candidate's own design choices and is not a new method: it names its exact
proposal in applies_to, uses an option_id of the form mod.<proposal>.<slug>,
states the exact mathematical change with defined symbols, and states the
regime or preference under which it beats the proposed form. An option never
silently edits the proposal's mathematics; the proposal record remains the
proposer's attributed account. An option needs no answer to be useful; a
choice that genuinely requires the researcher's preference remains a
researcher_decision attention item naming the affected method stable IDs.

The Lead applies the consequential input rule below before authoring a
researcher_decision. A mathematical modification option alone requires no answer.
Preserve an explicit preference within its exact scope; unresolved scientific
judgment, proof obligations and error correction remain team work. Briefly record
material Lead-owned choices and reasons in the existing comparative summary.

Optional attention items record unresolved issues. Their affected_record_ids
name exact method stable IDs from actual proposals or the frozen method catalog.
Every researcher_decision names at least one affected method, including decisions
addressed to P3 or P4. A research_task may use empty scope only when explicitly
phase-wide. Branch association is never inferred from prose or proposal IDs.
The comparison must not copy or silently edit a retained
method's definition. Substantive repair requires an explicit scientific run.

## Direct delivery

The author writes the mathematics and explanatory content once. UI displays,
cross-auditors and later method work reuse the relevant sections or exact records.
No extra summary agent or presentation-repair stage is created. Shared scientific
records use the record delivery class and are not T1 cards; old T1 size caps and
audience restrictions do not apply.

## Publication and validation

The harness deterministically extracts retained method records from the original
proposals, preserving their scientific content and proposal/audit references.
It constructs the established method_changes, catalog and decision compatibility
views without authored duplication. Publication remains atomic.

Validate distinct proposal identity, one proposal per lead and specialist, all
required cross-audit targets, complete dispositions and scope. The lead proposal
must be assessed by both specialists in every supported mode. Every submitted
proposal has a distinct method identity. The focused-method contract's future
scope rules remain defined, but readiness rejects that mode in this increment.
Every retained proposal carries at least one modification option and at most
three, and every option names an actual proposal of the run.

Stable IDs remain permanent. Mathematical revisions advance the method version
and definition digest under the existing identity rules. Researcher selection,
activation and retirement remain separate authenticated actions. Publication
cannot silently retire or choose a method.

## User interface

The Phase 2 preparation card and launch use a single field labeled
"Additional instructions or ideas for Phase 2". Explain beside it that the
Research Lead receives this input, the specialists develop independent methods,
and both specialists subsequently audit the lead candidate and one another.
Do not require a separate method-idea checkbox or structured authoring form.

Group the reader into Proposed Models, Decisions to Discuss, and Additional Runs
and History. Show the Lead overview once, each candidate's concise purpose once,
and the selected model's methodological account with its defining mathematics
and decisive conditions. Different scientific targets remain distinct. Keep the
full original formulation and algorithm, computation and tuning, independent
applicability accounts, reviews and source details accessible by expansion.
Keep the original proposer summary distinct from the lead's post-review assessment.
Readable review headlines and finding titles open their original mathematical
evidence. Historical 1.0.0 records use their original text without manufactured
headlines, overviews, source pointers or method scope.
Historical records without a concise methodological account retain an explicit
full-account fallback; the reader does not fabricate a summary or discard custom
mathematical fields outside a fixed display list. Model-specific decisions retain
their exact scope and answers. Additional runs and the consolidated history use
the existing records and explicit launch actions.
Scientific detail stays accessible by selection or expansion. A method has
no invented score or synthesized display definition. Researcher origin is
visible when applicable.

## Authoring and review for the researcher

The proposal explains inputs, ordered computation, defining equations and
outputs while retaining its exact original mathematics. Specialists assess
whether the applicability account answers what each important condition enables
and what is lost without it. The lead's concise methodological account and evaluation
remain distinct. Reviews check both scientific fidelity and whether the account
answers the researcher's question within the reviewer's permitted evidence.
No review stage certifies a later lead account; the lead checks that account
before sealing. Use brief recaps and exact references instead of repeating full
criticisms, while preserving independent opinions and consequential caveats.

## Downstream behavior

P3/P4 use an explicitly selected exact published method. Preliminary P4 may
begin before theory is complete. P5 remains tied to one selected method lineage.
Method changes preserve historical results and their original scope; no phase
launches automatically.

## Acceptance scenarios

- With or without additional instructions, each of the three members proposes
  exactly one candidate and both specialists audit the lead plus one another.
- General P2 directions go only to the lead and guide its candidate and comparison.
- With a supplied idea, the lead develops that idea as its one attributed proposal.
- Specialist input omits the new notes and raw origin but preserves the common
  setting, relevant literature and exact scientific proposals at audit time.
- A malformed or missing target assessment blocks publication.
- The UI and retained catalog preserve the original proposal mathematics.
- Using an existing method as the lead's starting point freezes its exact
  published sources and starts the ordinary three-proposal comparison. It does
  not activate the method or guarantee a revision of its stable identity.
- Focused-method launch remains blocked; unsupported revision semantics are
  never inferred from a title or editable seed.
- Legacy shared preparation is read only when the common trunk file is absent;
  new explicit saves use the common path and method drafts remain separate.
- Existing pinned projects and historical generations remain readable under
  their original contracts.


## Researcher dialogue

Use only applicable frozen context and exact answered revisions with their sources.
Keep researcher reports, supported observations, assumptions and unknowns distinct.
A confirmed paraphrase or passing diagnostic does not verify a scientific condition.
Shared facts reach applicable roles and P2 additional directions remain Lead-only.
Saved responses do not start work, revise a model or establish a guarantee.

### Consequential input under the revised catalog

Invite researcher input when plausible answers materially change the target or
interpretation, validity of the intended claim, data applicability or a meaningful
resource compromise, and the missing input is an unresolved researcher preference
or study fact the team cannot establish from available material. When that input is
useful now, the Lead consolidates and invites it through the existing owned attention
output at its designated stage even if conditional work can proceed; members propose
it in their existing owned outputs for consolidation. Explain the proposed
conditional direction, plausible alternatives and what the answer would change,
keeping any proposed default provisional until adopted. An intended use, claim to
support first or reference standard for judging success can warrant this
nonblocking invitation. Do not omit such an invitation merely because it is not a
blocker. In an eligible stage, use the existing phase mechanism to pause only when
missing input makes the next authorized action unjustified; otherwise continue
justified work with explicit conditions.

Different mathematical definitions or defensible alternatives alone are insufficient.
The Lead uses the stated goal and scientific judgment to select routine details
within the authorized scope and budget, briefly recording consequential choices and
reasons in the existing phase summary. Counting all attempted developments and
reporting declared failures is Lead-owned evaluation work. Proofs, implementation
defects, scientific justification and uncertainty procedures remain team work.

Preserve saved preferences and the requested inferential claim. A prediction goal
does not waive valid uncertainty claims or appropriate censoring assumptions.
The researcher chooses the intended claim and acceptable scope, but cannot certify
statistical assumptions by preference. Empty attention output is valid.

For each new `researcher_decision`, author `decision_priority` as `interpretation`,
`inference`, `data` or `resources`, using the highest material consequence in that
order, and `response_kind` as `choice` or `study_fact`. Urgency and an actual pause
remain separate. Keep `question` to one current choice or exact factual request.
`context_markdown` identifies the affected point. When mathematics distinguishes
the choices, show the affected problem or equation with enough formulation to
understand the decision, defining symbols and any shared objective once in that
context. For a choice, provide useful finite `options` when appropriate, usually
two or three realistic alternatives as `{id, label, consequence}` with unique IDs.
Each mathematically distinct option's `consequence` gives its formulation or changed
equation under that shared context, followed by a concise practical effect and
material benefits/costs. Prose-only options do not explain a mathematical distinction.
`likely_consequence` gives the overall practical effect without repeating the option
accounts. Plain study facts, budgets and choices without a mathematical distinction
need no artificial equation. `recommendation` is Markdown Lead advice with its reason, or a candid
statement of what is missing. Do not preselect, save a recommendation as an answer,
or invent literal researcher responses. An open-ended choice need not have options.
A study-fact request names the missing information, applicability limit and what
can proceed while unknown, without options or recommendation.

Inspect supplied material before asking. Unknown patient/event counts, encoded
feature dimension, collection and ascertainment facts remain unknown; synthetic
settings never establish them. Retain unknown facts with their applicability limits.
Defer questions without a useful current consequence; do not repeatedly request
unavailable facts. Reuse exact applicable saved answers, and reopen an answered
question only when its premise materially changes. There is no question quota.
Consolidate duplicates without merging independently answerable premises, exact
question IDs, model versions, audiences or saved answers. Carry forward only materially new
consequences in the brief; preserve full derivations and prior context through
exact sources. Legacy rationale fields need no separate repetition, and no rigid
word cap applies. Specialists propose only qualifying items in their existing
owned outputs; the Lead prioritizes and authors the final brief without another
stage or writer.

Use existing assumptions and data-requirement sections to explain target recovery and applicability in the described setting, including conditions unavailable data cannot check. Leave identification and applicability gaps explicit even when P3 is not requested.

## Scientific meaning for the intended reader

Apply the [shared question-language guidance](researcher-question-language.md) within this phase's existing output ownership and interaction rules. It refines the existing question, context, option consequences and recommendation; it adds no artifact, questionnaire or question quota.

In P2, explain what each relevant method would estimate, predict or decide and how a consequential choice changes its scientific use. Algorithm design and technical verification within the agreed goal remain team work.

## Writing duties in existing outputs

The executable objectives give the task, shared writing core, owned output duties
and separate scientific/execution constraints. Proposers explain purpose and
mechanism in `method.summary`, retain the complete calculation and constraints in
`mathematical_definition`, and keep cost, memory, scaling and honest unknowns in
`computational_profile`. Assumptions, limitations and data requirements carry
consequential premises for Lead consolidation. Review assessments state support
and consequence, distinguishing an undefined procedure, lost identification,
lost guarantee and observed failure. The Lead's `overview_markdown`, disposition
`method_summary_markdown`, `rationale` and comparison/modification fields give the
development recommendation and meaningful alternatives with decisive conditions,
proposer attribution and independent disagreement. Advice does not adopt a target
revision or invent a researcher risk preference.
