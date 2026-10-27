# Researcher communication: scientific meaning and mathematical precision

This guidance applies to existing scientific accounts, questions, explanations,
advice and report discussions. It changes writing, not scientific authority, output ownership,
answer storage or the threshold for asking a question. The executable objectives
and runtime briefs contain the instructions; this document explains their use.

## Know the reader through the conversation

Start with the finding, recommendation, answer or request that serves the reader's
task. A negative or inconclusive result may lead. Keep decisive conditions beside
their claims, and distinguish a proposed idea, an assumption, a check and an
established result. Visible numeric precision should convey the comparison and
uncertainty; exact values remain in source records.

In a decision record, `what_changed` answers what scientific progress changes the
present conclusion or use. If the conclusion is unchanged, say so and distinguish
rechecking or clearer explanation from new support. Counts, empty change arrays
and revisions remain in structured records. `principal_uncertainty` starts with
what remains unknown and its consequence, then gives the decisive obligation;
detailed verification steps remain in the linked argument or team task.

Use the researcher's stated goals, supplied scientific setting, questions and
expressed preferences to choose terminology, order and depth. A profession is not
an expertise score. A molecular biologist may know statistical theory; an ML
researcher may need an explanation of an assay. Neither should have to learn the
harness's internal vocabulary to answer a research question.

Keep necessary mathematics and connect its quantities and assumptions to the
actual population, measurements, scientific comparison and intended use. Where
context is absent, use neutral scientific language and label illustrative examples.
Do not infer a collection mechanism, causal interpretation, domain fact or reader
preference. No expertise questionnaire is required.

The canonical shared core lives in `src/model_forge_codex/researcher_language.py`.
Each executable stage objective gives its task, that core once, field-specific
writing duties and a separate set of scientific and execution constraints. The
consequential-input policy remains separate from prose style. This structure does
not create a question quota, output duty, extra review stage or pause authority.

## Preserve the scientific meaning

Clarity must preserve the target, assumptions, comparison, uncertainty, review
status and saved researcher preference. Check that meaning before judging style.
In theory, a sufficient finite stationary state keeps all three qualifications.
In option comparisons, preserve each different target revision and any noisy-audit
identification limit. A risk preference cannot be supplied by the writer.

In empirical accounts, equality observed in fitted synthetic cases stays limited
to those cases. Retain computational burden, unsuccessful fits, attempted and
returned denominators and inconclusive sampled uncertainty. A synthetic gain does
not establish benefit for people. These are interpretation examples, not facts or
defaults for an unrelated study.

Existing and started runs retain their exact objectives. Pause and P4 fallback
briefs recognize the complete current or previous canonical writing block and add
the current fallback only when neither is present. They do not rewrite retained
objectives. Newly prepared discussions use current runtime guidance and retain
their submitted bytes. Source catalog updates, application updates and explicit
project catalog adoption remain separate.

## Write one useful invitation

Use the existing fields rather than adding a second explanation artifact:

- `question`: one direct choice or factual request. Make optional status visible
  when work can responsibly continue.
- `context_markdown`: the affected scientific point and relevant formulation,
  with local symbols interpreted in the study. Give only the context needed now.
- `options[].consequence`: the changed target, constraint or condition, followed
  by its scientific meaning and material benefit or cost. Define common notation
  once. Usually two or three alternatives are enough when a useful finite set
  exists; open-ended preferences need no artificial list.
- `likely_consequence`: what the answer changes in the intended result or use,
  without repeating all option accounts.
- `recommendation`: Lead advice with its reason, when justified. It is not a saved
  answer. Study-fact requests have neither invented alternatives nor a recommendation.
- Exact sources, identities and answer revisions stay in their structured fields.
  Do not replay review history or internal identifiers in the visible explanation.

For an actual pause, `reason` gives the shared scientific context and names the
specific action that cannot responsibly proceed. Optional applicability details
say what can proceed and what remains conditional. Scientific importance does not
by itself make a missing answer a blocker. Unknown and unavailable are legitimate.

Address the researcher as **you** and the harness as **I** when useful. Name study
participants, experimental units and intended beneficiaries explicitly so that
they are not confused with the reader.

The Lead owns routine scientific and implementation choices within the agreed
goal. Missing proofs, numerical defects and diagnostics remain team work. Do not
ask a researcher to certify an assumption by accepting it. Preserve settled
answers. Retain earlier or alternative-method work in its proper scope rather
than listing it as a new obligation for the selected method.

Write as briefly as scientific completeness allows. There is no word or equation
quota, required question count, extra writer or automatic follow-up run.

## Examples for different research contexts

These are illustrative writing examples, not defaults for a user's project.

**Molecular biology: a consequential target choice.** Suppose the supplied design
has cells nested within donors and the scientific weighting target is unresolved.
Ask whether the primary result should describe an equally weighted donor population
or a population weighted by sampled cells. Let $Y_{ij}$ be the measured expression
for cell $j$ in donor $i$, with $n_i$ sampled cells from donor $i$. Explain the
sample summaries that illustrate the weighting distinction:

$$
\bar Y_D=\frac1N\sum_{i=1}^N\frac1{n_i}\sum_{j=1}^{n_i}Y_{ij},
\qquad
\bar Y_C=\frac{\sum_i\sum_jY_{ij}}{\sum_i n_i}.
$$

The first gives each donor equal weight. In the second, a donor with more sampled
cells contributes more. The target and sampling interpretation need justification;
these summaries alone do not define a population sampling model. The choice does
not make cells independent or determine a valid uncertainty calculation. Do not
ask this question if the scientific target already fixes the weighting.

**Molecular biology: optional missing information.** If matching is not established
by the supplied material: "Optional: can the before- and after-perturbation samples
be linked to the same donors? This determines whether within-donor changes can be
computed. Unknown is fine; conditional planning can continue." No artificial
equation or multiple-choice recommendation is needed for this factual request.

**RL: a consequential cost-protection preference.** Only when the preference is
unresolved, define the shared reward objective once and compare
$\Pr_\pi(G_C>b)\le\alpha$ with $\mathbb E_\pi[G_C]\le B$.
Explain that these constrain exceedance frequency and average cost respectively.
If the supplied cost represents toxicity, explain the distinction in that setting;
do not substitute toxicity for a cost whose meaning is unknown. Neither expression
alone bounds exceedance magnitude or establishes feasibility. A saved choice is
not reopened to obtain a cleaner example.

**Theory: an assumption's operational meaning.** If the retained policy uses past
measurements in its decision information, ask whether those measurements are
available before the action. Explain the relevant information-set condition and
which applicability claim remains conditional. The researcher reports timing;
the team determines what that timing means for the proof or implementation.

**Report: communication without changing science.** Use the intended audience to
choose how to introduce the retained target and interpret results. A section
discussion can explain its mathematics in domain terms. It cannot change the
target, weaken necessary qualifications or reopen upstream scientific choices.
Only an indispensable report-specific editorial preference warrants P5 attention.
