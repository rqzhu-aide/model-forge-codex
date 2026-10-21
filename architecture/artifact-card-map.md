# From authored research to the reader

P4 mappings revised October 16, 2026 for catalog 1.25.1/P4 contract 3.3.1.
P1 remains at contract 3.6.4 and P2 at 3.10.0. Installation and browser evidence
are recorded in the [implementation status](implementation-status.md).

This guide maps authored research to the current reader. Phase 1 has five
sections: Research Setting, Main Findings, Decisions to Discuss, Explore Individual Papers,
and Additional Runs and History. Shared colors and controls stay consistent across phases.
An artifact may supply several sections; it is not a card-sized file.

Catalog 1.26.0 uses the existing attention-to-card pipeline for consequential
decisions. The Lead supplies the concise affected point, practical consequence and
recommendation; structured `options` render directly as unselected radio choices.
`response_kind` separates choices from study information. `decision_priority`
orders interpretation, inference, data and resource consequences across phases.
One selection plus optional note becomes one editable exact-question instruction.
Legacy prose options remain display-only, and existing unknown answers remain
unknown. The blue team brief precedes the orange response controls; sources and
longer context remain expandable. The existing green system controls, card count,
history and explicit run-launch behavior are unchanged.

Discussion citations remain bound to the cited P1 run's published library when
questions carry into later phases. A display-only projection verifies the member,
entry identity and digest, then uses the shared blue citation preview and source
window. A missing exact reference is shown as unavailable; a newer source with
the same identifier is not substituted. Authored questions and research records
are unchanged.

P4 collection retains an authored exhibit manifest byte for byte under the
producing member's retained working files before relocating paths in the display
manifest. Both copies are sealed. Scientific references resolve by their exact
digest, while table and figure display uses the relocated paths. This prevents
collection itself from invalidating a correctly cited source.

The P1 paper-formulation scope keeps the authored fields, shapes, stages and KaTeX reader. Research Setting
gives brief essential context and notation with the interpreted goal; detailed
proposed project methods belong in P2. Main Findings remains a concise
cross-paper synthesis. Each visible paper explanation describes that source's
precise formulation or procedure and defining mathematics where available,
interpreting symbols in context. Full derivations and evidence remain in
expandable details. There are no word, paragraph or equation quotas, and
nonmethod contributions do not require invented procedures or equations.
This supersedes the detailed-setting emphasis of 1.23.3. Historical publications
retain their original instructions and provenance.

## Primary reading locations

