# Research presentation

The researcher should understand the scientific answer, inspect the comparison
that supports it, and supply consequential input without reconstructing internal
records. Catalog 1.30.3 supplies the same five authoring references as neutral
guidance across the five phases, with phase duties kept in the executable objectives:

| Reference | Responsibility |
| --- | --- |
| [Scientific explanation](../contracts/references/research-presentation/scientific-explanation.md) | Target, mechanism, design, notation, units and scientific meaning |
| [Claims and evidence](../contracts/references/research-presentation/claims-and-evidence.md) | Support, conditions, uncertainty, counterevidence and attributed disagreement |
| [Summary](../contracts/references/research-presentation/summary.md) | Finding first, selection and placement, one primary account per topic |
| [Tables and figures](../contracts/references/research-presentation/tables-and-figures.md) | Useful comparisons, denominators, uncertainty, captions and exact sources |
| [User inquiry](../contracts/references/research-presentation/user-inquiry.md) | Consequential filtering, overlap consolidation, short mathematical/domain explanations and response options |

## Delivery and ownership

The run freezes the entire adopted catalog. `presentation_references.py` reads
reference bytes from that frozen copy and inserts them into the submitted brief.
`research_presentation_v2` supplies explanation and evidence guidance to relevant
authors and discussions. P1 synthesis adds summary guidance; P2-P5 receive display
guidance, and synthesis Leads receive summary guidance. Eligible P1-P4 work retains
the inquiry reference. P5 assembly and revision Leads retain narrowly editorial
inquiry; parallel reviewers gain no inquiry authority. The four neutral editorial
references are frozen into the independent submission packet for all reviewers
and the revision Lead, without being repeated in their ordinary briefs.

Targeted question discussions and advice receive explanation/evidence guidance
and inquiry only where it was already permitted. Exact report-section discussions
receive explanation/evidence guidance without upstream elicitation. Mechanical
repairs retain the original brief. Existing projects require explicit catalog
adoption for future scientific work; old runs and publications remain unchanged.

For a numerical table the Analyst decides what each row compares before writing
the exhibit. A fixed comparator or study setting belongs in the caption or the
relevant panel heading. Varying comparisons, observed outcomes and the counts
that define their populations remain identifiable in the rows. The Phase 4
Lead checks this when selecting evidence. The Phase 5 Lead applies it to report
tables within the report's existing permissions to use the published evidence.

### Focused research accounts, catalog 1.31.7

The phase objectives distinguish the requested scientific objective and constraints,
the strategy used to learn or rank candidates, and any additional inferential
promise. A conservative ranking rule can serve the original objective. An added
guarantee needs an explanation of its assumptions and practical cost; an inherited
guarantee does not establish that the researcher requested it. Applicable saved
answers govern that distinction without silently rewriting a method.

P3 states the exact supported result and its assessment status, with the decisive
conditions beside it. P4 plans comparisons that can distinguish the claimed
mechanism. The Analyst inspects the actual saved display files and reconciles
reproduction instructions with the final declared files before completion. The
Lead reads those retained displays and selects useful evidence. Column metadata
changes labels and units only; it cannot hide columns. Compact tables therefore
need actual compact artifacts, with complete evidence and row mappings retained.

For catalogs declaring `research_account_focus_v1`, targeted discussions answer
the particular question with the source's mathematical definition and practical
consequence. Unknown information remains unknown. Advice is not a saved answer,
and a changed scientific formulation requires the existing revision route.
Longer derivations remain available when requested. The five neutral references
and the short shared writing guidance are unchanged by this focused revision.

### Mathematical table headings, catalog 1.31.8

Quantitative headings prefer concise source-defined notation, such as
$\operatorname{MSE}(\hat f)$ or $\operatorname{SD}(\hat V)$, when the recorded quantity
supports it. Full measure names, local symbol definitions, averaging subsets,
units and parenthetical uncertainty stay in captions or adjacent prose. Standard
deviation is not a standard error. Keep scenario and method labels descriptive;
headings do not create new metrics or notation records, or change saved values.

## Phase 2 comparison overview

The Lead's `overview_markdown` compares every candidate assessed in the same
run, including excluded alternatives. It begins with a supported finding or
conditional recommendation, then contrasts each candidate's central mechanism
and the conditions that matter for its use. Shared conditions appear once;
computational detail belongs here only when it changes the comparison. A short
account can expand to preserve a necessary scientific qualification. The full
comparison holds the extended reasoning and disagreements.

