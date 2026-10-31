# Phase 5: Technical report

Contract version: 3.5.2. Catalog: 1.30.2.

Phase 5 assembles, independently reviews and revises a connected statistical technical report for one exact published model. It connects the researcher's problem and intended use with the formulation, mathematical justification, numerical findings and limitations. Journal selection, novelty and publication readiness are absent from this workflow. The reading output is HTML: a compact main report with a separately linked in-app proof appendix. Each run's frozen `p5.instructions` governs reading scope and appendix organization. PDF creation, print layout and page-count checks are required only if the researcher explicitly requests them later.

The technical report has its own current slot and generation history. Historical manuscripts retain their original family, scope and exact review target. A selected manuscript can be history, but never supplies the current report to continue or review.

## Assembly and exact sources

Assembly requires the exact active published model, a frozen problem-context revision and applicable problem/model sources. Freeze available exactly aligned P3 and P4 records and their explicit absence. Missing theory or evaluation does not block an interim report. Source identity includes branch, phase, family, generation, content digest and exact locator. Changed bytes cannot be replaced by a new current record.

The primary report retains Markdown with LaTeX as its exact source and is read as HTML. It covers:

1. Problem, intended use, target, collection process, information and expectations.
2. Exact model formulation, notation, assumptions, inputs, outputs and procedure.
3. Relevant existing approaches, sources and consequential alternatives.
4. Mathematical justification, conditions and unresolved obligations.
5. Question-driven numerical analysis, configuration, uncertainty and computation.
6. Limitations, conclusions and each material frozen expectation's disposition.
7. Sources, exact versions, data/simulation identity, retained code and shared-runtime instructions.

Begin with a meaningful scientific title and a short opening stating the question, method idea, principal finding and its most important boundary. Headings can suit the scientific account. `section_anchors` identifies seven distinct scientific sections in the retained source, without a word, paragraph or equation quota. Treat the main report as a compact reading budget: select the central results and decisive exhibits needed to understand and assess this model. Define the target and exact model once, compare the closest relevant approaches and explain the principal findings. Use cross-references instead of repeating formulations, result tables, caveat lists or section summaries. Keep essential conditions beside affected claims and select the unresolved issues that materially change interpretation or use.

New runs capturing `p5.reader_report.v1` also declare `section_anchors.references`: one distinct explicit anchor immediately beside a genuine top-level References heading after all seven scientific sections. Individual references have unique stable citation anchors. This is a bibliography boundary, not an eighth scientific section or discussion target. The shared schema keeps it optional for historical records. Retained reports without it preserve their original extraction and reading behavior.

Write for a statistics or machine-learning researcher encountering this model for the first time. Develop each scientific point in connected prose, explain why a construction is needed before its notation, and interpret its defining relation. Use conventional statistical language and precise verbs. Distinguish the estimand, estimator and realized estimate; assumed and fitted quantities; oracle and feasible procedures; sampling variability, resampling variability and Monte Carlo standard error; and association, prediction and causal effects. Preserve model-defining assumptions, constraints, conditioning, normalization, fitting and tuning conventions, numerical values, units and claim strength. A tuple or notation list does not replace the defining formulation. Put citations beside the claims they support; avoid internal execution vocabulary, long dashes and promotional claims.

Organize numerical evidence around the scientific comparison. Explain the data-generating mechanism, fitting and evaluation separation, competitors' information, metric definitions and source of uncertainty. Select decisive exhibits, with captions explaining units and conditions; avoid repeating the same values in tables, figures and prose. Keep negative and inconclusive findings visible. A figure may re-express exact retained values with a declared mapping and rendering script, but new experiments, statistical aggregations or uncertainty calculations remain upstream work.

Use KaTeX-supported LaTeX, with `$...$` inline and `$$...$$` or `\[...\]` for central displays; split long equations with an aligned environment. Do not rely on custom macros or document-level TeX commands. Check the actual report Markdown through `validate_artifacts` and inspect rendered equations when rendering is available. Correct syntax without changing mathematical meaning. A syntax pass does not establish mathematical fidelity.

Claims carry readable text, exact source references and a support route, without a fixed count or a claim from every phase. Figures and tables retain their source generation/digest, caption, units and declared data dependencies. Prose numbers identify exact retained scalar values and explain rounding or presentation transformations. Keep generation IDs, digests, scalar pointers, review dispositions and detailed reproduction files in their structured records or declared supplements. The main account retains defining model equations, theoretical statements with essential conditions and interpretation, main findings, scientific attribution, essential design choices and short reproduction instructions. All proofs, proof sketches, proof-only derivations and auxiliary lemmas belong in a separate declared appendix, retained in Markdown and exposed in a separately linked in-app HTML view. Link its exact theorem/proof anchors to matching main-report statements and immutable P3 support. Secondary full tables and lengthy reproduction recipes may accompany it. Distinguish researcher descriptions, proposed assumptions, established support and measured findings.