| Phase and reader question | Author and scientific check | Existing source fields | Reader and source access |
| --- | --- | --- | --- |
| P1: What is the setting and research goal? | Lead interpretation of the researcher brief | `research_setting.statement_markdown`, `component_interpretations`, `research_goal_markdown` | Research Setting: brief essential context and notation with the interpreted research goal. Target expressions clarify the goal where needed; detailed proposed project methods belong in P2. Unknown facts and target ambiguities remain explicit. Notation opens in a popup. The header opens Project instructions, including saved setting changes; goal correction/discussion belongs beside Study goal. The exact goal source remains in its dialog. The goal is shared with later specialists. |
| P1: What is known and where does this project fit? | Lead thematic synthesis, scoped source-fidelity check and explicit relevance assessment | `landscape.summary_markdown`, `overview_item_ids`, `citation_refs`, `common_assumptions`, selected records' `explanation_markdown`, `project_relevance` and `relevance_reason_markdown`; `coverage_limits` | Main Findings: concise cross-paper methodological synthesis and approach paragraphs explaining targets, modeled relationships, mechanism, decisive conditions and fit. Equations make that account precise where helpful. Detailed derivations, common assumptions and evidence open on demand. Hover/focus citation previews and activation read the exact entry and bibliography from this account's own publication. Direct fit is highlighted with an explanation; unknown fit stays unknown. |
| P1: What does this reference contribute? | Each member owns their attributed assessment; lead corrections keep their own basis | Literature entries' `formulation_markdown`, `explanation_markdown`, `relevance_markdown`, `limitations_markdown`, `evidence_locations` and `reading_extent` (legacy accounts retain `innovation`, `definition` and `evaluation`) | Selected paper and member assessment in Explore Individual Papers. The visible contribution paragraph explains that source's precise formulation or procedure, with defining mathematics where available and symbols interpreted in context. Broad family prose or notation definitions alone are insufficient. Full derivations and supporting details remain expandable. Paper selection retains its existing searchable control. Unavailable sources and incomplete reading are stated rather than filled in; nonmethod papers retain their actual contribution without a forced equation template. |
| P1: What needs my decision or another review? | Existing attention author and Lead reconciliation; researcher gives direction | Typed contextual `attention_items`, versioned answers and existing run instructions | Decisions to Discuss displays one compact, expandable row per question before the paper reader. A red/yellow light and text show urgency; a neutral light marks a saved instruction. The consequence and one editable current instruction appear inside the row. Additional Runs and History retains the explicit enrichment request. Saving an instruction does not start a run. |
| P1: What happened in earlier work? | Retained records and actual run state, without another author | Published research bases, library snapshots, independent search scopes, profiles, original records and attempts | Additional Runs and History: status, saved run instructions, team tasks, exact earlier accounts, scientific review, library counts, source details and run history. Original metadata and correction provenance remain tied to their publication. |
| P2: What are the candidates? | Lead comparison across independent proposals and reviews | Comparison `overview_markdown` and excluded-candidate rationale | Proposed Methods: brief cross-model conclusion, separate from model selection. Publication citations remain linked. Standalone internal audit-reference groups and their separators are omitted from this overview only; substantive prose and original records are preserved. Exact audit sources remain in the selected method's review details. |
| P2: How does this model work? | Independent proposer; theorist/analyst review and Lead comparison within existing read boundaries | `method.summary`, selected `method_summary_markdown`, complete `method.mathematical_definition`, assumptions and computational profile | Select a Method to Explore: one selector and the selected model's concise methodological account with defining mathematics and decisive conditions. Full formulation, computational requirements and assumptions open on demand. Current exact models have theory/evaluation actions beside the account. Catalog-only models remain available. |
| P2: What is innovative and what is doubtful? | Lead, retaining specialist disagreements | Comparison `rationale`, independent audit headline, applicability, assessment, findings and consequences | Select a Method to Explore: Reviews and scientific sources disclosure. Historical scores carry their reasoning and missing-scale explanation. Only exact producing pins at catalog 1.24.0 or later activate the concise Lead account; older or unknown records keep the proposer summary visible and their complete Lead account disclosed. Publication is not a scientific verdict. |
| P2: What needs my decision or further investigation? | Existing typed attention author, Lead and researcher | Scoped questions, response revisions, targeted conversations, Lead suggestions, modification options and proposed evaluation | Decisions to Discuss shows one compact disclosure row per selected-model or project question. A light plus text conveys urgency or saved status. Expanding reveals Discuss, Lead suggestions and one current instruction with Save/Edit controls. Saving preserves row order and keyboard focus. Conversations use exact question context and a frozen saved-note snapshot; unsaved drafts are labeled and never silently adopted. Context and earlier question versions are expandable, with original-source instructions still editable. Additional Runs and History owns the explicit work request, team investigations and correction recovery. Saving an instruction does not launch work. |
| P2: What happened previously? | Retained publications and run records | Prior comparisons, proposal generations, model identities, exact sources and run history | One Phase run history entrypoint inside Additional Runs and History, including previous comparisons and model versions. Source dialogs preserve exact identity and return focus. |
| P3: Which claims are established and under what conditions? | Theorist; existing audit/lead judgment checks claim, assumption and argument scope | Theory statements, `regime`, `quantifiers`, `sensitivity`, `justification`, claim-map `proof_status`, `depends_on`, `novelty_refs`, falsification probes | Overall account and Claims, assumptions and proofs. Inventory links select exact graph components; declared literature references resolve only through saved P1 inputs. Missing references remain explicit. |
| P4: What method was implemented and tested? | Lead synthesis of analyst results and theorist audit | `decision_summary.method_formulation_markdown`, `implementation_markdown`, concise scientific outcome and same-evaluation `actual_data_application`; exact frozen method snapshot for older records | Summary: concise mathematical method recap, developed/tested scope and conclusion. Explicit synthetic/actual-data disposition. Full historical definition is labeled and disclosed. No numerical table or figure appears here. |
| P4: Was the implementation faithful, and can I share the code? | Lead fidelity account based on analyst implementation and theorist assessment | `method_fidelity_markdown`, `implementation_summary`, `reproduction`, verified files and `theory_audit.audit` | Implementation and Code: short fidelity assessment, material issues and portable model/example download. Full correspondence, checks, dependencies and individual files expand on demand. Unavailable downloads stay explicit. Downloads do not execute code. |
| P4: How does it perform, at what cost and under which conditions? | Analyst experiments and synthesis; Lead topical coverage; theorist validity review | Protocol sources/cases, question answers, coverage `question_ids` and `exhibit_ids`, diagnostics, eligible `metrics_long`, exclusions and exhibits | Experiments and Results: Synthetic example, Performance, Computation, Tuning, Robustness and Actual data when applicable. No data selector. All numerical tables/figures have one canonical location here; related questions link to that location. Authored coverage determines grouping; exact legacy exhibit-ID mentions are supported. DGP/design, bias/empirical SD versus MCSE, time/convergence, tuning and changed-DGP robustness remain distinct. Unmeasured work is explicit. |
| P4: What needs my decision? | Original question author, lead and researcher | Scoped questions, conversations, suggestions, editable saved instructions and pause responses | Decisions to Discuss: compact question rows with separate discussion, suggestions and Save/Edit. Active unanswered pauses stay actionable. Resolved evaluation directions are collapsed history so they do not displace current questions. |
| P4: What should run next, and what happened before? | Researcher directions; retained run and input records | Saved preparation, selected `input_ids`, local input metadata, prior publications and run history | Additional Runs and History: instructions, optional dataset/code/configuration import, explicit launch and retained history. Starting a run freezes selected file bytes. Saving directions or importing a file does not start computation. |
| P5: What is the contribution and how well is it supported? | Lead assembly/revision and in-house source check | Decision `current_conclusion`, `fundamental_contribution`, `what_changed`, technical report package, `claim_traceability`, limitations | Overall account, Report and Supporting evidence tabs. Completion gaps and exact-byte review status remain separate. Traceability supplies readable claim text, support, counterevidence, assumptions and unresolved links. `claim_support_index` remains an index, not a replacement for the detailed evidence. |
| P5: What was reviewed and what still needs work? | Theorist and analyst use their permitted frozen read sets; the outside reviewer uses its packet and declared public search; lead dispositions and revision | Exact reviewed report reference, attributed review reports, issue ledger, disposition and revision account | Overview review status and attributed Reviews. Each review links its own draft; a revised report does not inherit an earlier draft's independent review. Offline report export retains mathematics, figures and exact sources. Historical manuscripts keep their separate reader, original type and review target; PDF preview and labeled TeX source remain available. Frozen review focus and scope remain inspectable. |
| All: What needs my decision? | Original issue author; existing lead disposition and researcher response | Stable attention/issue identity, authored context, alternatives, consequence, target phase, response revisions | Issues and decisions. Similar independent findings remain separate. Explanation is a side conversation; saved answers remain editable and retain which revision later work consumed. |
| All: What should we investigate next? | Existing specialist/lead recommendations; researcher chooses instructions | Existing proposed work, `smallest_decisive_result`, `available_actions`, phase-specific follow-up proposals | Further development. State the research question and why it matters; starting work remains an explicit researcher action. |