The Proposed Methods card presents this complete overview in its left 60%, with
Full comparison, Shared notation and applicable exclusion reasons in the right
40%. Changing the selected method below does not change this run-level account.
The interface preserves saved prose and uses the full comparison when no
nonblank overview exists. The stronger instructions affect future runs using
the updated catalog, not previously published research records.
Frozen `research_presentation_v1` catalogs retain their original P4-scientific,
other-phase-inquiry routing and their own retained reference bytes.

The Analyst computes numerical evidence and emits compact supported flat tables
alongside full diagnostics, through the existing managed script/result path.
Tables are ordinary `kind=table` CSV or scalar columns/rows JSON exhibits. The
Lead selects existing exhibit IDs and explains supported findings. The renderer
does not calculate comparisons, infer denominators or reinterpret uncertainty.
P5 keeps its existing checked proof exposition and exact-value figure permissions.

### Scientific quantities from problem definition to report

A researcher should be able to read a result without knowing how the software
records it. Use the accepted term for the quantity the study actually measures.
For example, write “probability that discounted cost exceeds the threshold” and
give its probability expression. Define who or what varies. A probability for
a new patient and a proportion across independently fitted models use different
denominators, even when both are called risk in the source.

| Phase | What the researcher should learn |
| --- | --- |
| 1. Define and Explore | What outcome or estimand the study targets, in the domain's terms. Explain a paper's different target when comparing it. |
| 2. Propose Methods | Which quantities competing methods optimize or estimate, and which assumption, constraint or comparator distinguishes them. |
| 3. Theory | What parameter, loss, event or coverage statement the result concerns. Identify the source of randomness and which conditions the guarantee requires. |
| 4. Numerical Eval | What was measured or estimated, against which reference, in what units and over which observations or replications. Explain an empty subset in the caption. |
| 5. Report | Carry the same scientific definitions into the abstract, result prose, headings, captions and linked evidence. Use a short heading and supply shared details once. |

