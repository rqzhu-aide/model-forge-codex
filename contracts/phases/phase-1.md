# Phase 1: research setting and literature landscape

Contract version: 3.9.1. Catalog: 1.30.1.

## Five-card reading contract

The researcher reads Research Setting, Main Findings, Decisions to Discuss,
Explore Individual Papers, and Additional Runs and History in that
order. The four authored records and two-stage execution remain unchanged.

The Lead's research basis uses schema 1.3.0. Research Setting contains separate
brief study and goal accounts in connected prose. statement_markdown describes
the study problem, essential observations or conceptual objects, and contextual
notation. research_goal_markdown interprets what the researcher wants to learn,
predict, compare, estimate or establish and what a useful result would answer.
A simple target expression may clarify the goal. Research Setting does not
require a full model specification or methodological development. Detailed
formulation of each proposed project method belongs in P2. Keep the account
sufficient to orient the researcher without a fixed word or paragraph quota;
do not prescribe an unchosen model family, architecture or estimator.
Distinguish a target from its estimating procedure and report deliverable, and
prediction or association from intervention effects. Unknown choices remain
symbolic or explicitly labeled alternatives; do not silently choose a time origin, horizon,
loss, policy or identification assumption. Neither account repeats the literature,
inventories methods or lists questions. component_interpretations supplies short
notation definitions for optional lookup, not the only explanation of visible
symbols. Missing data and unknown collection facts remain explicit.
Goal ambiguities belong in Decisions to Discuss. The setting and landscape
remain shared with later specialists; phase2_preparation keeps its existing readers.

