# Phase 5: Technical report

Phase 5 assembles, independently reviews and revises a concise statistical technical report for one exact published model. It connects the researcher's problem and intended use with the formulation, mathematical justification, numerical findings and limitations. Journal selection, page quotas, novelty and publication readiness are absent from this workflow.

The technical report has its own current slot and generation history. Historical manuscripts retain their original family, scope and exact review target. A selected manuscript can be history, but never supplies the current report to continue or review.

## Assembly and exact sources

Assembly requires the exact active published model, a frozen problem-context revision and applicable problem/model sources. Freeze available exactly aligned P3 and P4 records and their explicit absence. Missing theory or evaluation does not block an interim report. Source identity includes branch, phase, family, generation, content digest and exact locator. Changed bytes cannot be replaced by a new current record.

The primary report is Markdown with LaTeX. It covers:

1. Problem, intended use, target, collection process, information and expectations.
2. Exact model formulation, notation, assumptions, inputs, outputs and procedure.
3. Relevant existing approaches, sources and consequential alternatives.
4. Mathematical justification, conditions and unresolved obligations.
5. Question-driven numerical analysis, configuration, uncertainty and computation.
6. Limitations, conclusions and each material frozen expectation's disposition.
7. Sources, exact versions, data/simulation identity, retained code and shared-runtime instructions.

Headings can suit the scientific account. section_anchors identifies the seven content sections in the retained source without imposing journal names. Their depth follows scientific need, without a word, paragraph or equation quota. An abstract, extended introduction, exhaustive literature review and full proof development are not required. Define the target and exact model once, compare the relevant existing approaches, state applicable support and explain the principal numerical findings. Use cross-references instead of repeating formulations, result tables, caveat lists or section summaries. Keep qualifications beside affected claims and synthesize the decisive limitations and unresolved expectations briefly.

Write in conventional statistical language. Distinguish the estimand, estimator and realized estimate; sampling variability, resampling variability and Monte Carlo standard error; and association, prediction and causal effects. Explain the actual model relation or statistical operation rather than inventing software metaphors. Conciseness must preserve model-defining assumptions, constraints, conditioning, normalization, fitting and tuning conventions, numerical values, units and claim strength. A tuple or notation list does not replace the defining formulation.

Use KaTeX-supported LaTeX, with `$...$` inline and `$$...$$` or `\[...\]` for central displays; split long equations with an aligned environment. Do not rely on custom macros or document-level TeX commands. Check the actual report Markdown through `validate_artifacts` and inspect rendered equations when rendering is available. Correct syntax without changing mathematical meaning. A syntax pass does not establish mathematical fidelity.

Claims carry readable text, exact source references and a support route, without a fixed count or a claim from every phase. Figures and tables retain their source generation/digest, caption, units and declared data dependencies. Prose numbers identify exact retained scalar values and explain rounding or presentation transformations. Keep generation IDs, digests, scalar pointers, review dispositions and detailed reproduction files in their structured records or declared supplements. Detailed derivations, secondary full tables and lengthy reproduction recipes may be linked as supplementary detail. The main account retains the defining model equations, decisive conditions, main findings, scientific attribution, essential design choices and short reproduction instructions, without copying all earlier mathematics. Distinguish researcher descriptions, proposed assumptions, established support and measured findings.

Each relative file link or image in the report body resolves to exactly one declared, digest-verified submitted material. Existing matching path aliases need no extra mapping. Use `artifact_authored_paths` keyed by the exact retained `artifact_id` when the report-relative target differs from its supported aliases. Each value is one nonempty report-relative path string, not an array. Additional copied scientific files require their own exact supplementary declarations. Declare copied or generated scientific files in `supplementary_artifacts` with exact relative path, media type and digest. Workspace presence alone does not establish reader or portable-export availability. Check the unique source action and portable export for each body target. Published prior scientific assessments may be declared as scientific support; private researcher dialogue and current P5 parallel review findings remain outside the first-reader submission.

For a prose scalar inside a retained JSON artifact, `source_refs` names the exact-model P4 record generation and digest, `pointer` selects that record's artifact pointer, and `scalar_pointer` selects one finite JSON number inside the digest-verified artifact. The exact artifact still travels with the submitted materials. Without `scalar_pointer`, the existing direct numeric-record pointer applies. Numeric-looking strings, paraphrases and unchecked copies do not replace the exact numerical source.

## Completion and mathematical support

The harness derives interim or complete status from retained content and support dispositions. An author's label cannot set completion. Complete reports require actual relevant numerical analysis for the exact model, with its question, relevance, data or simulation identity, analysis scope and implementation sources. Negative and inconclusive findings can be completely reported. An execution label alone supplies no numerical support. Researcher-supplied results must first be inspected and incorporated in applicable numerical work.

Synthetic mechanisms and computational checks permit work without supplied data. They remain distinct from intended-setting validation. Real data alone does not establish a suitable collection process or validation design. Baselines are required when they address a material comparative claim or expectation. Otherwise explain why comparison is inapplicable and examine stability, approximation error, limiting cases, sensitivity, cost or another relevant numerical question.

