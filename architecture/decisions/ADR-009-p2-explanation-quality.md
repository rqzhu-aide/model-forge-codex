# ADR-009: Phase 2 explanation quality and validation boundaries

Status: adopted for the September 25, 2026 follow-up implementation.

## Context

The four Phase 2 tabs separate the lead's procedure explanation, specialist
applicability assessments, lead evaluation and next work. Catalog 1.11.1 already
instructs authors to explain inputs, ordered steps, equations and output; what
changes when conditions are absent; and innovation, criticism and resolving work.
Required new fields reject empty or whitespace-only text. These checks establish
presence, not adequate scientific explanation. A vague nonempty sentence can
still pass the mechanical publication checks.

The [validation strategy](../design/06-validation-strategy.md) separates record
integrity and deterministic consistency from scientific review. The
four-tab verification (retained in the ignored local archive) exercised
scripted scientific records and explicitly did not evaluate live-model writing
quality. Existing real-provider exercise scripts do not close that gap for the
new fields.

## Decision

Keep scientific adequacy in the existing author and review responsibilities.
Do not add advisories based on keywords, list syntax, equation presence or text
overlap to `validate_artifacts`, stage findings or publication checks. This
decision covers non-blocking advisories as well as blockers. Continue to enforce
required fields, schema shape, resolvable declared references, mathematical
renderability and the existing deterministic consistency rules.

Catalog 1.11.2 asks authors to cite existing finding, proposal and literature
references when reusing a caution, then explain its consequence for the current
section. Brief recaps remain appropriate. Independent conclusions, disagreement
and attribution stay visible; the renderer does not merge or remove authored
paragraphs by inferred similarity. Existing pins and sealed records are unchanged.

Document scientific quality through a separate human review of real-provider
outputs, using the protocol below. This change adds no runtime judge, automatic
scientific repair, new member stage or evaluation harness. No new live-provider
quality evaluation has been completed as part of this decision.

## Why formatting advisories are insufficient

- A direct estimator can have a clear procedural explanation in prose with an
  inline equation. Absence of an ordered Markdown list or display equation does
  not establish that the procedure is missing. Conversely, numbered vague steps
  and an irrelevant equation satisfy that format without explaining anything.
- A specialist can identify an assumption accurately by its stable ID and
  paraphrase its role. Matching its statement text would miss that explanation.
  Repeating the assumption verbatim does not explain what its absence changes.
- A review can cite a finding without evaluating its importance. A report that
  explicitly identifies missing literature and the next comparison may be honest
  and useful even when no applicable literature entry exists to cite.
- The same caution can support distinct applicability and research-priority
  judgments. Similar wording alone does not identify redundant reasoning or
  establish agreement between independent authors.

Non-blocking warnings avoid publication failure but still direct authors' effort
and can encourage superficial compliance. They should be reconsidered only with
observed examples showing an actionable pattern and an evaluation of false
positives. Deterministic reference checks remain appropriate when the contract
declares a typed reference; this decision does not weaken those checks.

## Human review protocol

Use an isolated test project or an explicitly authorized research run with the
current adopted catalog. Exercise each Phase 2 mode with a small documented
setting, including a direct estimator, a multistep procedure, and a case with an
unresolved condition. Preserve each run's full context, exact provider/model and
reasoning settings, catalog version, run ID and source artifacts. Record failures
and cancellations as incomplete cases, not successful quality evaluations.

Read every authored proposal, targeted specialist assessment and lead
disposition against its frozen source material. For each candidate, assign
**adequate**, **needs revision**, or **not assessable** for the criteria below.
Record the exact source field or finding ID and the reason for each judgment.

| Criterion | Review question |
| --- | --- |
| Procedure | Can the reader identify the inputs, ordered computation, defining equations and output? Does it faithfully explain the original method, marking missing specifications? |
| Applicability | Does it answer when the method can be used and what each important missing condition changes, separating undefined computation, lost identification, lost guarantees and demonstrated failure? |
| Evaluation | Does the lead give a scientific judgment, evaluate the claimed contribution against available sources, identify the main criticism and specify the next resolving work? |
| Repetition and attribution | Do repeated cautions add the consequence needed in the current section, with usable source references, while preserving disagreement? |
| Researcher decisions | Are choices requiring researcher input explicit, method-specific and separated from scientific work the team can resolve? |

Also check that a claimed guarantee or novelty conclusion is supported by the
available source account. This is plausibility and evidence review, not a proof
certificate. If source material is unavailable, use **not assessable** and state
what is missing rather than inferring support from fluent writing.

Retain the item-level judgments and unresolved defects in a dated evidence
record. A successful connection test, schema-valid run or completed publication
does not count as a passing quality review. Compare revisions on the same cases
when practical, and record model or context changes that limit comparability.