Main findings is a concise thematic cross-paper synthesis in landscape.summary_markdown,
with [Author, year](#cite:source.id) citations and the central mathematical
distinction or relationship when needed to understand the landscape. Explain how
the approaches address the problem and what their assumptions permit or leave
unresolved; integrate equations where they clarify that account. Do not replace
the synthesis with model names or disconnected formulas;
do not duplicate every selected approach. Each citation_refs binding names
the exact effective member entry and SHA-256 digest. Index references identify
pre-reconciliation entries. When correcting an entry, compute the effective
digest after applying changes, using SHA-256 of UTF-8 json.dumps(entry,
ensure_ascii=False, sort_keys=True, separators=(',', ':')). Review and correction
targets continue to identify the original entry. Citation previews and readers
use the bibliography and correction provenance of the synthesis's own publication.

overview_item_ids selects useful existing mathematical records. A selected
explanation_markdown is connected methodology-style prose explaining the
approach's target, modeled relationships and central mechanism or estimation
strategy. Integrate informative source-supported mathematics with its terms and
decisive conditions interpreted in context;
project_relevance (direct, conditional or background) and
relevance_reason_markdown give a short fit reason. Extended formulations,
derivations and exact support remain inspectable. The visible account must be
methodologically understandable without opening details. Author common_assumptions only when shared conditions
clarify the project beyond object-local assumptions, with exact references.
Default this required array to empty when local conditions suffice.
Proximity to a problem does not establish an assumption or comparative superiority.

The member paper fields directly supply Explore Individual Papers, retaining
one attributed assessment at a time. explanation_markdown is the visible paper
summary: concise, connected methodology-style prose describing this source's
actual model, formulation or method. Explain what it models or estimates and
how it works, including the source-supported defining relationships, criterion,
update or construction needed to understand it. Interpret LaTeX symbols and
decisive conditions in context. A broad family account, method name or notation
list is insufficient. The visible summary must be understandable without opening
details. formulation_markdown retains fuller definitions, assumptions and
derivations; it must not be the only place containing the defining mathematics.
Concision removes repetition, not the source-specific methodological explanation.
Do not force a formula for a nonmathematical contribution or invent unavailable
source mathematics. Consequential questions use existing
attention, scope and conversation records. Analyst data_profiles travel with
the frozen collection index to the Lead and remain in source/run details.
Additional Runs and History combines explicit literature-update controls,
saved instructions, team tasks, search scopes and retained dated accounts.
Saving instructions does not start work. Historical content stays complete
through labeled details; no display writer, clipping or shortened-record rewrite
is required. The producing package's immutable metadata.catalog_pin determines
whether the basis or individual assessment uses the concise writing contract
introduced in 1.23.0, the visible mathematics guidance in 1.23.1, or the
methodology-style clarification in 1.23.2, completeness clarification in 1.23.3,
or brief-setting and source-specific paper clarification in 1.23.4.
Missing or unrecognized provenance remains legacy/unknown; adopting a new
catalog does not rewrite historical research.

phase2_preparation.instructions_markdown remains required and nonblank, with
only additional P2-specific preparation and attributed supplied-method material.
Do not repeat the study, goal or findings. When there is no addition, use
"No additional P2-specific preparation is identified."

## Scientific purpose

Establish the requested problem context and a cumulative landscape of
relevant literature. P1 identifies what published sources formulate, establish,
assume and leave unresolved. It does not investigate a particular project
method's validity, development or performance. Even a method supplied in the
researcher's manuscript remains an attributed seed for P2.

## Current-state semantics

The current library retains sources and attributed member assessments across
runs. The latest research basis supplies the requested setting, preparation for
P2, exact framework synthesis, scoped scientific review and coverage. The lead
can directly correct targeted scientific fields in current paper entries during
ordinary reconciliation. Corrections preserve original authorship and record
lead revision provenance; original submissions remain immutable history.
Absence from a later update
does not delete a source. Exclusion or retraction requires an explicit source
disposition with a reason. Prior generations remain inspectable.

The established literature_synthesis, literature_coverage and phase_decision
slots are deterministic compatibility views. They do not require additional
member-authored summaries or create scientific text.

Run details show the current package's three independent member scopes together,
with the publication date and actual reading limits. Earlier scopes remain in
dated history with exact sources. A legacy scope without a reliable date or
package association stays explicitly unverified. Papers searches the cumulative
library; an older entry remains useful unless its recorded scientific status
changes. Library counts and update bookkeeping belong in run details.

Work status is a read-only view of the frozen stages, recorded stage states,
execution records and output seals. A received account is distinct from a stage
accepted after delivery checks. A failed update leaves retained results readable
and does not certify or reject their scientific conclusions.

## Researcher choices and entry conditions

A readable current project brief is required. The researcher chooses broad or
focused search scope and run instructions; selected history is optional.
Researcher-supplied material supplements, rather than replaces, literature.

The Study goal action in Research Setting opens the project-context editor for
goal correction or discussion. A saved correction retains its exact
published goal source, researcher attribution and context item identity, and
is indicated beside the immutable Lead paragraph. The actual correction is
readable in Decisions. Subsequent runs receive saved context and provenance;
an active run keeps its frozen account. Saving makes no model call or new run.

## Inputs and independence

All three discovery members receive the same frozen current project brief,
available library, prior synthesis and coverage, supplied material and run
instructions. Discovery members cannot read one another's current-stage
collections before all three finish. The lead reconciliation receives all three
fixed collections and the same frozen basis through an entry navigation index
and exact selected-entry retrieval, rather than three full JSON bodies inline.
Common objectives are supplemented by role_objectives: the lead emphasizes
formulations and research traditions, the theorist exact statements and validity
conditions, and the analyst existing algorithms, information, computation and
reported empirical evidence. These are overlapping emphases, not paper quotas.

## Role sequence and required artifacts

| Stage | Author | One required deliverable |
|---|---|---|
| Independent discovery | Research Lead | p1.lead_literature |
| Independent discovery | Theorist | p1.theory_literature |
| Independent discovery | Data Analyst | p1.empirical_literature |
| Reconciliation | Research Lead | p1.research_basis |

Each new collection follows literature-findings.schema.json version 1.2.0. It records search
scope and coverage for this member's search in this update once, then paper entries with complete source identity,
exact relevant mathematical formulation, explanatory prose, relevance,
limitations and evidence locations. reading_extent is required and distinguishes
material actually read and claims checked from findings merely reported by a source.
Use Markdown with LaTeX; define notation and necessary assumptions. Do not
invent inaccessible mathematics or replace it with toy examples.

The new basis follows research-basis.schema.json version 1.3.0: research_setting,
phase2_preparation, landscape, coverage_limits, scientific_review and
entry_corrections. Optional supplied_method
contains title, specification_markdown and source_reference, faithfully
attributed to the researcher. Optional source_dispositions and attention_items
record substantive unresolved issues without separate duplicate outputs.

The landscape contains only useful frameworks, variants, relationships and algorithm_families
with exact formulation, assumptions, explanation, entry references, scoped support
status and limitations. Keep required topics minimal or empty. Variants name a
parent framework and mathematical changes; relationships name endpoints and their
conditions; existing algorithms name their frameworks and computational needs.
An unavailable comparison remains unresolved instead of receiving invented math.
Landscape equations describe existing source-supported formulations. Do not
invent a new model or architecture to fill an evidence gap. The Lead may define
shared conceptual targets as clearly attributed interpretations; these are not
literature findings or a new model selected in P1.
Required arrays may be empty when scientifically appropriate: topics, framework,
variant, relationship and algorithm inventories, overview selections, common
assumptions, glossary, review findings/limits, corrections and coverage limits.
Keep all required containers and nonblank text. Empty citation_refs is appropriate
only without inline citation links. Selected source-supported or partially-supported
records still need exact supporting entry references.

The lead checks central claims and source fidelity and records the actual scope
and limits in scientific_review. It checks that visible paragraphs explain the
scientific relationship and method, agree with the fuller formulations, clarify
their symbols and decisive conditions, and do
not confuse a defined target with an identified or established result.
It authors any targeted correction itself in
entry_corrections, with exact original role/family/run/entry/digest, changed fields,
reason and evidence. Allowed fields are formulation_markdown, explanation_markdown,
relevance_markdown, limitations_markdown, evidence_locations, topics and
reading_extent. Source and entry identities are immutable. The harness applies
the authored content deterministically; no return-to-author scientific turn,
separate review artifact or extra synthesis round is required.

Each new attention item uses schema_version 1.2.0. The original author supplies
kind, target_phase and context_markdown in the same ordinary deliverable.
The context identifies the exact affected point with the minimum useful mathematics,
locally defined symbols and sources. Keep the practical effect in likely_consequence,
with derivations and earlier context available through exact source references.
Do not invent mathematics merely to fill a field.

Setting clarifications appear once in basis.attention_items as
kind=researcher_decision and target_phase=P1. Do not duplicate them as bare
research_setting.clarification_questions. A question asks the researcher to
choose or clarify the setting, not to prove a claim or develop an algorithm.
Method, proof and simulation follow-up are kind=research_task and target P2,
P3 or P4 as appropriate. Literature gaps remain coverage or landscape content.
Items retain stable identity across runs until an explicit researcher answer
or reasoned team disposition supersedes them; omission does not resolve them.

There are four substantive deliverables. No extra display-card, summary,
decision, source-change list or teammate-packet writing stage is required.

## Direct delivery

These are scientific records shared by the UI and relevant later members.
The original author writes the visible mathematics and explanation during the
ordinary producing stage. No second agent repairs them for presentation.
Use `$...$` for inline mathematics and `$$...$$` or `\[...\]` for a central
equation that benefits from display, with aligned line breaks for long expressions.
Write concise connected scientific prose; do not assemble disconnected
formula-and-caption blocks or turn this guidance into a checklist of subsections.
Completeness takes priority over brevity. There is no requirement for a display
equation in every field or a word, sentence, paragraph or equation quota. Use
KaTeX-supported commands and correctly escape TeX in JSON. Existing math checks
report rendering errors to the author; syntax validity does not prove correctness.
The lead performs actual cross-paper reconciliation, not a rewrite of every
paper entry. Records have no T1 2 KB or definition 600-character limit.
Large supporting detail remains referenced or expandable, never silently
truncated into a scientific substitute.

## Publication and validation

Publication preserves original member content, source identities, attribution,
reading basis and exact generations. It applies explicit lead corrections to
effective current entries while retaining originals and lead revision history.
Correction targets bind the original complete paper-object digest; framework
support references resolve to the final effective snapshot. Structural validation
checks allowed changed fields, resolvable versions, source links and dispositions.
The library and basis publish atomically and corrections do not inflate source
or assessment counts.
Source traceability is not proof that every scientific claim is correct.
The producing members retain responsibility for scientific content.

A failed run leaves the earlier package current. New generations do not
rewrite older sealed results or retrospectively upgrade their contracts.
Frozen older catalog pins and 1.0.0/1.1.0 artifact shapes remain readable. New
requirements do not manufacture review coverage, reading extent, goals or
overview selections for older work.

## User interface

The page has five researcher-facing cards, in this order:

1. Research Setting: project title and instruction action, concise study and
   interpreted-goal paragraphs with essential contextual notation and a simple
   target expression when helpful,
   and notation lookup. Saved setting additions remain in the instructions dialog.
2. Main Findings: concise cited methodological synthesis and selected approach
   paragraphs explaining relationships, mechanisms, decisive conditions and fit,
   with informative equations. Extended formulations,
   relationships, common conditions and support remain accessible through details.
3. Decisions to Discuss: all unresolved consequential researcher questions,
   each with a short question, likely consequence and response/discussion action.
   Scientific context, alternatives and earlier responses remain accessible.
   Team tasks belong in Additional Runs and History.
4. Explore Individual Papers: exact citation, concise source-specific model or
   method explanation with its defining mathematics, relevance
   and material limitations for one selected attributed assessment. Full
   formulations, reading extent, evidence and revisions remain inspectable.
5. Additional Runs and History: saved further-work instructions, scope choices,
   explicit start, compact status, recovery/continuation controls and dated history.
   Expand operational details, search scopes, data profiles and review records.
   Current findings are linked, rather than displayed again as a second synthesis.

The reading sections retain the compact tinted backgrounds used across phases.
Answered entries are neutral. Progress is compact; history and source records
are secondary. Project-wide instruction edits do not rewrite published research.
Historical untyped questions remain readable with their original source rather
than being automatically classified. Source equations and attribution stay intact.

## Authoring for the researcher

Each paper's `explanation_markdown` explains this source's actual model,
formulation or method through connected methodology-style prose, including the
defining relationships, criterion, update or construction needed to understand
it. Explain symbols and decisive conditions in context. A generic family
description cannot replace the paper's specific mechanism. `formulation_markdown`
and evidence locations preserve expanded definitions, assumptions and derivations;
the method's defining mathematics must also appear in the visible summary when
available. For a nonmethodological paper, explain the actual contribution and
decisive statement or evidence without forcing an algorithm or equation.
Reported claims, checked arguments and missing access remain distinct.
`relevance_markdown` explains fit and `limitations_markdown` states material
qualifications briefly. Do not replace scientific explanation with notation
definitions or require display equations in every field. During discovery, do not author the
setting, cross-paper findings or history. The Lead's study and goal accounts
give essential context, notation and the interpreted goal. Detailed proposed
project methods belong in P2; only the findings synthesize literature. Within
the recorded review scope, the Lead checks that visible paper accounts explain
the source-specific formulation or procedure, match the fuller formulations and
retain decisive conditions.

These are sections of the existing independent collections and research basis,
not new card files or another writer's paraphrase. Detailed reasoning has one
primary home; other sections cite it with a brief consequence-focused recap.

## Downstream behavior

P2 receives the current exact research basis, relevant effective corrected paper
entries and current
shared researcher instructions. Additional P2 instructions and any explicit
supplied-method seed go only to the lead. No P1 publication
automatically launches P2. Later source updates preserve historical evidence.
P3-P5 retain their existing phase boundaries and authority.
Current open tasks addressed to a phase enter its next user-started run as
frozen context. A P1 setting answer updates the shared research instructions;
additional P2 input continues to go only to the Research Lead.

## Acceptance scenarios

Under catalog 1.23.4, discovery collections use schema 1.2.0 and the Lead basis
uses schema 1.3.0. Each collection may record consequential missing information
in `proposed_questions`, with the affected point in `context_markdown`, its practical
answer effect in `answer_consequences_markdown` and exact `source_refs`. Where
mathematics distinguishes the proposed answers, include sufficient formulation and
locally defined symbols in that affected point for Lead consolidation. A separate
`why_it_matters_markdown` repetition is optional historical support. Parallel discovery must not contact
the researcher through native host question tools or create a blocking pause.
After submissions close, the Lead consolidates these proposals into scoped
`attention_items`. Materially different premises remain distinct; answer reuse
requires exact applicability references. Optional questions permit qualified
literature work. Only an eligible serial stage may author a justified blocking
`researcher-question.json`.

The Lead index retains raw sealed assessments and both values of bibliographic
conflicts. Harmless initials punctuation is compared conservatively. Contradictory
strong identifiers, source statuses and duplicate member entries still block
discovery. Shared generic URLs cannot override different DOI/PMID identities.
True authors/title/year disagreements need primary-source verification and
explicit Lead `entry_corrections.source_metadata`, binding the exact target
digest, evidence and reason. Only authors, title, year and venue may change;
metadata-only corrections require no scientific changes. Identity, locators,
status, timestamps, search provenance and original science stay intact.

For corrected metadata the harness retains the original source revision and
authored checksum, then derives a new `content_sha256` over the effective citation
record excluding that field. Its `content_sha256_scope` is
`citation-record-excluding-content_sha256`. Citation/support references use the
effective whole-entry digest; review and correction targets use the supplied
original digest. Publication, reconstruction and readers share the same replay.
Unresolved genuine conflicts block final publication. Original pinned runs and
historical citations retain their producing contract and publication snapshot.

- A first valid P1 run requires three collections and one basis.
- A source not revisited on a rerun remains in the cumulative library.
- The selected paper UI and P2 resolve the same exact current formulation,
  including explicit lead corrections with original authorship and history.
- Stale correction digests, identity changes and dangling framework references
  are rejected mechanically; unresolved scientific disagreement is displayed.
- Lead scientific corrections add no specialist turn or paper/assessment count.
- A setting amendment is visible and supplied to the next run.
- A supplied method appears as an attributed P2 seed, not a P1 method verdict.
- Historical packages display their existing content with honest missing-field
  labels, without fabricated equations or a presentation-repair run.


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

The Data Analyst may inspect supplied accessible data read-only within P1 for observation units, repetition/timing, missingness, ranges and consequential descriptive structure. Record exact identity/digest, scope, shared runtime and limits in empirical_literature.data_profiles. Fit no model and import no full P4 controller. An observed discrepancy becomes a sourced question, not a silent correction of the researcher account.

## Scientific meaning for the intended reader

Apply the [shared question-language guidance](researcher-question-language.md) within this phase's existing output ownership and interaction rules. It refines the existing question, context, option consequences and recommendation; it adds no artifact, questionnaire or question quota.

In P1, connect a proposed question to the scientific objective, population, observation unit or intended interpretation. Do not ask for an estimator choice before the research goal calls for it.

## Writing duties in existing outputs

The executable objectives give the task, shared writing core, owned output duties
and separate scientific/execution constraints. `papers[].explanation_markdown`
explains each paper's actual target and mechanism with source-supported defining
mathematics. `formulation_markdown` retains the fuller account; relevance and
limitations stay in their fields, with honest access and verification limits.
The Lead's `research_setting.statement_markdown` and `research_goal_markdown`
describe observations and the intended scientific answer with essential notation,
keeping prediction, estimation and causal aims distinct. `landscape.summary_markdown`
and approach accounts explain meaningful differences across sources. Specialists
propose consequential premises through `proposed_questions[]`; only the designated
Lead stage consolidates attention. No new pause authority is granted.

## Shared notation and presentation (catalog 1.30.0)

Discovery preserves source-local paper notation and reuses admitted study notation on reruns. The existing Lead research basis establishes the canonical study core through `notation_updates`; the generated lookup replaces independent new `component_interpretations` glossary authoring.

The five neutral presentation references apply through `research_presentation_v2`; shared notation is separately gated by `project_notation_v1`, which requires v2. Keep full measure definitions beside results and actual resource measurements outside mathematical notation. This adds no stage, output family or scientific authority. Retained catalogs preserve their original routing and historical local fields.