## Projection boundaries

- The [UI contract](design/07-ui-contract.md#2-interaction-rules) owns P1 action
  placement. Main Findings has the single complete current **Research basis
  source** action; source-bound goal, citation and historical links keep their
  exact targets.
- `research.py` and `research_sources.py` expose known sections and declared,
  verified source relationships. Missing or changed sources have an explanation;
  they are never replaced by a later similarly named record.
- `ResearchDocument` renders declared narrative fields, nested headings,
  ordered steps, tables and the existing supported math delimiters. Unknown
  structured fields remain in the complete source, not recursively dumped into
  the scientific account. Code and HTML stay literal.
- P4 narrative run links use the shared math and Markdown reader. A source
  control requires the authored run URI and declared digest to match an exact
  projected record or verified retained file in the selected branch. Ambiguous
  or unavailable sources retain their authored label with an unavailable notice.
  Table explanations appear once in the figure caption; the table retains a
  title caption and an accessible relationship to that explanation.
- Stored numbers, scientific prose, code, source figure colors and original
  artifacts remain unchanged. Display formatting applies to numeric cells;
  declared uncertainty sets useful precision where available. It does not
  manufacture paired-comparison uncertainty, units or interval confidence.
- The optional `data_exhibit_ids` relationship lets a
  figure explicitly name its table exhibits in the same publication. Captions
  and filenames are not used to infer this association. Missing associations
  remain visible for older figures.
- Table pages are bounded at 200 rows and recheck the saved source. SVG
  responses use a sandboxed content policy for both embedded and direct views.
  PDF and TeX keep appropriate media types.
- Execution, hashes, receipts and full source structures stay available as
  secondary detail. They do not supply a scientific verdict.

## Author and reviewer delivery

The actual P1-P5 stage objectives, applicable schema descriptions and examples
state the reader question, support, conditions, uncertainty and decision
consequence. Existing reviewers assess explanatory fidelity within their
permitted evidence and use existing findings when an explanation is misleading
or incomplete. The outside review brief receives its frozen stage objective
without gaining access to internal records.

These responsibilities use the existing authors and review stages. Publication
checks do not judge scientific explanation quality by keywords or word quotas.
Sealed scientific outputs retain their authored bytes. Deploying the application
and adopting a workflow catalog in a project remain separate actions.

See [current verification and limits](implementation-status.md).
Automated delivery tests cannot establish the quality of future model-authored science.