Write the proof appendix for a statistics PhD student outside the subfield. Read the retained result, assumptions, proof route and invoked results before editing. Orient a substantial proof with its target and main reduction; explain why auxiliary constructions and consequential steps are needed, what remains random and where assumptions apply. Use meaningful rows in supported aligned displays, keeping immediate algebra compact, and connect intermediate conclusions to the target. Checked local expansions of supplied algebra or conditional reasoning are allowed within the retained assumptions and route; check every newly written mathematical step. Changed assumptions, substantive missing arguments, new results and stronger claims remain P3 work. An incomplete proof stays explicitly incomplete. The main report's compact reading budget does not impose a proof-compression rule or a separate proof-audit stage.

Each relative file link or image in the report body resolves to exactly one declared, digest-verified submitted material. Existing matching path aliases need no extra mapping. Use `artifact_authored_paths` keyed by the exact retained `artifact_id` when the report-relative target differs from its supported aliases. Each value is one nonempty report-relative path string, not an array. Additional copied scientific files require their own exact supplementary declarations. Declare copied or generated scientific files in `supplementary_artifacts` with exact relative path, media type and digest. Workspace presence alone does not establish reader or portable-export availability. Check the unique source action and portable export for each body target. Published prior scientific assessments may be declared as scientific support; private researcher dialogue and current P5 parallel review findings remain outside the first-reader submission.

For a prose scalar inside a retained JSON artifact, `source_refs` names the exact-model P4 record generation and digest, `pointer` selects that record's artifact pointer, and `scalar_pointer` selects one finite JSON number inside the digest-verified artifact. The exact artifact still travels with the submitted materials. Without `scalar_pointer`, the existing direct numeric-record pointer applies. Numeric-looking strings, paraphrases and unchecked copies do not replace the exact numerical source.

## Completion and mathematical support

The harness derives interim or complete status from retained content and support dispositions. An author's label cannot set completion. Complete reports require actual relevant numerical analysis for the exact model, with its question, relevance, data or simulation identity, analysis scope and implementation sources. Negative and inconclusive findings can be completely reported. An execution label alone supplies no numerical support. Researcher-supplied results must first be inspected and incorporated in applicable numerical work.

Synthetic mechanisms and computational checks permit work without supplied data. They remain distinct from intended-setting validation. Real data alone does not establish a suitable collection process or validation design. Baselines are required when they address a material comparative claim or expectation. Otherwise explain why comparison is inapplicable and examine stability, approximation error, limiting cases, sensitivity, cost or another relevant numerical question.

A new formal result requires completed applicable P3 support before it is presented as established. P5 explains and assembles existing results; it does not originate a guarantee. A cited established result needs the Theorist's retained check: source and locator, statement used, conditions and applicability to the exact model. A nontrivial new argument routes to P3. Unchecked conditions and missing guarantees stay qualified or open. A separate P3 run is consequently claim-dependent rather than unconditional.

An interim report identifies missing work and remains readable when execution or data access is unavailable, including before P4 exists. It cannot substitute invented numbers or imply completion. Structural checks establish integrity and declared support, not scientific adequacy or proof correctness. Completion and independent review are separate statuses.

## Independent review and revision

Review-revision requires one exact current report from the selected model lineage. Prepare its immutable packet once before parallel dispatch. Every reviewer and the revision lead receives the same report bytes, every supporting exhibit with its retained data dependencies, declared supplements, source-resolution map and verbatim review directions. Instructions have their own digest and provenance. Reader-report writing and proof directions are selected from the review run's captured catalog; old frozen catalogs and existing packet bytes retain their original directions. A review-revision run freezes its own `p5.instructions` and does not inherit assembly instructions. Repeat applicable reading-scope and appendix directions in both runs. Review the rendered main report and separate appendix as HTML; no venue or pagination fields are introduced.

The Theorist checks statements, conditions, justification, retained proof status, local expansions and appendix exposition against exact support, including cited results without P3. The Data Analyst checks implementation, displayed numbers, experiment description, metrics, uncertainty, comparison scope, question relevance and expectations. The Independent Reviewer judges whether a first reader can reconstruct the method, interpret the evidence and follow the appendix reasoning using only the report and declared materials. Parallel reviewers remain read-only; the revision Lead authors accepted exposition changes. The Independent Reviewer receives no private conversations, internal audits or later outputs, and never enters researcher dialogue or a mid-review pause. Missing context becomes a finding.

Each parallel reviewer records consequential unknowns as `open_question` findings in its owned review output. Use `issue`, `scientific_consequence`, `evidence_basis` and `requested_resolution` to explain the missing input, its implications, plausible conditional consequences and what the declared materials cannot establish. The outside reviewer uses `prioritized_issues`; the specialists use their review-finding arrays. Parallel reviewers do not write attention or `researcher-question.json`, and do not use a native host question. The serial Lead consolidates applicable questions without rewriting the original findings or implying reviewer agreement.

