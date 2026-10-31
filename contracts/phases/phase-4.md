# Phase 4: Numerical Eval

Contract version: 3.6.2. Catalog: 1.30.2.

## 1. Purpose

Phase 4 builds and maintains the empirical and computational evidence base for one user-selected method. It evaluates implementation fidelity, statistical behavior, robustness, comparison with alternatives, and consistency between observed results and the method's stated claims.

Phase 4 is parallel in pipeline status to Phase 3. It may run immediately after Phase 2 and does not require Phase 3 to have run. The phase enables the user to judge what the current evidence supports, which evidence remains applicable, and what computation or analysis a rerun should address.

## 2. User choices

Before launch, the user chooses:

- One active method and its exact current version
- Preliminary or comprehensive scope
- Additional empirical, computational, or scientific instructions
- Optional current project context
- Whether to include selected historical Phase 3, Phase 4, or other run material

Preliminary scope, displayed as Feasibility check, requires implementation verification, a controlled example and relevant numerical checks. A baseline is required when it addresses a material comparative claim or researcher expectation; otherwise explain why comparison is inapplicable. Comprehensive scope, displayed as Detailed evaluation, begins with a prioritized plan addressing the researcher's intended benefit, comparative performance, computation, tuning and relevant sensitivity or assumption questions. Either scope may be selected on any run; scope is not determined by run number.

Preliminary proof-of-concept experiments may run before Phase 3 exists or
its proofs are complete. Available aligned theory and its limitations are
included. The analyst and auditors distinguish feasibility evidence from
evidence for a theoretical claim. Both scopes retain the three-role audit
sequence; preliminary scope does not require a full diagnostic suite.

Current aligned records are included by default. Historical runs are excluded unless selected. After completion, the user decides whether to rerun Phase 4, run Phase 3, return to Phase 2, defer, or proceed when Phase 5 is eligible.

## 3. Prerequisites

A run requires:

- A current project research brief
- A validated current Phase 1 literature basis
- A current Phase 2 method catalog
- One active selected method with an exact stable ID, version, and mathematical-definition digest

A Phase 3 record is optional. The prior Phase 4 evidence index, empirical synthesis, and implementation record are absent on the first run and required together as current context on a rerun for the same exact method identity. A negative or inconclusive prior empirical outcome does not block a rerun. A retired or noncurrent method selection blocks preparation, and an older method version cannot be selected as the current target.

## 4. Frozen inputs

The run basis freezes:

- The exact selected method record, stable ID, version, and definition digest
- The current project brief and Phase 1 literature basis
- The current Phase 2 catalog generation and method provenance
- The current Phase 4 evidence index, empirical synthesis, and implementation record for this exact method identity, if they exist
- The current Phase 3 theory record and empirically testable implications for this exact method identity, if they exist
- Current cross-phase alignment, dependency, and unresolved-issue records
- Preliminary or comprehensive run scope
- User instructions and optional current context
- Exact historical records selected by the user
- Researcher-supplied supplementary material seeded with the run command (for example the researcher's own partial code, to be utilized or revised so the implementation is easier), frozen with researcher_seed provenance; additive only and never a substitute for published records
- Role instruction, knowledge, skill, tool, data-access, and execution-environment manifests

Current records for another method version are excluded from current context and may appear only as selected history.

## 5. Role order

The role order is fixed.

1. The data analyst performs the primary Phase 4 work. The analyst states the evaluation protocol, implements or verifies the exact selected method, executes the authorized scope, and produces the candidate evidence records, synthesis and implementation account. The eight analyst outputs include `implementation_record_candidate.json` and its retained source files.
2. The theorist receives the frozen basis and analyst output, including that implementation account and exact retained code/configuration, then checks mathematical fidelity, correspondence between implementation and definition, interpretation of comparisons, and consistency with current theory when available.
3. The research lead receives the frozen project, literature, method catalog, selected method, prior empirical, and available theory basis together with both role outputs, resolves or exposes disagreements, and produces the candidate formal empirical record and user decision summary. Before sealing, the lead performs the in-house scientific check: every claim in the empirical record and handoff is linked to its supporting evidence or theory record, or recorded as a limitation or open question. An unlinked or unsupported claim is the lead's defect to resolve in-house, never the outside reviewer's discovery.

Each handoff states what was computed, the exact method and configuration used, what changed, what the evidence supports, and what the next role must verify. There is no silent repair loop. If implementation fidelity or evidence validity remains unresolved, the lead reports it and gives the user an exact rerun question. The outside reviewer does not participate in Phase 4.

For the `progressive_evaluation_v1` capability, the analyst's stage spans
checkpointed turns and bounded managed batches. Save the initial protocol before
computation, verify implementation with small checks, then execute one planned
comparison at a time while monitoring outcomes and the authorized resource
budget. A genuine unresolved researcher preference or unavailable study fact that
blocks justified progress requires a durable pause before further experiments or
handoff. A severe scientific defect also stops further experiments: retain the
evidence and ask only about a consequential scope or continuation choice, rather
than asking the researcher to solve the defect. The same pause operation is
available to reviewers. No role repairs the mathematical
method or launches P2/P3 automatically. Ordinary coding corrections may restore
an unambiguous frozen definition, with affected observations invalidated and
fresh attempts recorded. A negative result alone is not a failed run.

## 5.1 Ordered scientific workflow under catalog 1.25

The analyst follows Steps 1-4 and completes its answers and handoff in Step 5.
The theorist then audits those completed outputs. The lead owns Step 6.
These are the existing three stages, not additional agents or approval gates.

1. **Define the evaluation and choose the implementation route.** Read the exact
   P2 model, researcher target and data-collection account, relevant P1 work,
   aligned P3 results when available, prior implementation and saved directions.
   Name the target, units, population, intended use and material unknowns.
   Distinguish estimation, prediction and intervention questions. Inspect suitable
   shared Python/R packages and supplied/prior code. Choose `package_reuse`,
   `package_adaptation` or `custom_implementation`, explaining exact equations,
   objective, preprocessing, tuning, estimation/prediction and uncertainty
   correspondence. Record package/API/version/source, provided operations,
   missing pieces and adapter behavior. `strategy=new/reuse_verified/adapt_verified`
   separately describes prior-project lineage. First-run package use may be new;
   supplied custom code remains custom with its origin recorded. Check the actual
   shared runtime and dependencies, distinguishing inaccessible from absent
   installations. Report precise setup needs and use machine/user-wide tools only.
   Plan question-linked checks, example, performance criteria, actual-data use,
   fair comparators, scenarios, uncertainty, timing and resource/stopping rules.
2. **Deliver reusable code and an executable synthetic example.** Supply a model
   entrypoint taking data/configuration and returning estimates/predictions,
   diagnostics and failures. A thin package driver, adapter or standalone model
   is sufficient; a full installable package is optional. Separate fitting,
   generator, example configuration and demonstration runner. Record ordinary
   invocation, columns/types/units, outputs, seeds, dependencies and actual runtime
   in `reproduction`. Retained exports must run without provider credentials,
   run-directory paths, hidden state or required `MODEL_FORGE_*` variables.
   Explain the DGP with mathematics, observation/dependence structure and known
   target. Compute truth independently of estimator code and qualify numerical
   approximations. Distinguish illustrative choices from researcher facts. Write
   source bytes, complete their exact pointers, then `save_plan` before Step 3;
   do not invent a planned-file digest.
3. **Verify on the synthetic example.** Run independent reference/invariant
   checks, the example fit, dimensions/domains and relevant input/failure cases
   with declared tolerances. Run the retained exported bytes from a separate
   working directory through the managed runner, using ordinary arguments.
   Save command, outcome and discrepancies. A smoke test supports execution or
   fidelity only. Repair routine code defects to the unambiguous frozen model,
   invalidate affected measurements and preserve attempts. A defective or
   ambiguous mathematical method stops further experiments. Report the unresolved
   scientific defect; ask only about a necessary scope or continuation choice.
4. **Evaluate performance and apply to supplied actual data.** Use the verified
   implementation and a justified scenario plan. Assess target accuracy,
   uncertainty/reliability, computation, tuning and robustness as relevant in
   either scope; give reasons for unassessed/inapplicable criteria. Feasibility
   can be small; Detailed evaluation needs evidence adequate for its claims,
   without a universal scenario or repetition quota. Use fair paired comparisons
   when the claim requires them. Estimation uses known-truth error; prediction
   uses held-out loss/calibration/discrimination as appropriate. Predictive
   accuracy cannot replace intervention-effect error. Keep the P2 tuning rule
   fixed; out-of-rule variants are named ablations or upstream proposals.
   Map usable supplied data to mathematical variables/units and fit the same
   model interface, with preprocessing, missingness, splitting and observation
   restrictions documented. Report actual-data estimates or held-out prediction
   and diagnostics, without unknown truth, invented coverage or unsupported
   causal/clinical interpretation. Record the final `actual_data_application`
   disposition and reason, rather than editing the frozen protocol. No supplied
   dataset means `not_supplied`, not a fabricated actual-data case.
5. **Complete answers, then independently audit.** The analyst completes all
   eight outputs, every exact test answer and its handoff before the theorist
   begins. Each answer presents a finding and quantitative exhibit, conditions,
   usable counts, uncertainty, decisive caveat and decision consequence. The
   analyst must not depend on later reviewer outputs. The theorist separately
   checks mathematical fidelity, source/code correspondence, design,
   denominators and interpretation, preserving disagreement and unassessed work.
6. **Consolidate results and researcher decisions.** The lead starts with the
   consequential supported finding and scope, then recaps the exact implemented
   method and what was developed/tested on synthetic and supplied actual data. Topical accounts
   compose existing analyst answers and verified exhibits without changing the
   results. `headline_exhibit_ids` gives preferred exhibit order within Experiments
   and Results; Summary contains no exhibits. Consolidate consequential questions
   with alternatives, implications and proposed resolving work in existing
   attention/decision records. Suggestions neither change the method nor launch
   a run. A genuine blocker during any earlier step immediately uses the durable
   `request_decision` pause; final consolidation must not delay it. Nonblocking
   unknowns remain explicit conditions in the analyst/theorist handoff.

### Result templates and denominators

Use the delivered frozen [tables-and-figures reference](../references/research-presentation/tables-and-figures.md)
for concrete compact display patterns, common caption/precision/source rules and
separate figure guidance. The Analyst generates supported flat `kind=table`
artifacts from saved result rows through the authorized script and managed route,
before handoff; a multi-section result JSON is supplementary material. Keep the
scientific denominator and uncertainty distinctions below.

For independent generated datasets, known-truth scalar estimation may report

$$
\widehat{\operatorname{Bias}}=\frac{1}{R}\sum_{r=1}^R(\widehat\theta_r-\theta_r),
\qquad
\widehat{\operatorname{RMSE}}=\sqrt{\frac{1}{R}\sum_{r=1}^R(\widehat\theta_r-\theta_r)^2}.
$$

Within a fixed-target scenario with $R>1$ usable independent datasets, the
empirical standard deviation is

$$
\widehat{\operatorname{SD}}(\widehat\theta)
=\sqrt{\frac{1}{R-1}\sum_{r=1}^R(\widehat\theta_r-\overline{\widehat\theta})^2},
\qquad
\overline{\widehat\theta}=\frac1R\sum_{r=1}^R\widehat\theta_r.
$$

Empirical SD describes variation between estimates, while Monte Carlo standard
error (MCSE) describes precision of a reported simulation summary. Label them
separately. Report bias and empirical SD when they answer the estimation target;
use appropriate held-out error when the target is prediction. Do not invent
an unmeasured statistic to fill a template.

A one-dataset example reports estimate/error, not bias or RMSE. A bootstrap
resamples a dataset and does not increase the number of independently generated
datasets. `replication_unit` distinguishes `independent_dataset`, `fixed_dataset`,
`resample`, `split` and `deterministic_check`. Keep full-procedure failures apart
from internal fitting failures. State conditional usable denominators and all
planned/completed/failed/not-run counts. Interval return, coverage among returned
intervals and joint return-and-cover have different denominators; administratively
unrun datasets remain separate. Unmeasured uncertainty is unassessed, never zero.
Paired contrasts need uncertainty for the paired difference, not just marginal
error bars. Timing captions name the runtime, hardware/thread settings and
component overlap; add only nonoverlapping components.
Report convergence behavior or a convergence trace only when retained evidence
records it. Tuning selections alone do not measure sensitivity to tuning choices.
Robustness changes the DGP or observation mechanism in a problem-relevant way;
repeating one fixed DGP does not establish it. An unperformed sensitivity or
robustness study remains unassessed.

Figures answer a useful pattern or relationship under the delivered reference;
there is no plot quota. Their `data_exhibit_ids` identify actual verified underlying
tables. Exact source identity never grants permission to fabricate a comparison.
The source examples remain explicitly illustrative.

### Sources and portable delivery

`protocol.data_sources[]` has a stable ID, label, origin (`researcher_observed`,
`external_data`, `synthetic`, `computational_check`), selected frozen `input_ids`,
supporting files, description and variable mapping. Every case links its exact
`data_source_ids`. A mixed question retains its whole authored answer. Append
new definitions with `amendments.added_data_sources`; never mutate an original
source or insert a mutable actual-data path. Newly supplied actual data requires
the appropriate new frozen run input. Raw participant records stay out of briefs
and result summaries.

`implementation.reproduction` records availability, Python/R language,
`model_entrypoint`, `example_generator`, `example_runner`, `readme`, ordinary
`invocation`, `support_files`, dependency versions/sources and `runtime_identity`.
Each retained file is `{kind, artifact: <existing artifact pointer>}`. Metadata
belongs outside the artifact pointer. An unavailable bundle has explicit null
missing files and an honest reason in the existing five implementation-summary
sections. Source availability does not prove execution or scientific validity.

The analyst's `actual_data_application` records final `analyzed`,
`supplied_not_analyzed` or `not_supplied`, with source and exact question IDs and
a scope/omission explanation. Lead `headline_exhibit_ids` references only verified
exhibits from this evaluation. These additions preserve eight analyst outputs,
two theorist outputs, five lead outputs and existing publication families.

## 6. Run-local outputs

The active run workspace must contain:

- A scope-appropriate evaluation protocol and analysis plan
- Source code or exact code references with immutable digests
- Data, simulation mechanism, benchmark, and preprocessing identities
- Configuration, tuning, random-seed, dependency, and execution-environment records
- Immutable primary outputs, tables, figures, logs, and diagnostic artifacts
- Structured evidence records with stable evidence IDs
- An analyst synthesis distinguishing new evidence from previously current applicable evidence
- A theorist audit with stable issue IDs and explicit method-fidelity findings
- Claim-to-evidence links and limitations
- A candidate current evidence index
- A candidate current empirical synthesis
- A candidate current implementation and reproducibility record
- A structured candidate phase decision with an exact rerun question

Progressive runs also preserve the decision context, ordered work items,
prospective plan amendments and host batch ledger. The analyst synthesis has a
typed result for every declared question, including unassessed work: a direct
answer, comparison, tested conditions, reliability, uncertainty, limitations,
decision implication and next work. Results refer to exact cases, metrics,
comparators, evidence, exhibits and plan revisions. Counts include all eligible
planned outcomes; invalidated earlier attempts are reported separately.
Each `question_results` entry uses one exact effective
`protocol.claim_tests[].test_id` as `question_id`, with `test_ids=[test_id]` and
all and only case IDs linked to that test. Include prospectively added tests.
Do not invent question aliases or merge tests into one result. Detailed reasoning
may be shared through exact source references.
Every completed quantitative answer has a verified exhibit or an inline table
of its exact case and metric diagnostics independently recomputed from eligible
rows. This permits finishing with existing partial evidence when no plot was
produced; it does not permit additional experiments after a finish decision.

The lead's empirical synthesis contains a readable `decision_summary` with
coverage, important tradeoffs, limitations and recommendation, plus attributed
`question_reviews`. It does not replace the analyst's original answers.
Each review uses the same exact effective protocol `test_id` as its
`question_id`, with one review per test, including prospectively added and
unassessed tests. Decision coverage `question_ids` uses those same identifiers.
Do not replace them with aliases or merge their reviews. Feasibility
contains faithful implementation checks and a controlled numerical question;
include a distinct comparative-performance question when
`comparison_applicability.required` is true. Detailed
evaluation covers the relevant decision questions without inventing irrelevant
panels or interpreting incomplete coverage as comprehensive success.

The lead uses `coverage` for the five topical accounts: `synthetic_example`,
`performance`, `computation`, `tuning` and `robustness`, plus `actual_data` when
supplied. Each relevant topic has `summary`, `limitation_markdown`,
`implication_markdown`, exact `question_ids` and relevant existing `exhibit_ids`.
Use an explicit `not_assessed` or `not_applicable` explanation when appropriate;
these accounts do not require additional experiments. The synthetic example
describes the DGP and simulation setup. The other accounts distinguish target
estimation or prediction, recorded computation, tuning choices/sensitivity and
changed-DGP robustness. The analyst owns substantive answers and exhibits; the
lead composes the topical summaries without creating or revising evidence.
Optional `coverage.exhibit_ids` supports retained accounts that predate exact
topic-to-exhibit links; no missing metric or link is silently manufactured.

The analyst owns the detailed implementation explanation once, in
`implementation_record_candidate.json`. Its specialized schema requires
nonempty `implementation_summary.rule`, `correspondence`, `environment`,
`verification` and `limitations`; configuration, choices and departures remain
optional. Correspondence names the relevant algorithm steps or equations and
exact retained code/configuration pointers. A check that could not run is
explicitly unavailable, not successful verification.

The lead reads this account and the independent theorist audit, and authors
`decision_summary.method_formulation_markdown` as a concise mathematical recap
of the exact implemented method from its frozen P2 definition. Explain essential
inputs, model relationship, fitting criterion or estimating rule, target/output
and decisive conditions, with defined notation and source-backed LaTeX. A target
equation alone is insufficient when the model and fitting criterion explain the
method. Keep the full canonical definition in its existing source; do not extract
isolated equations heuristically or silently use a later method revision.
The existing `implementation_markdown` briefly states what was developed and
tested, distinguishing synthetic work, actual-data work and unperformed work.
`method_fidelity_markdown` supplies a short checked-fidelity/issues account for
Implementation and Code, with exact implementation and audit references.
The five lead outputs do not include another implementation record.
`theory_relation` distinguishes `unavailable`,
`not_tested` and `tested` theory and names the exact tested statements. Explain
implementation choices, checks and unresolved departures using the analyst's
record and the theorist's audit. Numerical agreement is not a proof. These are
authored scientific accounts, never conclusions inferred by the interface.

Every evidence item identifies whether it evaluates the selected method, a baseline, an ablation, or a sensitivity case. Agents may not overwrite formal evidence or the current evidence index directly.

## 7. Machine validation

The protocol declares labeled cases linked to its test IDs, metric IDs and
comparators, with planned replicate IDs and seeds where applicable. Every
planned replicate has one eligible completed, failed or not-run row. Invalidated
or retried attempts remain recorded with their reason and execution identity,
but do not enter final estimates. Metric
summaries name their aggregation and uncertainty method. Diagnostics and
exhibits refer to these stable cases and tests.

For catalog 1.4+, validation recomputes supported mean, median, sum and
single-value estimates, mean MCSE, runtime summaries, solver rates and
declared replicate threshold changes from the recorded rows. It verifies
source-byte hashes for protocol, rows, script and primary artifacts. This
checks recorded numerical consistency, not reexecution of the original
experiment or the scientific adequacy of the design. Custom calculations
remain explicitly outside the independent arithmetic checks.

Unavailable uncertainty is null or unassessed; inapplicable stability and
solver panels may be empty. Deterministic checks need no invented seed,
MCSE or solver status. Failed replicates remain visible in the case ledger.

Before promotion, the system verifies that:

- The required analyst, theorist, and lead outputs exist in the stated order
- Every selected-method computation records the frozen stable method ID, version, and definition digest
- The protocol maps calculation-defining method components to implementation and configuration records
- Evidence concerning a baseline or ablation is labeled separately and cannot satisfy selected-method fidelity
- Every evidence item has a unique stable ID, source run, code digest, data or simulation identity, configuration, seed policy, environment identity, and output locations
- All artifact links and recorded digests resolve
- Preliminary and comprehensive runs satisfy their distinct required-scope schemas
- The current evidence index contains only evidence eligible for the exact current method identity
- Superseded, outdated, invalid, and unresolved evidence remains explicit and is not silently deleted
- Claims in the empirical synthesis link to eligible evidence or are labeled as interpretation
- The theorist's fidelity issues have dispositions or acknowledged unresolved states in the lead synthesis
- All writes remain inside the active run workspace

Machine validation establishes reproducibility metadata, exact identity, traceability, and record consistency. It cannot determine whether the study design is scientifically sufficient, whether a result is credible, or whether an empirical conclusion generalizes.

Progressive protocol amendments append new test, case, metric, baseline and work
identities. They never replace original cases. A dated revision records its
reason, already inspected evidence, changed work and inferential consequences.
New outcome-selected questions remain exploratory; planned adaptive precision
procedures retain their stated interpretation. Effective case coverage includes
deferred and not-run work. Published rows bind to the host batch and attempt that
produced their recorded artifact; merely copying a digest into an authored file
does not establish that computation occurred.

## 8. Scientific assessment boundary

The data analyst owns study design, implementation, computation, data provenance, measurement, missingness, leakage, batch effects, uncertainty, and first interpretation of empirical behavior. The theorist owns the independent assessment of mathematical fidelity and consistency with stated theoretical implications. The research lead owns integrated scientific interpretation, biological or substantive relevance, external validity, and communication of disagreement.

Evidence may support, partially support, contradict, fail to distinguish, or leave a claim untested. Negative or inconclusive results remain part of the cumulative evidence record. They are scientific outcomes, not failed runs. Evidence becomes current only when both its authority and exact-method applicability are explicit.

## 9. Promotion rule

After validation, promotion is one atomic operation with two effects:

1. Append new immutable evidence records and their primary artifact references to the method's cumulative evidence history. Existing evidence artifacts are never overwritten.
2. Replace four current generations for the exact selected method identity: the evidence index, empirical synthesis, implementation record, and phase decision.

The protocol, role handoffs, and detailed run artifacts remain immutable run provenance referenced by the promoted records. They do not create additional current Phase 4 slots.

The current index may retain previously promoted evidence when it uses the exact method identity and the lead still assesses it as applicable. It excludes evidence that is outdated, superseded, invalid, or unresolved for current claims, while preserving that evidence in history. If promotion fails, no evidence is appended and the previous current index remains unchanged.

## 10. Formal current record

The formal Phase 4 view for a method consists of its cumulative immutable evidence registry and four current slots:

- The evidence index for the exact method identity, including explicit evidence exclusions
- The empirical synthesis, including claim-to-evidence links, method-fidelity findings, limitations, and unresolved attention items
- The implementation record, including current code, configuration, environment, and reproducibility references
- The phase decision, including the compact lead summary and meaningful user choices

Each current generation identifies its source run and frozen basis. The publication receipt proves that all four slots were committed atomically.

Downstream phases use the current evidence index and synthesis by default. They do not treat the latest attempted run as the current scientific record.

## 11. Invalidation effects

A change to the method's mathematical-definition digest makes every selected-method computation for the previous version inapplicable to the new version. The latest Phase 4 generation remains current in derived position, while an authority event sets its derived alignment to `outdated` until a successful P4 rerun replaces it. Earlier evidence remains formal and traceable but cannot be reclassified as compatible or included as selected-method evidence for the new version. Selected-method results must be recomputed under the exact new definition and receive new evidence IDs. Baseline, data, or code artifacts may be reused when justified, but they cannot substitute for exact-version evidence.

A new Phase 3 record with the same exact method identity creates research attention when it changes a theoretical claim, assumption, boundary case, or empirical implication connected to existing evidence. It does not automatically create method-identity misalignment.

Publication of a new Phase 4 record appends an authority event that marks the current Phase 5 technical report under this catalog outdated. It marks Phase 3 for research attention when current evidence contradicts or materially narrows a theory statement. No event launches a rerun automatically.

## 12. UI projection

The reader has five cards in this order, with results available before a
researcher has manually selected the only evaluated method:

1. Summary: decisive finding and scope, short authored method recap and what was
   developed/tested on synthetic and actual data, with notation available separately.
2. Implementation and Code: compact fidelity, consequential issues and shareable
   code; expandable original correspondence, dependencies, checks and same-run audit.
3. Experiments and Results: Synthetic example (DGP and simulation setup),
   Performance (target prediction error or estimation bias/SD), Computation
   (recorded timing/convergence), Tuning (parameters and actually tested sensitivity)
   and Robustness (changed DGP). Explicitly describe actual data when supplied,
   with mapping, analyzed scope or omission reason. Each topic gives its authored
   account, relevant tables/figures, interpretation and limits before optional
   question/design detail. All quantitative tables and figures, including
   implementation-check and complete-diagnostic tables, live in this card.
4. Decisions to Discuss: urgency-marked consequential items, team explanation,
   researcher contribution editor and one saved instruction.
5. Additional Runs and History: research direction, user-controlled run action,
   previous evaluations and retained execution details.

Label actual data origins beside complete results. Preserve valid explicit
method/reader choices and deliberate empty topics during polling.
When no choice exists and exactly one method has published P4 evidence, select
it only for viewing. Never activate a method or start work. Mixed-source questions
keep the complete answer and table, with explicit source-origin labels. Legacy
unclassified cases remain visible as Other recorded evidence. Missing or unreadable
sources are visibly different from absent data, unperformed work or negative
scientific findings. Summary and Implementation and Code contain no quantitative
tables or figures. Give each exhibit a home in Experiments and Results; question
answers link to it. `headline_exhibit_ids` retains preferred order there.
Preserve exact numerical source access. Historical records lacking the new
formulation use the exact producing evaluation's frozen method account when
available, with its source and identity; otherwise state that the recap is
unavailable. Never infer a new formulation or substitute the current P2 method.

Each quantitative answer keeps effect magnitude, uncertainty, usable repetitions
and tested regime together where recorded. Failed, invalidated and not-run
observations retain their reasons. Per-method cost and total study budget are
distinct. Figures never suppress numerical source access. Verified CSV, JSON
and Markdown table artifacts use declared labels and units. Figures declare
underlying table exhibits through `data_exhibit_ids` in the same manifest;
missing data relationships remain visible unknowns. Titles, axes and captions
explain measures, units, uncertainty and scope without inferring validity from
a plotted ordering. The theorist checks interpretation against its available
evidence, and the lead checks the integrated account before sealing.

A paused run presents its question separately from the last published account.
Provisional plans and results keep their run and method scope; they never imply
a lead verdict or silently replace an earlier evaluation's design.

Progress separates Protocol and empirical work, Theorist audit, Lead
interpretation and Evaluation published. A completed batch does not complete
the analyst account. A sealed account is received before its delivery checks
accept it. Experiment budget measures elapsed experiment time, not scientific
completion or per-method cost. Interpreter-launch and sandbox-access failures
display Setup needs attention with configuration guidance and retained logs:
the computation did not run and no conclusion about the method follows.
These statuses derive from the existing execution ledger and pause request.

History retains full rows, figures, code, configuration, environment, plan
revisions, execution attempts and prior publications. Earlier pinned runs keep
their original execution and display semantics; missing authored answers are
not invented from chart captions or diagnostic numbers.
Earlier lead-owned implementation records preserve their source stage and
author. New analyst-owned records retain the same `implementation_record`
publication alias and remain available to Phase 5. Explicit catalog adoption
applies the revised ownership and schema only to new runs.

The Phase 4 tab displays:

- A read-only list of active feasible methods from Phase 2
- A selected-method panel with purpose, mathematical definition, exact version, assumptions, and provenance
- Preliminary and comprehensive scope controls available on every run
- Whether a current Phase 4 record exists for the exact method identity
- Authority and exact-method alignment
- Counts of current applicable, outdated, superseded, invalid, and unresolved evidence
- Empirical outcome, strongest findings, uncertainty, and limitations
- Research-attention items from theory or evidence conflict
- What changed in the current evidence synthesis
- The exact question a rerun would answer
- Controls for instructions, optional context, and selected history
- A user-controlled Run or Rerun action

The UI distinguishes the current cumulative record from the latest run attempt and displays alignment, scientific outcome, and research attention separately.

## 13. Acceptance criteria

- Given an active method with no Phase 3 or Phase 4 record, when a valid preliminary Phase 4 run is promoted, then a current evidence index is created without requiring Phase 3.
- Given an existing current evidence index, when a valid rerun is promoted, then new evidence is appended and previously applicable evidence is retained unless explicitly reclassified.
- Given any run number, when the user selects preliminary or comprehensive scope, then preparation uses the selected scope rather than inferring it from chronology.
- Given a current aligned Phase 3 record, when Phase 4 runs, then its identity and empirical implications are frozen for the theorist and lead.
- Given a selected-method computation with a mismatched definition digest, when validation runs, then that evidence cannot enter the current evidence index and the run cannot claim exact implementation fidelity.
- Given a baseline using another method, when it is labeled and fully identified, then it may be preserved as comparison evidence but cannot satisfy selected-method evidence requirements.
- Given a mathematical method change, when the new method version becomes current, then evidence for the previous version is excluded from current applicability for the new version.
- Given an inconclusive or negative result with complete provenance, when validation and promotion succeed, then it remains visible as a current scientific outcome.
- Given no history selection, when a rerun is prepared, then older run workspaces are absent and the current cumulative evidence record is used.
- Given invalid output or an interrupted promotion, when the project is read, then the earlier current evidence index remains complete and unchanged.
- Given a successful run, when next actions are displayed, then the system waits for the user's decision and starts no Phase 3, Phase 5, or rerun automatically.


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

Author comparison_applicability in the protocol with required, reason and relevant comparative claim or expectation references. Distinguish researcher observations, external/proxy data, synthetic mechanisms and computational checks. Retain exact data/simulation identity and scope. Actual relevant analysis, including negative or inconclusive findings, supports a completed report; execution completion alone does not.

## Evaluation instructions under catalog 1.21

Checkpoint planning and publication use the same frozen comparison capability.
A justified noncomparative protocol may leave baselines empty; a material
comparative claim still requires a jointly scheduled fair comparison. Show the
authored rationale and any protocol departure, including its impact and
disposition, in the existing experiment design disclosure. Missing answers remain unassessed;
the design is a plan, not an observed finding. Explain the actual data origin,
tested conditions, usable counts, uncertainty and limitations beside results.
Separate estimate MCSE does not establish uncertainty in a paired difference.

The existing native tool readiness check runs once before ordinary work in each
progressive stage for runs frozen with `native_tool_preflight_v1`. A failed check
prevents ordinary member work and experiment execution for that stage. Retain
existing cancellation, numerical-budget and durable-pause behavior.

The Analyst and Theorist put nonblocking consequential researcher questions in
their existing handoff `unresolved_issues`, giving the exact affected point,
practical consequence, sources, model scope and audience. Unavailable study facts
need no fabricated alternatives. They do not author an
unassigned attention file or use native host questions. The Lead consolidates
these into its owned attention 1.2 output without inventing answers. A genuinely
blocking fact or choice uses the existing P4 `request_decision` operation and
ends the turn for a durable pause. Ordinary scientific investigation remains
team work, and unknown facts can remain explicit conditions.

For predictive improvement, distinguish positive gain, a valid statistical claim
of positive gain and gain exceeding a meaningful threshold. Unknown clinical
importance does not waive inferential validity. Synthetic Monte Carlo intervals
are not an actual-study significance procedure. The team establishes the target,
inferential unit, tuning/selection effects, censoring identification and relevant
multiplicity. All-attempted, completion and successful-fit performance retain
their distinct denominators and meanings.

## Scientific meaning for the intended reader

Apply the [shared question-language guidance](researcher-question-language.md) within this phase's existing output ownership and interaction rules. It refines the existing question, context, option consequences and recommendation; it adds no artifact, questionnaire or question quota.

In P4, connect a consequential input to the interpretation of a result, realistic data conditions, intended-use criterion or meaningful resource tradeoff. Implementation, fair comparisons and routine diagnostics remain team work; simulated conditions are not observed study facts.

## Writing duties in existing outputs

The executable objectives give the task, shared writing core, owned output duties
and separate scientific/execution constraints. Analyst `question_results[]` and
exhibits give observed comparisons, units, attempted and returned denominators,
relevant uncertainty and the synthetic/actual-data boundary. Captions explain
direction and tested scope. The Lead's `decision_summary`, coverage and review
fields explain implementation fidelity, evidence, usefulness and tradeoffs without
repeating every table. Keep unsuccessful fits, computational burden and inconclusive
sampled uncertainty visible. Equality in observed fitted synthetic cases stays
within those cases; a synthetic gain does not establish human benefit. These
interpretation examples do not require new experiments.
A comparison that does not demonstrate benefit has not demonstrated its absence.
Distinguish evidence against benefit from inconclusive evidence; nonsignificance
does not establish equivalence. Retain the applicable uncertainty and tested scope.

## Delivered presentation references

The run's frozen catalog supplies five short references under
`references/research-presentation/`. P4 Lead receives all five; Analyst receives
scientific explanation, claims/evidence, tables/figures and inquiry; Theorist
receives the same four for its existing meaning/fidelity audit and authorized
questions. The four scientific modules start in P4; inquiry reaches eligible
P1-P5 authors and targeted discussion/advice without expanding authority.

The Lead authors optional `decision_summary.method_recap_markdown` for the visible
target/mechanism/output recap and `notation_markdown` for a separately reachable
table of recurring mathematical symbols, definitions, scientific meanings and
relevant units. Ordinary metric names, abbreviations and computational cost do
not belong in notation. Spell out measures and explain their definitions beside
the results; report elapsed time, processor time or memory use under computational
cost with the actual units and measured operations. Essential definitions stay
visible at first use; `method_formulation_markdown` retains the fuller formulation.
The existing scientific outcome conclusion states the decisive observation and
boundary. No glossary or recap is inferred for historical records.

The Analyst owns calculations and numerical artifacts, Theorist owns the existing
independent fidelity audit, and Lead selects whole existing exhibits and composes
the account. The Lead may quote/round supported values, but cannot invent a
denominator, interval or contrast or replace numerical artifacts. Each exhibit
has one primary topic home; required review/implication fields remain complete
without replaying the same answer. Preserve all exact per-test reviews, unique
qualifications and attributed disagreement. These P4 rules leave P5's existing
checked proof exposition and exact-value figure permissions intact.

## Shared notation and presentation (catalog 1.30.0)

The existing Lead empirical synthesis adopts evaluation additions through `notation_updates`. The harness generates the complete lookup; new-capability authors omit legacy `decision_summary.notation_markdown`. Analyst numerical ownership, Theorist fidelity review and Lead selection of existing displays are unchanged.

The five neutral presentation references apply through `research_presentation_v2`; shared notation is separately gated by `project_notation_v1`, which requires v2. Keep full measure definitions beside results and actual resource measurements outside mathematical notation. This adds no stage, output family or scientific authority. Retained catalogs preserve their original routing and historical local fields.