For a simulation, distinguish the target, performance measure, and Monte Carlo
uncertainty. A nominal 95% confidence interval for an estimate and empirical
coverage of intervals across repeated samples answer different questions.
Mean squared error requires a squared discrepancy from a specified truth.
A reward difference against a competing policy can be reported without claiming
regret relative to an optimal policy. This follows established guidance on
reporting simulation studies. [Morris, White and Crowther (2019)](https://doi.org/10.1002/sim.8086)

Primary summaries select the finding, its decisive conditions and the next
unresolved question. The complete condition inventory, proof mechanism and
history stay in linked sources. Essential qualifications remain beside the
claim; neither the author nor the renderer shortens text by dropping conditions.
The Phase 3 overview also shows its existing authored headline when it differs
from the full conclusion.

Catalog 1.31.2 gives the P3 Lead's existing decision fields one connected
overview. The visible account is `current_conclusion`, not the compact theory:
it states what the result permits for the research goal with the original target
visible, its decisive relation and premise classes, and the nearest misleading
stronger reading. **What this analysis adds** explains the mechanism, **What
remains uncertain** the most consequential missing evidence, **Main risk or
limitation** its practical effect, and **Next useful step** one bounded question
with the gap it resolves. These side fields add information rather than restate
the account. The readable manuscript opens with the science; the phase summary
records what the run changed; the compact theory retains standalone technical
context for later work, including material corrections. Theorist assumptions may
carry an authored scientific `label`; claims keep their existing claim-map label.
Sufficient conditions stay sufficient, and a probabilistic guarantee keeps its
population and denominator. This P3 patch does not change other phases' duties,
the shared language core or the five neutral references, and existing records
are not rewritten.

New table authors select the scientific comparison before choosing columns.
Related quantities may share a cell, such as a count with its denominator or an
estimate with its interval. Shared setup belongs once in the visible caption.
Reusing a displayed denominator requires the same population and count in the
source, not merely equal numbers. Zero outcomes, missing values and uncertainty
coverage remain explicit. Descriptive condition names come from the protocol;
scientific sample sizes distinguish observations from simulation repetitions
and computational checks. Existing tables are not rewritten or automatically
compressed. Desktop artifact tables keep their first column visible during
horizontal scrolling; narrow screens retain ordinary scrolling.

## Existing cards, clearer reading

Catalog 1.31.4 organizes P4's existing account as a compact numerical experiments
section. The Analyst explains replication, fixed and varied settings, comparator
information, measures and their subsets, then produces supported comparisons,
uncertainty and compact displays before Lead selection. Selective or constrained
methods keep return, constraint behavior and objective quality separate, including
their conditional subsets and unresolved reference classifications. Pilots and
finite code checks remain distinct from principal repeated-simulation evidence.
The Theorist identifies which claim each qualification affects, preserving its
premise and evidence boundary without generating new evidence.
`scientific_outcome.conclusion` selects the principal Summary finding and decisive
scope limit, including a tested failure or no-useful-output condition when it
changes the practical assessment; `decision_summary.conclusion_markdown` adds
interpretation. In Experiments and Results, design and measures precede the
results; coverage summaries own the design or principal finding and any
source-backed explanation of a negative result, followed by its exhibit,
evidence or claim boundary and distinct implication. Exact-test reviews retain
every assessment and unique qualification without repeating the primary account.
Each topic lists all interpreted exhibits in its existing `exhibit_ids`, including
shared ones. The first declaring coverage entry owns the display and later
entries show links. Existing topics, output shapes and frozen source/notation
authority remain unchanged. Project adoption
affects future runs and does not rewrite historical records or establish improved
model behavior by itself.

Phase 4 Summary prefers optional `decision_summary.method_recap_markdown` for the
visible implemented target and rule. `method_formulation_markdown` remains the
full mathematical source. Older records retain their existing fallback.
`project_notation_v1`, which requires presentation v2, supplies one shared
**Notation** dialog across the existing P1-P5 reading locations. Each Lead adopts
small `notation_updates` in its existing account. The harness freezes admitted
inputs and generates a complete final `notation.json` and matching `notation.md`
before sealing the account. The publication owns those files through its
`notation_snapshot` pointer. P1 owns the study core, P2 the exact method/candidate
scope, and later Leads their account additions and explicit translations.

The lookup uses the selected account's retained final view, including symbols
introduced during synthesis. It preserves paper/proof-local meanings and the
method's stable identity plus definition digest. P5 review, section discussion
and offline HTML use the report's retained definitions and mappings. No mutable
project-wide latest glossary is consulted. Historical P1 component arrays and P4
`notation_markdown` remain fallbacks for their own records; new-capability authors
do not independently write them. Essential definitions remain inline.

Notation contains mathematical symbols used substantively in the account. Full
performance-measure names and their actual loss, averaging unit and uncertainty
belong beside results. A substantive population risk functional remains a model
quantity. Computational cost names the measured resource, units and operations
outside notation. Existing authored content is not filtered or rewritten by the
renderer. The [notation design](shared-notation-plan.md) records scopes, source
checks and compatibility boundaries.

New method titles identify the mathematical or statistical framework and a
supported defining variant. The proposal instructions no longer require a coined
acronym. The schema and both ordinary and supplied-method proposal routes use the
same naming rule; method identities and historical names remain unchanged.

Experiments and Results owns tables and figures in a connected numerical section.
Compact section links connect the authored setup, comparisons, sensitivity and
measured computational cost. Each principal finding precedes its verified exhibits;
distinct limitations and implications follow. Each exhibit has one primary home,
with links from other relevant sections. Full protocol fields, attributed Analyst
accounts and scientific reviews remain supporting detail, without duplicating
the primary setup. Unassessed scope stays explicit and compact; failed findings
and consequential qualifications remain visible. Diagnostic values remain
accessible when the main display is unavailable. Source windows preserve title,
close control and focus return; stable reading anchors and card styles remain.

For a hosted portable report, HTML appendix download links use a short attachment
URL bound to that report generation and exactly one declared material. The
service verifies the retained source and digest, then returns the original bytes
and filename. Downloaded standalone reports still embed their original materials
and do not depend on a running service. Their browser-dependent data-link saving
is distinct from HTTP attachment delivery. The report sandbox and source-reader
restrictions remain unchanged.

## Consequential questions and answers

The Lead invites a decision when the researcher's purpose, study setting, or
constraints would change which model to develop, which claim to pursue, or what
to investigate next. A result can reveal that choice for the first time. For
example, a method that recommends an action only with much more data can prompt
the Lead to ask what sample size is realistic for the intended use. If the
researcher has already supplied that information, the team can act on it.
Technical comparisons the team can resolve itself stay with the team. The Lead
consolidates questions only when one answer settles both
under the same target, population, conditions, timing and scope. Scientific
findings and independent reviews do not merge merely because wording overlaps.

New primary inquiries use explicit prose ceilings: 20 words for the question,
45 for shared context plus overall consequence, 30 per option, 20 for the Lead's
reason, and 180 total for a choice or 80 for a study fact. Compact formulas are
additional; prose inside formulas counts. Essential conditions take priority over
history and repeated explanation. These are authoring requirements, not runtime
truncation or a claim that word counts establish scientific usefulness.

An optional `recommended_option_id` identifies a justified suggestion, placed
first in new authored choices. The UI never infers it from array position, changes
historical order or preselects an answer. Facts remain text/unknown. Custom answers
are available through **Suggest another option**. Badges preserve author
attribution rather than attributing every suggestion to the Lead.

Catalog 1.30.4 assigns the existing inquiry fields complementary reading jobs:
`context_markdown` identifies the affected choice or fact, and `likely_consequence`
completes the same Why this matters account. Other consequence fields should not
repeat it. Options carry their distinct formulation, meaning and practical
tradeoff; the recommendation supplies its reason once beside the exact suggested
option. No justified ranking remains a valid outcome. Existing word ceilings and
scientific conditions remain unchanged.

The interface consolidates headings for typed researcher inquiries while keeping
all distinct historical passages, mathematics and citation ownership. It does
not attempt semantic summarization of old outputs. The response stays full width
below the 60/40 explanation/assistance row. Saved and read-only answers retain the
original options and recommendation in a compact disclosure; editing reopens the
single answer owner. Recommendations never imply selection, adoption or a pause.

Discuss and Lead advice carry an explicitly unsaved structured response when
present, including an option selected without a note. The backend resolves option
text against the exact question, while saved answers remain separate. A discussion
does not save, resolve, adopt or start research. One effective answer is edited at
its original location; retries retain their exact input and idempotency identity.
An unsent discussion reopened after an answer edit uses the current draft.

Notation rows support exact-source explanation and one editable correction in
the existing researcher-context store. Saving requests future work; it does not
adopt a definition. A published Lead disposition names the exact saved revision
and records adoption, an unchanged definition with a reason, or scientific
revision. Account-local correction ownership follows the retained source account;
inherited mirrors and explicit clarifications reopen the same owner.

Automated checks cover contract routing, frozen reference bytes, source identity,
scoped updates, historical reads and report materials. They do not establish
model compliance or scientific equivalence. Fresh paired guidance excerpts exist
under `.tmp/shared-notation-probes/`; they are synthetic writing probes rather
than complete research runs. Browser/keyboard review, the final independent
implementation review and the broader regression result are recorded separately
when completed. See the notation document's evidence and reader-acceptance block.
Local review and probe records stay in the ignored `architecture/evidence/` and
`.tmp/` directories; they are not distributed with the application. Bounded
writing probes are not a replacement for evaluating a complete scientific run.

## Optional reading without rewriting the science

The interface separates the primary account from supporting documents using
compact toolbars and centered readers. This is a display projection, not a new
authoring obligation, summary generator or workflow-catalog migration.

The primary account keeps the claim and its necessary conditions together.
P3 obtains whole-theory restrictions from the exact complete theory, and displays
registered assumptions with the selected claim. P4 retains numerical exhibits,
denominators, uncertainty, exclusions and the tested-theory context in Experiments
and Results. P5 retains outcome scope, assumptions and recorded counterevidence
with claim text; a linked document alone does not establish a scientific verdict.

Complete readers retain their authored mathematical and scientific contents,
including legacy fields and numerical Markdown tables. Reading controls provide
truthful prose/equation or structured-content sizes where available. Unknown
size is omitted, and a collection of files or sources does not become empty
because it has no prose.

Opening a reader freezes its scientific sources, while live answer editors,
discussion, advice, run preparation and pause controls retain their existing
owners. Reading does not adopt a recommendation, save an answer or launch work.