The lead addresses every finding with an exact issue disposition and preserves material disagreement. Exposition corrections can revise the report. Changed models, missing proofs and unsupported numerical conclusions route to explicit upstream work. Editing or omitting prose cannot create evidence or clear concerns. The original reviewed generation remains named; revision bytes have only the lead's check until independently reviewed again.

## Researcher dialogue and portable reading

Discuss whether the report faithfully describes the problem, collection process, intended use, useful demonstrations and consequential limitations. Address every material frozen expectation as met, not met, inconclusive or untested with exact support or an explanation of the gap. Saved explanations and answers cannot rewrite sources, scientific conclusions or an independent review.

Assembly and revision Leads own `p5.attention_items`, which may be empty. Phase 5 does not repeat problem, collection, model or study-design elicitation from P1-P4. Keep report-specific scientific open items in their source records or the review ledger; missing inputs remain explicit limitations while conditional or interim reporting continues, and resolving scientific work belongs to the responsible upstream phase. Use attention only for an indispensable researcher editorial choice needed to write this exact report. New attention uses schema version `1.2.0`, exact project/model scope, a named responsible audience and exact answer applicability references. Use the existing `researcher-question.json` only when that editorial choice makes the next authorized reporting action unjustified. Explain `question` and `reason`, set `blocking=true` with `scope` and `source_refs`, and retain partial work before stopping. Optional `options` and `conditional_scope` can explain the decision. Changed models, scientific targets and numerical scopes belong to new authorized upstream work. Neither a question nor a saved response starts another phase automatically.

For newly adopted P5 contracts, the existing native command/write preflight checks each stage member before any ordinary research turn. It uses that member's owned workspace, records a zero-model-turn receipt and leaves scientific review scope unchanged. A failed check prevents paid member turns in that stage. This adds no scientific stage or artifact writer. Older frozen catalogs retain their original preflight behavior.

The app renders retained Markdown and LaTeX, with the proof appendix opening in its own linked HTML source dialog. The full offline HTML edition comes from the immutable generation and contains the report, trailing bibliography and declared materials, with inline mathematical rendering, fonts and all figure dependencies. A material-specific edition retains that full bundle. Verify HTML reading, rendered mathematics, figures, citations and cross-document links, with exact sources still available. PDF generation and pagination are outside acceptance unless explicitly requested later. The offline edition includes report generation, exact model version, interim/complete status and gaps, independent review of these exact bytes and export time. Revisions never inherit earlier exact-byte review status.

Validated publication replaces only the report slot atomically. A valid interim report may publish. Validation failure preserves the previous report and retains failed candidates and reviews in the run. No report, review or suggested question starts another phase automatically.

## Compact editorial decisions

Follow the delivered frozen [user-inquiry reference](../references/research-presentation/user-inquiry.md)
for new inquiry ceilings, overlap consolidation, stable option IDs and justified
suggestion-first presentation. New attention retains exact scope, audience and
answer applicability. P5 attention remains limited to indispensable editorial
preferences for this exact report; metadata does not authorize study-fact or
upstream scientific elicitation. When an editorial alternative presents retained
mathematics differently, show that formulation and its meaning without choosing
a new scientific definition. Preserve source and answer history. Empty attention
is valid, and saving an answer neither resumes a pause nor launches work.

## Scientific meaning for the intended reader

Apply the [shared question-language guidance](researcher-question-language.md) within this phase's existing output ownership and interaction rules. It refines the existing question, context, option consequences and recommendation; it adds no artifact, questionnaire or question quota.

In P5, adapt explanations to the intended report reader while preserving the retained scientific claims and qualifications. Researcher-directed attention and pauses remain limited to indispensable editorial choices. Scientific open-question findings stay in the owned review output or source records. Do not reopen upstream scientific choices or use audience adaptation to remove necessary mathematics or limitations.

## Writing duties in existing outputs

The executable objectives give the task, shared writing core, owned output duties
and separate scientific/execution constraints. The report opening states the
problem, model idea, main result and contribution, including negative evidence
when supported. Keep proofs separate and preserve exact mathematical meaning and
necessary conditions. Review findings state assessment, support and consequence;
the revision account distinguishes the independently reviewed original bytes from
a later Lead-checked revision. Researcher questions remain editorial only;
reviewers retain scientific open-question findings in their owned outputs.

## Shared notation and presentation (catalog 1.30.0)

Assembly and revision freeze each report candidate's complete notation with the declared review materials. Reviewers check that submitted view without hidden or newer project context. Main-text translations preserve exact proof-local meanings; report-section discussion cannot publish notation or reopen upstream elicitation.

The five neutral presentation references apply through `research_presentation_v2`; shared notation is separately gated by `project_notation_v1`, which requires v2. Keep full measure definitions beside results and actual resource measurements outside mathematical notation. This adds no stage, output family or scientific authority. Retained catalogs preserve their original routing and historical local fields.