A new formal result requires completed applicable P3 support before it is presented as established. P5 explains and assembles existing results; it does not originate a guarantee. A cited established result needs the Theorist's retained check: source and locator, statement used, conditions and applicability to the exact model. A nontrivial new argument routes to P3. Unchecked conditions and missing guarantees stay qualified or open. A separate P3 run is consequently claim-dependent rather than unconditional.

An interim report identifies missing work and remains readable when execution or data access is unavailable, including before P4 exists. It cannot substitute invented numbers or imply completion. Structural checks establish integrity and declared support, not scientific adequacy or proof correctness. Completion and independent review are separate statuses.

## Independent review and revision

Review-revision requires one exact current report from the selected model lineage. Prepare its immutable packet once before parallel dispatch. Every reviewer and the revision lead receives the same report bytes, every supporting exhibit with its retained data dependencies, declared supplements, source-resolution map and verbatim review directions. Instructions have their own digest and provenance. The packet has no venue fields or page quotas.

The Theorist checks justification and exact-model applicability, including cited results without P3. The Data Analyst checks implementation, numbers, design, scope, question relevance and expectations. The Independent Reviewer is a first reader with only the report and declared materials. It receives no private conversations, internal audits or later outputs, and never enters researcher dialogue or a mid-review pause. Missing context becomes a finding.

Each parallel reviewer records consequential unknowns as `open_question` findings in its owned review output. Use `issue`, `scientific_consequence`, `evidence_basis` and `requested_resolution` to explain the missing input, its implications, plausible conditional consequences and what the declared materials cannot establish. The outside reviewer uses `prioritized_issues`; the specialists use their review-finding arrays. Parallel reviewers do not write attention or `researcher-question.json`, and do not use a native host question. The serial Lead consolidates applicable questions without rewriting the original findings or implying reviewer agreement.

The lead addresses every finding with an exact issue disposition and preserves material disagreement. Exposition corrections can revise the report. Changed models, missing proofs and unsupported numerical conclusions route to explicit upstream work. Editing or omitting prose cannot create evidence or clear concerns. The original reviewed generation remains named; revision bytes have only the lead's check until independently reviewed again.

## Researcher dialogue and portable reading

Discuss whether the report faithfully describes the problem, collection process, intended use, useful demonstrations and consequential limitations. Address every material frozen expectation as met, not met, inconclusive or untested with exact support or an explanation of the gap. Saved explanations and answers cannot rewrite sources, scientific conclusions or an independent review.

Assembly and revision Leads own `p5.attention_items`, which may be empty. Phase 5 does not repeat problem, collection, model or study-design elicitation from P1-P4. Keep report-specific scientific open items in their source records or the review ledger; missing inputs remain explicit limitations while conditional or interim reporting continues, and resolving scientific work belongs to the responsible upstream phase. Use attention only for an indispensable researcher editorial choice needed to write this exact report. New attention uses schema version `1.2.0`, exact project/model scope, a named responsible audience and exact answer applicability references. Use the existing `researcher-question.json` only when that editorial choice makes the next authorized reporting action unjustified. Explain `question` and `reason`, set `blocking=true` with `scope` and `source_refs`, and retain partial work before stopping. Optional `options` and `conditional_scope` can explain the decision. Changed models, scientific targets and numerical scopes belong to new authorized upstream work. Neither a question nor a saved response starts another phase automatically.

For newly adopted P5 contracts, the existing native command/write preflight checks each stage member before any ordinary research turn. It uses that member's owned workspace, records a zero-model-turn receipt and leaves scientific review scope unchanged. A failed check prevents paid member turns in that stage. This adds no scientific stage or artifact writer. Older frozen catalogs retain their original preflight behavior.

The app renders retained Markdown and LaTeX. Portable HTML comes from the immutable generation with inline mathematical rendering, fonts and all figure dependencies. It works offline and provides a print stylesheet for PDF export. It includes report generation, exact model version, interim/complete status and gaps, independent review of these exact bytes and export time. Revisions never inherit earlier exact-byte review status.

Validated publication replaces only the report slot atomically. A valid interim report may publish. Validation failure preserves the previous report and retains failed candidates and reviews in the run. No report, review or suggested question starts another phase automatically.

## Compact editorial decisions

P5 attention remains limited to indispensable editorial preferences for this exact
report. Apply the same consequence threshold: the preference must materially affect
the report's interpretation or use and remain unresolved by existing instructions.
Mathematical alternatives, scientific justification and missing study facts stay in
their scientific sources and upstream work, with explicit report limitations.
Empty attention output is valid. Briefly record material Lead-owned editorial choices
and reasons in the existing decision summary.

New researcher items author `decision_priority` as `interpretation`, `inference`,
`data` or `resources` and `response_kind` as `choice` or `study_fact`. This metadata
does not authorize P5 study-fact elicitation. Keep `question` to the current editorial
choice, `context_markdown` to its affected point and `likely_consequence` to its
practical effect. When useful, offer usually two or three realistic `options` as
`{id, label, consequence}` with unique IDs; open-ended choices may omit them.
`recommendation` gives the Lead's Markdown advice and reason, or the evidence missing
for advice. Do not preselect or save it as the researcher answer. Keep full sources
accessible without repeating context or imposing a word cap. Preserve exact question
scope, model version, audience and answer history. Saving an instruction does not
resume a pause or launch scientific work.
