# Design 07: UI Contract

Browser UI (React + Vite), served by FastAPI on the researcher's host.
Document windows keep the title and Close control in a fixed header. Only the
body scrolls; the body is keyboard-focusable, and closing restores the invoking
control without changing the underlying page's reading position. Notation
citations save and restore the body's scroll position when returning from a paper.
Research-meaningful labels only. The current source baseline is catalog
1.28.5, including consequential nonblocking invitations. The October 23 visual
refinement uses the shared blue/team, navy (Illini Blue)/system and orange/researcher roles,
18px card titles, neutral card outlines and title separators, and the
reading rules in section 2a. The [design master](../../design-system/model-forge/MASTER.md)
and [shared styles](../../web/src/styles.css) define the visual contract.
Source checks, browser acceptance and installed-release verification are
recorded separately in the [implementation status](../implementation-status.md).
An installed app serves the built assets of its selected release; a source
preview does not update that release.

P3 overview references open the exact cited proof or supporting account in the
existing source window. Decisions and summary fallbacks use their own producing
publication's verified sources. A newer similarly named artifact cannot replace
an unavailable cited source. Closing the source window returns focus and reading
position to the invoking reference.

The Lead's change account explains the scientific change or unchanged conclusion.
The uncertainty account states what cannot yet be concluded or used before its
technical checks. Detailed inventories and revision bookkeeping remain in the
owned sources. Assumption explanations distinguish observations that must be
recorded from scientific bounds on unobserved outcomes. These are generating
instructions and field descriptions, not renderer rewrites of historical prose.

The Next line counts unanswered questions from the same projection as the
destination card. P2 destinations preserve the exact proposal or catalog
version, including the producing run for historical unregistered proposals.
Shared questions count once, alongside the currently selected method's questions;
the phase total is the unique project total. A jump to another method changes
the mounted reader selection, preserves drafts, and focuses its decision card
after reading restoration. Paused runs are checked project-wide, including a
pause already present in pending decisions but not yet in the run list. The
destination displays that run's requested input; P5 opens its recovery disclosure.
Navigation never starts or resumes a run.

The consequential-decision interface keeps one disclosure row per question.
Expanded rows put the exact affected point,
practical consequence and Lead recommendation before Context and sources. Newly
authored choice options are radio controls with a short consequence; no answer is
preselected. When alternatives change a mathematical target, assumption or method,
`context_markdown` states the smallest sufficient affected formulation and defines
its symbols. A common objective appears once; each option's `consequence` gives
its changed equation or constraint followed by its practical effect. Short option
labels remain easy to scan. Formulas do not replace interpretation, and plain
factual or resource questions do not require artificial mathematics. These rules
also apply to run pauses through their existing `reason` and option fields, and to
P5 editorial questions only within their existing editorial scope. All these
fields render LaTeX, including numerical-run pause options. A selection and optional note save as one editable instruction bound
to the exact question. Custom answers and uncertainty remain available. Study
information requests retain unknowns without inventing preference options. Legacy
prose alternatives remain readable rather than becoming fabricated radio choices.
Authored priority orders interpretation, inference, data applicability and resources
across carried questions, with numeric authored order inside a publication. Historical
unranked questions keep their stable fallback. Saving preserves focus and reading
position and never starts or resumes research. An active pause remains distinct.

P1 authoring uses the existing fields, shapes and stages. Research
Setting gives brief essential context and notation with the interpreted goal;
detailed proposed project methods belong in P2. Main Findings remains a concise
cross-paper synthesis. Each visible paper paragraph explains that source's
precise formulation or procedure and defining mathematics where available,
with symbols interpreted in context. Broad family prose or notation definitions
alone are insufficient. Full derivations and supporting details remain
expandable in `formulation_markdown` and the existing source fields. There are
no word, paragraph or equation quotas, and nonmethod contributions do not
require a forced procedure or equation template. The existing KaTeX reader is
unchanged. This supersedes 1.23.3's detailed-setting emphasis; historical
publications retain their original instructions and provenance.

P3 uses four primary cards:
an authored overview, scientific detail, issues and editable decisions, and
further work with saved instructions. P5 begins directly with the report reader,
followed by Next revision. General problem and method decisions remain in earlier
phases; section discussions handle report clarification. The overview and scientific detail share
the blue team role; discussion and further-research shells use orange for
researcher interaction, with blue team context and separate urgency cues. Progress is
a compact shared strip, derived from the frozen stage plan, collected accounts,
execution status and accepted seals. An account received is not yet accepted.
The latest failed or cancelled attempt remains visible beside retained results;
source freshness and scientific conclusions have separate meanings. P4 setup
failures ask for configuration correction and link retained logs. Research
history and original sources are secondary. P1 uses the five-card order below;
P2 separates the overview in Proposed Methods from the selector and selected
evidence in Select a Method to Explore, followed by Decisions to Discuss and
Additional Runs and History. Current action locations
are defined in section 2.
The project header shows its name, the phase stepper and a resume region. From
Phase 2 onward the region restates the opening of the trunk research goal and
links to the full P1 setting. A Next line counts researcher decisions waiting
in the P1 to P4 decision cards and opens the phase holding the first; P5
clarification stays in report section discussions, so P5 is not counted.
The stepper shows the same count under the phase that holds the questions.
Opening the decisions moves focus to the decision card and briefly outlines
it; it never answers, starts or saves anything. The existing authored overview appears
before full work status, with a compact notice above it for exact-scope failure,
requested direction or correction. Project instructions open from the P1 Research
Setting header.
Reader choices and the main reading anchor survive project, phase, method,
settings and run-history navigation. P1 and P2 share a reader within the project;
P3 through P5 retain separate method readers. Current graph selections can show
revised current theory, while P1 assessment entries and historical links keep
their exact source identity. Explicit theory navigation selects Claims and the
requested inspector before restoring its position. Equivalent polling does
not move focus or reset a table page. Verified server tables refetch their saved
page and restore both frame scroll axes during the current app session; only
the necessary disclosure path reopens. Dialog traversal includes native
summaries and frames, and close returns focus without scrolling. Field borders
have a separate control token with at least 3:1 contrast in both themes.
Implementation and verification evidence is recorded in
the September 26 revision (retained in the ignored local archive).
An installation or npm launcher update must select and start the new release
before its interface appears in the researcher's browser.

The September 27 visual audit (retained in the ignored local archive)
records the former aurora palette. Its role colors are superseded by the
October 15 blue/sage/peach revision, whose sage system role the October 23
Ironforge pass replaces with Illini Blue. The
[design rules](../../design-system/model-forge/MASTER.md) define the current
palette alongside the October 19 typography, spacing, controls and responsive
behavior across phases.

The interface includes a searchable retained P1 library, readable retained P2 proposals, cumulative
attention and P5 review issues, and structured scientific content in source
drawers. Complete technical records remain expandable. The existing P3 graph
and distinct current and historical P4 evaluation views retain their roles.

Contextual questions retain their exact sources and named destination. Their
editable response belongs with the phase that raised the issue; shared setting
questions remain in P1. Scientific work for the team is distinguished from a
question needing the researcher's preference. A researcher response does not
resolve the scientific finding. Saved answers retain the response used by earlier
work, and edits apply only to subsequent explicitly started work.

The September 13 Phase 2 branch revision (retained in the ignored local archive)
presents the lead's reviewed result first, followed by one method-branch
dropdown and the selected method's content. Method-specific clarifications
stay with their named methods; shared P1 setting questions and answers remain
separate.

## 1. Surfaces

- **Projects list**: create/open project (folder-backed), status chips.
- **Project view**: five phase tabs, trunk context for P1/P2, and a selected
  method for P3/P4/P5. The displayed method identity is checked at selection.
  Navigation uses the exact labels **Phase 1 - Define and Explore**,
  **Phase 2 - Propose Methods**, **Phase 3 - Theory**,
  **Phase 4 - Numerical Eval**, and **Phase 5 - Report**.
- **P1 project instructions**: edit the project name and one project-instruction
  field containing the research question, direction, and constraints. Project
  creation uses the same single field. The Research Setting header's **Project
  instructions** button owns reading and editing the current brief. Its dialog
  retains saved changes to setting. The run-launch dialog retains the selected
  input brief separately from its one-run instruction; that input can differ
  from the current project brief. Older split fields are combined without losing either part.
  Edits apply to new runs; ongoing and historical runs retain
  their frozen brief. The independent outside-review packet remains isolated.
- **Phase tab**: current conclusion and consequential unresolved issues,
  an explicit mode/instruction/run action, and research evidence. Readiness
  names the missing input for the selected action rather than requiring the
  previous numbered phase. Execution progress is separate from scientific
  support. History and raw records sit behind disclosure controls.
- **Phase 1 literature**: Research Setting, Main Findings, Decisions to Discuss,
  Explore Individual Papers, and Additional Runs and History, in that order.
  The setting gives brief essential context and notation with an interpreted
  research goal; detailed proposed project methods belong in P2. Unknown facts
  and target ambiguities remain explicit. It retains a notation popup and an exact-source goal
  correction/discussion control beside Study goal. Findings contain cited
  synthesis and compact, initially closed approach rows showing the authored
  title and fit. Opening a row reveals its complete account of modeled
  relationships, mechanism, decisive conditions and fit, with equations
  integrated where informative. Support qualifications remain visible on the
  closed row. This disclosure changes the initial reading density, not the
  authoring requirements or stored scientific content. Each paper's visible contribution
  explains its precise source-specific formulation or procedure and defining
  mathematics where available, with contextual notation. Detailed derivations,
  assumptions and evidence open on demand.
  All unresolved researcher questions remain discoverable before
  the paper selector. Team tasks, search scope, profiles, review and history are
  expandable in the last card. Project-wide instructions remain distinct from
  the next study's instructions. Original publication pins determine whether an
  account follows the concise contract; earlier text remains intact on demand.
  The paper selector groups equivalent official NeurIPS abstract URL paths only
  when their publication year and hash match and source dispositions agree.
  This is a reading projection: original source IDs, exact member assessments,
  citations, provenance and saved reading anchors remain intact. History counts
  accepted source records separately from grouped paper options.
- **Phase 2 methods**: Four primary cards, in order: Proposed Methods,
  Select a Method to Explore, Decisions to Discuss, and Additional Runs and History.
  Proposed Methods contains the brief cross-method Lead conclusion and its
  publication citations. Internal proposal and audit hash links in this summary
  appear as plain prose; exact records remain in details and history.
  Select a Method to Explore contains one native selector labeled **Choose a method**
  and one selected methodological account, including its defining mathematics
  and decisive conditions. Assumptions and limitations, Computation and full
  formulation, and Reviews and scientific sources are expandable sections.
  The complete proposer formulation remains accessible, including custom
  mathematical objects. Computational requirements, tuning and estimated costs
  have one home and are prospective, not measured results. Reviews retain
  independent attribution and disagreement. Only an exact producing catalog pin
  at 1.24.0 or later identifies the revised concise Lead account. Earlier or
  unknown publications show their original proposer summary and disclose the
  complete historical Lead account without clipping or rewriting it.
  Decisions to Discuss displays each question as one compact disclosure row,
  in stable authored order. A leading light and short text label indicate
  authored blocking/reassessment urgency (red), unresolved discussion (yellow),
  or a saved instruction (neutral). Color is never the only status cue.
  The card itself uses the orange researcher-interaction surface. Expanded team content uses the blue research
  surface and names its author. The instruction editor and saved researcher
  contribution use the peach contribution surface. The discussion shell and
  rows requesting input use orange before expansion. Amber **Your input needed**
  styling applies only to an unanswered researcher decision, not ordinary team
  work. Conversation replies, researcher messages and editors use the same
  blue/peach distinction. Source controls keep system fills and blue reference
  labels. Navigation, selector, Close and Cancel controls retain the system
  role even inside a warm contribution panel.
  A saved instruction is not a resolved scientific finding. The same ownership
  cues apply throughout the phase readers.
  A `research_task` marked `partially_fixed` remains pending team work with its
  authored disposition visible; it never requests a researcher choice. Project
  scope applies across method branches in the receiving phase, even when its
  latest update was published on one method branch. Model scope remains exact.
  A project-wide question explicitly directed to shared P1 remains answerable
  there even when its source is a model's P5 report work. P1 never inherits a
  selected method's private questions. Destination routing preserves the
  original question/source identity for discussion, answer revisions and
  future frozen inputs; the phase tabs and Next use the same question set.
  The full question, consequence, scope, Discuss, Lead suggestions and one
  Your instruction field appear when expanded. Save instruction replaces the
  current instruction for that exact question; Edit instruction reopens it.
  Older edits remain in storage rather than appearing as extra instructions.
  Shared understanding and earlier question versions remain expandable; each
  retained original question also has one editable current instruction.
  An explicitly carried-forward answer may be edited into a current-source
  instruction, which then takes precedence over the inherited answer in new
  work. Previous runs retain their captured instructions.
  Native disclosure controls preserve keyboard operation, mathematical titles,
  reading anchors and unsaved drafts. Saving keeps the row open and in place;
  Edit focuses its textarea, while Save and Cancel return focus to Edit without
  scrolling. This shared item pattern also applies in the other phase readers.
  Discuss opens a saved conversation with the exact component and related
  scientific context. A new conversation snapshots its exact saved response;
  an open note editor also supplies an explicitly unsaved draft, shown before
  submission. Asking a question does not save that draft as the answer.
  Lead suggestions opens a separate request with an editable starting question
  and routes to the Research Lead for recommendations, alternatives, tradeoffs
  and missing information. Its history and drafts remain separate from Discuss.
  Both use asynchronous replies and preserve their initial context for followups
  and retries. They do not resolve the question or revise the model automatically.
  Across phases, Discuss, Lead suggestions and research-goal/study-context replies
  use their own assessment instructions. For a consequential mathematical choice
  or a comparison the researcher asks about, `assessment_markdown` identifies the
  affected formulation, defines shared notation once, and pairs each alternative's
  changed equation or formulation with a concise practical effect and tradeoff. Advice states
  its supporting conditions or the missing evidence. These are conditional writing
  rules, not a fixed response template: ordinary factual questions need no artificial
  equations, and routine scientific choices remain with the Lead. Optional context
  follow-up questions use the existing `consequence_markdown` for their affected
  formulation and answer effect, with exact scope and no repeated shared explanation.
  Existing P3 assumption explanations and P5 report-section discussions keep their
  focused instructions. The normal phase catalog does not control these separate
  interactive briefs; a runtime update applies to newly prepared discussion turns.
  Additional Runs and History owns modification options, proposed investigations,
  team work, correction recovery, run history and previous method versions.
  Before methods exist, Select a Method to Explore is omitted and the work form
  is initially open. Shared research setting remains in P1; the P2 summary does
  not repeat a setting card or a shortcut to P1.
  Selecting a method reads its exact identity without starting work. Historical
  definitions remain readable and cannot silently acquire a successor's
  decisions. Beside the selected account, **Run this Method in Phase 3 - Theory**
  and **Run this Method in Phase 4 - Numerical Eval** open `LaunchRun` preparation
  for that exact selected method branch and version while P2 remains active.
  The researcher reviews the work and instructions before explicitly submitting
  the run. Browsing actions say **Go to Phase 3 - Theory** or
  **Go to Phase 4 - Numerical Eval** and open existing work. Catalog-only definitions
  remain selectable even when other models have linked proposals. The instruction
  box distinguishes using the selected method as the lead's
  starting point from exploring new alternatives. It does not promise a focused
  identity-preserving revision. P2 additional instructions and supplied formulations
  reach only the lead; specialist proposals remain independent.

- **Theory**: What is established about this method precedes Claims, assumptions
  and proofs with Claims, Assumptions, Arguments and Review tabs. The graph,
  statement inspector, exact mathematics, proof obligations and violation
  consequences remain readable. Explain this assumption, a targeted assessment
  and a publishing theory revision have distinct effects. Issues and decisions and Further theory
  development follow. Method freshness remains visible.
- **Numerical Eval**: Five cards, in order: Summary,
  Implementation and Code, Experiments and Results, Decisions to Discuss,
  Additional Runs and History. Summary recaps the implemented model in rendered
  mathematics, what was developed and tested, and the concise scientific conclusion.
  The Lead authors this account; older evaluations may display their exact frozen
  method definition, explicitly labeled, with its full fitting criterion disclosed.
  Never substitute the currently selected P2 definition for a historical evaluation.
  Summary contains no quantitative tables or figures. Implementation and Code shows
  a short fidelity assessment, material issues and a verified portable code download.
  Full correspondence, dependencies, checks and individual files remain disclosed.
  Experiments and Results is the home for every numerical table and figure, with
  topics Synthetic example, Performance, Computation, Tuning, Robustness and Actual
  data when applicable. There is no data selector. Source origin remains labeled.
  Synthetic example explains the generator and simulation design; Performance
  separates prediction error, bias, empirical SD and MCSE; Computation presents
  measured cost and recorded convergence; Tuning and Robustness keep parameter
  investigations distinct from changed data-generating mechanisms. Missing studies
  remain explicitly unassessed. Authored coverage and exact exhibit references
  determine topic placement. Earlier records may use exact exhibit IDs in authored
  coverage prose. Otherwise, the first explicitly citing question supplies the
  canonical display home; other questions retain links to it. Broad question/test
  links are fallback related evidence, never a
  reason to duplicate an exhibit across topics. Figures follow their declared data
  exhibit. Each exhibit has one location in Experiments; cross-topic links reveal
  it and move focus there. Complete answers, reviews and diagnostics remain
  available. All disclosures have stable reading anchors.
  Decisions retains the single editable instruction and separate discussion
  and suggestion actions. Saved evaluation directions use a collapsed, counted
  disclosure; an active unanswered pause remains expanded and actionable.
  Additional runs contains saved preparation, explicit
  local-file selection, scope, managed budget and history. One evaluated method
  is initially selected for reading without changing the project's active
  method. Deliberate choices and reading position survive polling. Earlier
  evaluations use their own summaries, evidence and availability labels.
- **Report**: Technical report and reviews opens directly on the complete report,
  with Supporting evidence, Reviews and Changes as secondary tabs. There is no
  duplicate overview before the report. Source identities and report tools are
  compact disclosures. Completion gaps and independent review status remain
  visible and separate; review of an earlier draft does not transfer to a revision.
  Each of the seven authored main section headings has an orange **Discuss**
  icon and label. It opens the existing fixed-title discussion window for that
  exact section and report version, with focus returned to the section on close.
  The Research Lead receives the selected section, its original frozen context,
  relevant supporting sources and the saved comment as of each question.
  Earlier turns and retries retain their own context snapshots.
  A separate **Leave a comment** editor saves one editable comment per exact
  report section and version; removal retains edit history. Comment drafts survive
  closing and request errors. A concurrent edit requires explicit reload before
  saving, and delayed responses cannot erase newer drafts. Comments do not revise
  scientific records, adopt shared study facts or start research work.
  Review comments, lead responses and researcher direction remain separate.
  Next revision follows the report; Phase 5 has no general Discuss your problem
  card. Genuine execution pauses and correction controls remain reachable within
  Next revision. Its shaded contents are clipped to the card's rounded outline,
  preserving the border and title separator. The report uses concise statistical
  prose, defines mathematical quantities at first use and places detailed
  derivations, secondary tables and reproduction recipes in linked supporting
  material. Scientific gaps stay qualified in the report and route to the
  relevant earlier phase; only indispensable editorial choices ask for new input.
  The outside reviewer still receives only its review
  packet; the lead explains an outside comment as an attributed interpretation.
  Retained candidates and Historical manuscripts have separate tabs when present;
  historical manuscripts retain their original type, scope and review target.

- **Run view**: live activity feed (heartbeat stream), per-stage status,
  usage/rate-limit telemetry, findings panel, correction authorization
  control (with the findings shown verbatim), cancel control.
- **Recovery progress**: artifact correction shows its purpose and attempt
  number. A stopped automatic repair keeps the findings and existing explicit
  correction route available. P4 distinguishes a rejected request, unavailable
  validation and an unconfirmed operation outcome. Unknown outcomes direct the
  researcher to inspect saved work before another attempt; they never assert
  that nothing executed. Raw field pointers, errors and retained attempt
  receipts are available in Recovery details. Historical inspection questions
  use their own saved receipt and describe its recorded uncertainty; they do
  not inherit the current question's feedback or imply that a later accepted
  continuation is still uncertain.
- **Workspace controls**: the bottom of the desktop sidebar contains Team
  Settings, a persistent Light / Dark theme choice, and OpenAI Account.
  Research is opened through the project list. Narrow layouts keep these
  controls together below the project list without covering the research view.
- **Team Settings**: Research Lead, Theorist, Data Analyst, then Outside
  Reviewer, with Research Lead selected initially. Model/provider, reasoning
  effort, instructions, and token thresholds. A shared provider file can
  supply the connection and model settings; its effective values are shown
  directly. Without that file, custom providers use the manual Provider ID,
  model, Base URL, API-key environment variable name, and reasoning effort
  fields. No provider preset is required or selected. Keys stay on the host,
  in the provider file or environment. A Responses-compatible
  endpoint can be used directly; the optional [Responses shim](../decisions/ADR-008-responses-shim.md)
  supports a Chat Completions upstream through its configured Base URL.
  Unsaved drafts survive navigation in the browser session. A **Test
  connection** action per member checks the effective settings with one
  bounded live exchange (§3). A
  skill-pin editor and memory-policy controls are not currently exposed.
- **OpenAI Account**: explicit connection to available host credentials or
  official device sign-in, with visible pending, connected, and error states.
  Existing member credentials remain intact. Credential material stays on the
  host; read-only example previews disable account mutations.
- **Source access**: exact generation readers and run detail remain available;
  journal and receipt endpoints support inspection. A complete authority
  dashboard is not required in the main research workspace.
  A whole-record source drawer does not repeat a link that reopens itself.
  Exact reviewed-version references, files, supplements and exports remain available.

## 2. Interaction rules

P1 gives each current action one primary location:

| Action or source | Location |
| --- | --- |
| Read or edit current project instructions | **Project instructions** in the Research Setting header; saved changes to setting remain inside its dialog |
| Correct or discuss the Lead's interpreted goal | Beside **Study goal** in Research Setting; the confirmation text remains after saving |
| Inspect the complete current research basis | **Research basis source** in Main Findings |
| Inspect the exact goal being corrected | Inside the goal dialog, tied to the original committed paragraph |
| Read a citation or earlier publication | At its cited passage or history entry, retaining its exact generation |

The current brief is not repeated as a bottom Saved project instructions
disclosure. Decisions to Discuss does not repeat the generic goal action, and
the saved-goal confirmation does not add another Review correction action.
Setting and current-account history do not add links to the same complete current
research basis. Exact citations, goal targets and historical generations retain
their own source access. These placement changes do not change the scientific
catalog, authored outputs or researcher controls.

P2's Proposed Methods summary renders internal proposal and audit hash links
as plain prose, without raw-record source controls or a shared-setting P1
shortcut. Publication citations remain active. Reviews and scientific sources,
selected-account details and history retain access to exact records. The nested
Not retained disclosure does not add an assessment source control.

- Run and assessment requests carry idempotency keys; repeated submission
  returns the original run. Method selection includes the displayed identity.
  Other configuration/control endpoints do not implement a universal sealed
  command ledger.
- Gates are explicit human clicks; nothing auto-authorizes.
- Basis staleness: the Run action stamps the rendered basis; the service
  refuses on mismatch with a re-open message.
- The phase's reading positions remain present before results exist, with truthful
  empty states once a method is selected. P3 through P5 first show a method
  chooser when there is no selected method. Phase navigation summarizes work
  across methods explicitly in that context; a selected method always shows
  only its own state. Waiting for direction takes precedence over older results.
  Core scientific content uses visible headings in one level of
  phase-specific tabs. Graph inspection and complete document readers remain.
  History and source files use secondary disclosures.
- Further-work instructions persist by project, phase and method. Unsaved
  browser drafts also retain that scope. Save instructions does not start work;
  the visible work form provides a separate explicit start. Selected scientific
  issues are carried by exact references rather than copied identifiers.

- Taking another look saves an assessment and discussion without replacing
  theory, modifying its formal status, or launching a repair. Follow-up stays
  linked to the assessed version. An explicit repair carries the selected
  assessment into the normal reviewed P3 revision process.
- A source-linked P3 assumption also has a conversation icon. It opens an
  **About this assumption** dialog with a labeled question field and saved
  conversations; opening history makes no model call. Each conversation uses
  its original assumption, method, and frozen sources. Earlier versions are
  grouped explicitly by stable assumption ID within the same branch and record
  family. Claims and unresolved graph nodes do not get this control.
- Identified scientific issues in all phases have the same Explain more action.
  The discussion stays with its exact source version and responsible role.
  P3 assumption explanations use the theorist. Implementation issues normally
  use the analyst. Outside-review comments use the lead without reopening the
  outside reviewer's context. Opening the discussion sends no request.
- Explanation runs are isolated from scientific publication and continuing
  member memory. They remain out of focused scientific assessments and future
  research inputs. Closing the dialog leaves accepted answers running. Pending,
  failed and completed attempts survive reload, and explicit retry retains the
  failed attempt. The isolated explanation controller can answer a question
  while P4 awaits direction without resuming its experiments.
- Inline discussion references become source-window controls only when they
  match an exact retained reference from that conversation. Unverified local
  paths and arbitrary API links are not opened. The original authored transcript
  stays unchanged; structured source families may still require source details
  when no narrative reader exists.
  A report-section conversation's own frozen source also qualifies, including
  its verified section anchor. It does not need to be repeated in the answer's
  additional evidence list.
- Explicit scientific finding subtypes remain team work, with their authored
  statement as the row label. They offer source and discussion controls without
  a researcher-answer editor. Existing saved notes remain readable. Explicit
  researcher decisions retain their single editable instruction.
- A later noncancelled attempt supersedes an older correction indicator only
  for the same phase, branch and scientific work target. The failed run remains
  visible in history; another target or an explanatory conversation cannot
  suppress its correction indicator.
- P4 answers can be saved and edited before an explicit Continue, Finish or End.
  Continuing consumes the exact saved response revision. Work already using an
  earlier answer keeps it. Other phases apply saved direction to the next
  explicitly started work and do not present a false Continue action.
- An interrupted-experiment message is tied to the current decision's exact
  recorded attempt reference. An older failure elsewhere in the ledger does
  not explain a new scientific question. Retained partial results remain
  provisional. Current accepted feedback clears an earlier request error from
  the progress strip; checkpoint feedback remains inspectable as history.
- Recovery uses the existing decision form and Save, Continue, Finish and End
  controls. It does not introduce another response editor or automatically
  restart an experiment. The displayed state comes from saved run/controller
  records rather than a browser-only assumption about execution.

- Keep project, method, phase, and selected component when opening a run or
  settings and returning. Show failed loads, interrupted work, and disconnected
  activity streams with a recovery action.

## 2a. Visual and density requirements

Use the shared blue/navy/peach purpose palette with calm reading surfaces
and one compact, intuitive sans-serif heading per card. The main surface
should explain the current scientific conclusion and the next useful
researcher action. Counts, stage files, thread IDs, and raw JSON belong in
execution or source detail.

The shared type scale applies to both direct and wrapped card headings:

| Element | Size and treatment |
| --- | --- |
| Project title | 26px Marcellus; 21px on narrow screens |
| Main card heading | 17px Plex, weight 600, consistent title strip |
| Selected method name | 17px document title |
| Ordinary subsection | 16px, weight 600 |
| Scientific prose and researcher writing | 16px; scientific prose retains 1.65 line height |
| Compact controls and metadata | 13px; meaningful status at least 12px |

Researcher writing includes editable fields and saved contributions. Preserve
the 16px card gaps, 8px corners and 14px by 16px body padding (12px on narrow screens).
Cards use neutral hairline outlines and separators below the title strip, with
decorative corner fittings. Inner sections keep lighter dividers and flat bands. Decision questions may
use up to two lines on desktop while markers and status labels stay in stable
positions; narrow layouts wrap the full question. P4 narrative uses a 72-76ch
measure while tables, equations, figures and code retain the wider card area.
P1 Research Setting does not repeat the project name already in the page header.

Light remains the default; dark uses coordinated slate surfaces and readable
text with the same semantic colors and interactions. Authored scientific
figures keep their original colors and a white canvas in both themes.

Scientific findings use a labeled Finding badge; execution uses a separate
compact status pill. An absent outcome is Not assessed, even after successful
execution. Purpose colors never imply urgency or scientific support. Issues
and decisions distinguishes unanswered decisions, an evaluation still waiting
for direction, open team research, correction needs and saved responses.
Responding does not resolve a scientific finding. System selection uses Illini Blue,
independently of these states; research contribution controls use warm focus
tokens. Disabled labels use readable colors
instead of blanket opacity.

The existing shared `ActionButton` defaults to `data-ui-role="system"`.
Writing and editing researcher direction, asking questions, discussion,
suggestions, focused research assessments, and research preparation or launch
explicitly use `data-ui-role="research"`. The primary visual variant does not
assign that role. Settings saves, navigation, selectors, ordinary reading disclosures,
source controls, Close and Cancel remain system navy, including inside warm panels.
Inline publication citations use blue citation tokens in both themes, even
inside a system-role panel. Citation text and hover/focus previews retain blue;
general source-opening controls keep system fills and blue reference labels.
Unselected buttons and tabs retain their filled backgrounds. Team replies and
all authored scientific accounts, table headers and inline code remain blue. Discussion and
further-research entry points use orange; disclosures that open a researcher
response editor are research interactions, not generic system navigation.
Expanded team questions, reasons, options and proposed-understanding context
use a flat blue band before the warm response area. P2's original researcher-supplied
method and source use peach; the team's reformulation remains blue.
The role changes color without changing
handlers, labels, disabled
behavior, disclosure operation or focus restoration.

Theory assumptions are neutral, solid and rounded. Claims show their proof
status in text; only cited proofs use a dashed outline. Missing or unresolved
support differs from contradiction or a failed probe. Selection adds an outer
outline while preserving the scientific status stroke. The drawn legend uses
the same shapes and labels.

Keep mathematical hover/focus previews, pinned graph inspection, and readable
focused neighborhoods. Expand experimental detail around a selected question;
retain every recorded estimate, applicable diagnostic, caption, and source in
the detail views. Reduction in overview density must not remove evidence.
Narrow layouts, keyboard use, dialog focus, and zoom require acceptance checks;
a build alone is not visual or interaction verification.

P4's three scientific cards are Summary, Implementation and Code, and Experiments
and Results, followed by Decisions to Discuss and Additional Runs and History.
They supersede the older side-by-side implementation and theory accounts.
Within Experiments and Results, topic accounts and their explicitly mapped
exhibits come first, with full question answers and complete numerical diagnostics
in disclosures. Shared cases do not
override conflicting test or metric associations. A follow-up carries the
exact inspected question and protocol into the launch dialog and server
request. Theory context compares linked claims and dependencies with the
tested generation; unknown provenance stays unknown. Historical claim links
open historical theory, with a separate action for the current graph.

When the Analyst declares a primary account, question source controls say
**Open full Analyst account**. The existing Research source dialog loads that
account lazily from its exact published run and verifies its digest. Markdown
and bounded JSON previews render the authored prose and mathematics; the exact
original remains linked. The compact structured record stays in source details.
Informal question keys in a full account never replace or remap structured
question IDs, and unavailable sources keep an explicit error.
Inline P4 `run://` locators resolve through verified bindings from the same
published evaluation's sealed record digests or declared artifact pointers.
Declared reproduction pointers and source-registry entries with an exact output
URI and digest are included. A registry filename is descriptive, never a path
search; run, package, stage, containment and digest boundaries remain enforced.
An unbound path never becomes a link merely because a retained file exists.

Diagnostic completion counters retain their source values. The contract's
`n_failures` includes unrun cases and reported nonconvergence, so the UI calls
it "incomplete or nonconverged" rather than claiming solver failures. This
aggregate alone does not receive failure coloring. Diagnostic runtime totals
are labelled as sums of recorded case times, not elapsed experiment time.

Catalog 1.13 adds authored P4 implementation and algorithm-fidelity accounts and
a theory relationship with three explicit states: unavailable, available but
not tested, or specific statements tested. Older accounts report missing fields
without inventing them. Numerical agreement is not a proof. Provisional plans
and observations remain distinct from reviewed findings. Detailed attempts and
prior evaluations stay in research history. Finish remains unavailable before a
valid plan exists; a stopping state precedes waiting until owned work stops.
P4 shows one current plan, with other recorded plans and full settings in
disclosures. Skipped work and inferential consequences stay visible. Question
answers expand on selection; independent review reasoning remains inside each
answer's labeled disclosure with its limitations intact. Legacy
overview gaps remain explicit without empty columns. See the
UI revision verification (retained in the ignored local archive).

## 2b. Artifact rendering (SPEC §6)

- **P2 direct records**: exactly three proposals, two targeted cross-audit
  reports and one lead comparison supply the workspace. Method titles,
  summaries and exact definitions remain proposer-authored. Reconciliation
  records the lead's assessment without silently rewriting those definitions.
- **P2 short authored content**: the lead comparison's `overview_markdown`
  supplies the result overview. Each disposition's `method_summary_markdown`
  explains the procedure, algorithm and related equations in Method; its
  `rationale` supplies the separate evaluation of innovation and criticism in
  Review. Each targeted specialist assessment's `applicability_markdown`
  supplies conditions and cautions in Assumptions, attributed to its author.
  These additions explain rather than alter the original method definition.
  Audit finding titles, reasoning and consequences remain visibly attributed.
  These fields are authored in the same six records, with no display writer,
  duplicate summary artifact or numerical scoring requirement.
- **P2 steering decisions**: during synthesis, the lead identifies unresolved
  choices that materially require the researcher's preference or input and
  records them as method-scoped `researcher_decision` attention items. Each
  states the relevant mathematics, alternatives and consequences. Existing
  questions and answers retain their identities; shared setting decisions stay
  in P1. Scientific checks and repairs remain team tasks. The UI displays the
  authored decisions without inventing questions or inferring preferences.
- **Nonblocking invitations**: a consequential request can be displayed while
  conditional research proceeds. The Lead briefly explains what the answer
  affects and when it is useful. Requested input and a paused run remain distinct;
  the reader does not infer a launch prerequisite from an unanswered row. Existing
  Discuss, Lead suggestions and one editable instruction supply the interaction.
- **Exact source navigation**: optional audit `statement_refs` are JSON
  Pointers into the assessed original proposal. Display the original equation
  or algorithm step; do not infer anchors or manufacture repaired definitions.
  Proposals, audits and comparisons stay linked to their exact producing runs.
  Lead procedure summaries, lead evaluations and specialist applicability notes
  open their cited paragraph directly, with the complete source record available.
- **Historical compatibility**: earlier P1/P2 cards and phase summaries remain
  readable under their original shapes. Missing new P2 procedural summaries,
  applicability notes, overviews, headlines, titles and source pointers remain
  absent. The UI offers the original detailed
  text without generating replacement scientific content. Legacy numerical
  assessments, when present, do not stand in for the current proposal/audit
  workflow.
- **T3m** is readable scientific material with source access, including the
  current technical report and historical manuscripts. Referenced T3w
  files support reproduction and inspection but are not a second systematic
  artifact list. A source link resolves its actual producing run and digest.
- **P3 scientific detail**: statements retain their exact assumptions, proof
  obligations, probes and frozen literature sources. Multiple matching source
  accounts stay separately attributed; a convenient first match cannot replace
  another member's assessment.
- **P4 implementation**: Implementation and Code reads the authored implementation account,
  method-to-code correspondence, environment, checks and limitations. Code,
  settings and check files resolve to retained source bytes. An implementation
  account does not imply an independent rerun of the computation.
- **P4 plots and tables**: figures preserve their source colors and open in a
  keyboard-accessible enlarged reader. Linked data tables use explicit exhibit
  references, readable labels and units. Large tables paginate without dropping
  rows. Exact recorded values, counts and uncertainty remain accessible beside
  exhibits; small nonzero values must not round to zero. Failed, unperformed,
  invalidated and missing observations retain distinct meanings. No confidence
  interval or standard error is invented by the display layer.
- **P5 supporting evidence**: the claim-traceability reader opens the exact
  frozen upstream support, counterevidence, assumptions and source files.
  Unresolved links stay explicit. The report reader shows completion gaps,
  exact model identity and review status. Historical manuscript readers retain
  their intended audience, included sections and review scope. TeX source and a rendered
  PDF are labeled distinctly; source text is not silently presented as rendered
  manuscript prose.
  Current report claim cards retain each authored qualification and exact report
  reference. A missing per-claim assessment remains absent; the projection must
  not invent a `not_assessed` outcome. Internal support-route classification
  stays in source details. Readable source-family labels accompany the exact
  generation controls, and unresolved sources keep an explicit explanation.
  Inline report links prefer a unique explicit authored-path mapping over upstream native aliases, while retaining source verification and exact digest checks.
  Links to retained Markdown support open in the fixed-title source window with
  rendered mathematics, tables and figures. A fragment selects its authored
  section; nested relative links use that document's path and the same verified
  material map. Closing restores the invoking control and report position.
- **Portable report**: every required source is resolved and digest-verified
  before rendering. The renderer receives compact verified file descriptors
  and embeds only assets actually used by a report link or image, checking
  their bytes again when read. Unused large diagnostic sources are not copied
  into its transient input. A deliberately external local-service link remains
  external and requires an explicit portability explanation in the report.
  Exported provenance records the exact generation, report digest, completion
  and review status; review of an earlier version does not transfer to edited bytes.
  Referenced Markdown support renders through the same scientific renderer in
  collapsed appendix disclosures, with namespaced anchors. Declared document
  identities prevent cycles and duplicate copies; unreferenced files remain unread.
- **Scientific documents**: readable headings, ordered procedures, nested
  lists, tables, literal code and mathematical delimiters are retained. Exact
  source access remains available. Display normalization is narrow and does
  not rewrite the stored authored record. Source SVGs are sandboxed when opened
  directly or embedded so scientific figures cannot execute active content.
- Current technical reports have no venue or fixed page-length requirement.
  Older manuscript venue preferences remain historical metadata.
- **Token controls**: optional per-member auto-compaction and token ceiling
  settings. Current ceiling handling can rotate after a turn; it is not a
  guaranteed mid-turn spending cap.

## Shared visual meaning

Color follows purpose across every phase, independently of specialist identity,
phase number or scientific outcome. The same light/dark `--team-*`,
`--system-*` and `--contribution-*` token families apply to current and older
phase readers. Existing aliases retain the shared role meanings:

| Purpose | Color |
| --- | --- |
| Team-authored phase summary, lead account, research setting, method, theory, evidence or manuscript | Blue |
| Publication citations and their previews, including within system-role panels | Blue in both themes |
| System navigation, settings, selectors and reading disclosures | Navy when selected; neutral stone otherwise |
| Source-opening controls | System fills with blue reference labels |
| Further-research request shells | Orange; blue authored recommendations within them |
| History and system activity shells | System styling, with history on library parchment; blue authored scientific records within them |
| Discussion card shell and rows requesting a response | Orange; blue team context and peach researcher contributions inside expanded rows |
| Researcher writing, saved instructions, questions, conversation messages and editors | Peach, with warm cream fields |
| Research contribution, assessment and launch actions | Warm buttons; terracotta/peach primary action |
| Requested researcher input | Orange row before expansion; amber status label and marker, red for explicit blocking/reassessment |
| Ordinary saved-status feedback | Neutral status badge; saved researcher words retain peach |
| Execution progress | System shell, with separate explicit state badges |

Completed execution is green, active work blue, waiting for direction amber,
and failed execution red. Cancelled or unperformed work remains neutral. These
signals describe execution, not scientific support. Text labels accompany color;
changing a method's author never changes its reader color. System controls
never indicate scientific success. Saving a response does not clear an unknown,
waiting or blocking state and does not resolve the scientific finding.

Shared outline icons distinguish conversations, reading details, opening a
source, requesting an assessment, and requesting a theory revision. Buttons that
open sources or existing records say **Open**; phase browsing says **Go to**
followed by the exact phase label. General launch-form actions say **Prepare**;
the selected P2 method uses **Run this Method in Phase 3 - Theory** or
**Run this Method in Phase 4 - Numerical Eval** to open preparation. The launch form's
submit button says **Start**. **End run** consistently cancels
remaining work without publication. Pause and finish-with-evidence retain their
different consequences. P2 and P4 use the same tab treatment, and all inline
disclosures use one directional cue. Answered questions use past-tense labels
and neutral styling. Outstanding waiting evaluations are visible, not hidden
inside a closed history disclosure.

### Compact revision summary

After a scientific attempt, Phases 1 through 4 show one **Revise and rerun** card. It summarizes
existing inputs and navigates to their original editors; it does not duplicate
forms, request a Lead assessment, or start work. Phase 5 shows **Revise report**
with preparation status, retaining discussion at each report section rather than
adding a general problem discussion.

- **Your answers to my questions** counts current applicable saved answers, unanswered
  questions and saved unknown responses separately. Exact source identity and
  explicit answer applicability follow the original question projection.
  Scientific findings, team tasks, superseded questions and operational pause
  history are excluded. A local unsaved edit is an additional indicator on the
  same question, never another answer.
- **Other information you gave me** counts separately saved notes and confirmed
  interpretations within the current model scope. Copied question or pause answers
  are excluded even when their original question is in another phase or history.
  An empty row says **None added**, not an unanswered task.
- **Please check my interpretation** appears only for a pending interpretation
  the researcher can confirm. Saving an answer never creates a second review task.
- **Instructions for my next run** reports saved or unsaved instructions, selected files and
  the existing launch form's input check. Response completion is not scientific
  readiness and does not introduce a new launch gate.

Labels navigate to the corresponding section; nonzero counts open the first
exact matching item. Zero counts remain text, while the row label reaches its
honest empty state. Navigation opens enclosing disclosures, focuses a heading or
summary without entering an editor, clears the sticky toolbar and briefly marks
the destination. **Back to rerun summary** restores the invoking control and
reading offset; if saving removes that count, it returns to the same row label.
Changed or ambiguous sources are reported rather than replaced by a guessed
destination. Polling never replays navigation or changes answer status.

One preparation card changes with the current phase's scientific history.
Before its first scientific run, **Instructions and run settings** opens directly
to the preparation form, with no rerun summary or duplicate heading. Once a run
exists, **Revise and rerun** (P5: **Revise report**) contains the compact summary
and a nested **Tell me what to do next** disclosure. The nested form is
collapsed on a fresh visit, remains mounted, and retains the original explicit
Start action. A title transition during work preserves the open form and drafts.
P4 **Prepare further work** enters this same card with the issue's exact source,
retains the draft and run settings, and offers **Back to research question**.
It neither opens a second launch form nor starts work. A phase or method change
clears any pending navigation request for the former scope.
P1/P2 use shared trunk history; P3/P4/P5 use the selected method's history.

### Directional language and one answer editor

Interface text addresses the researcher as **you/your**. **I/me** denotes the
harness speaking to the researcher. Name a particular team member when attribution
matters, such as **The Lead recommends**. Stock response choices use neutral text
such as **Not sure yet**; authored and historical researcher text stays exact.

The revision summary is headed **What I’ll use in the next run**. The input
destination is **What you told me**. A genuine proposed interpretation is labelled
**Please check my interpretation**, with **Confirm interpretation** as its action.
P5 retains section comments and report revision settings, without adding a generic
problem discussion or duplicate comment count.

A saved answer is edited at its original question or pause request. Its context
copy is read-only, linked back to that owner and excluded from extra-input counts.
Use the reserved answer-copy identity or explicit saved-answer context reference;
answer citations alone do not make a genuine interpretation a copied answer.
Generic context editing and interpretation confirmation cannot overwrite an answer
copy. Normal question edits update that same copy and retain earlier revisions.
Current sequential and evaluation pause owners suppress only their exact duplicate
question/answer projection. Other source versions remain reachable in history.
Navigation follows exact anchors, opens disclosures, preserves return position and
keyboard focus, and never repeats automatically after a refresh.
Failed attempts and retained publications count; focused discussions and
assessments do not. The first P2 publication may select a method for reading,
but it preserves the mounted shared preparation form and its draft. Only an
explicit method choice changes preparation to that method's own draft and seed.
The shared preparation choice is retained through phase navigation, run-history
return and reload. With one automatically displayed method, **Prepare work on
this method** provides that explicit choice without requiring a different method
to be selected first. Team work and history remain siblings. Team recommendations
remain blue, researcher input is orange, and system settings/navigation are
navy. Activity and Record role markers remain teal-green. The revision card shell uses
muted purple in both themes, including its title band, outline and separators;
its controls retain their original role colors. Card headings remain 17px with a neutral
outline and title separator. Exact question and context anchors, same-tab draft
notifications, reduced-motion behavior and scope-bound return sessions preserve
keyboard access and drafts without adding a scientific artifact contract.

### Phase 3 theory preparation

The P3 card uses the same lifecycle, with **Establish theory** and **Revise theory**
as separate work choices. Its heading follows scientific run history; the initial
work choice follows server eligibility. An untouched form prefers revision when
eligible, otherwise establishment. A saved or explicitly selected mode remains
selected through polling. Failed first work does not establish a revision basis,
and an assessment alone does not turn the initial card into a rerun card.

Revision actions from a claim, assumption, saved assessment or phase issue prepare
this one card. Preparing next work from a P3 pause also reaches it. Assessment-only
requests remain separate because they save an assessment without publishing theory.
Preparing, saving, choosing sources and answering questions never start a run.
The final action names the work: **Start theory development** or **Start theory
revision**. Current work, including a pause, continues to block another launch.

A focused revision displays the exact selected component and its source inside
settings, with an explicit action to clear the focus. Its scope includes affected
consequences and still produces a complete theory account. The component target
and optional assessment ID remain separate from selected issue sources. The
existing contract supplies current aligned theory and optional empirical evidence;
there is no extra baseline selector, scientific stage or readiness score.

Current issues authored in another phase can be carried into P3 with their exact
source phase and provenance intact. Selected sources outside the current-phase
issue list appear under **Additional selected issue sources**, labeled **Selected
source N**, with factual copy that they remain attached to the request. This group
does not imply that a source is earlier or has been replaced.

P3 scientific accounts render inline saved-source citations through verified
bindings from their producing publication. Run links require a matching sealed
output; artifact and relative links require one declared, digest-matching file;
generation links retain the exact source in the producing run's frozen basis.
The same projection serves current and historical documents. Blue source controls
open these exact records or existing artifact URLs. Missing, changed or ambiguous
sources remain readable with **source unavailable**, without a current-source
substitution or arbitrary file lookup.

Reusable instructions persist for the method lineage. Exact target metadata is
retained beside the prose in the browser draft and is checked against the current
theory and full method identity before launch. Missing or changed linkage keeps
the inspected target visible and blocked until the user clears or reselects it.
Neither polling nor a new publication silently substitutes a target. Generated
directions are shown separately from researcher prose so replacing or clearing a
target cannot leave contradictory old directions. Successful launch cleanup must
not discard edits made while launch was pending. Failed launches keep preparation.

An explicit preparation action opens the settings and focuses a stable element
below the sticky toolbar, with a return path to the invoking component. Ordinary
refresh does not repeat that navigation. The compact summary remains an overview
of the original question and study-understanding editors.

## 3. Live updates

Team Settings identifies the effective provider's source. When a shared
`providers.toml` is present, show its location, the effective member model and
connection, and credential source/status. The guarded **Edit provider file**
editor validates and atomically rewrites the file, refusing the save when the
file changed on disk since the editor loaded. Keys appear only in that editor,
masked until revealed. The file governs the members it names; absent members
keep their per-project settings. An optional shared default may be inherited
while other members use different connections. Display the selected member's
resolved connection in each case. File-governed provider settings are shown
from the file; instructions and token controls remain editable.
**Refresh settings** rereads the file while retaining unrelated unsaved edits.
An invalid file is shown as a blocking configuration error, not as an effective
manual fallback; the editor loads the error for repair. Without a file, the
existing member provider form remains.

**Test connection** is available per member in Team Settings and inside the
provider file editor. It tests the member's effective settings (saved file
and stored settings, or the editor's unsaved draft) in one bounded exchange
of at most 45 seconds: configuration, connection, one model response, one
tool round trip, and a final response, with each stage reported. The result
is ok, partial, or failed, with a classified, credential-redacted failure and
elapsed time, and is labeled **Saved settings** or **Unsaved draft**; a
simulated backend marks the result as simulated. Changing a relevant field or
inherited default clears the displayed result, and a result that arrives after
such a change is discarded. The probe uses an isolated throwaway home that is
deleted afterward, never touches research threads, runs, or project documents,
and may consume a small number of provider tokens.

Run activity streams over SSE. Show recorded stage/member progress and
terminal errors without inventing experimental progress that was not emitted.
The project view refreshes during work while preserving its research context.
Its initial read loads the selected scope; recurring polling pauses while the
tab is hidden and resumes when it becomes visible. Leaving a scope cancels its
outstanding browser reads. A failed refresh cancels sibling reads, and an
abandoned request must not replace the new scope's data or create an error.
Expensive artifact, readiness and pending-question reads run outside the main
server event loop so local status and unrelated reading remain responsive.
Pending-question aggregation reads the current decisions directly rather than
constructing every historical artifact. A readiness response reuses each
mode's calculated basis for its gate checks; run creation still verifies the
current inputs independently. No long-lived cache changes scientific freshness.
Same-scope refreshes capture the current reading anchor immediately before
committing results, after any reading during the request. A visible focused
control keeps its screen position without being refocused; otherwise the
nearest stable reading anchor is used. A short, bounded resize observation
also accounts for delayed tables. Reader input cancels this preservation;
scope changes, disconnected content and unmount dispose it. Publication must
not move the active reading control behind the sticky phase toolbar.
Raw event and thread data remain in execution detail.
Waiting for researcher direction closes the activity stream without making the
run terminal. If the run resumes in another view, its open activity page
reconnects automatically, including when polling misses the brief waiting state.
Busy dialogs consistently disable dismissal by Escape, backdrop and Close.

## 4. Non-goals (V1)

- No general chat with every member or direct editing of scientific records.
  A focused assessment discussion is supported within its exact research
  target; it does not grant permission to change that target.
- No collaborative editing or external notification integrations. Research
  progress and failures are visible within the workbench.

### P5 report and appendix reading

P5 presents one continuous report with the existing seven exact-version section
discussion/comment actions. An explicit `section_anchors.references` declaration
places the bibliography after scientific content without adding a discussion
action. The full-document block structure supplies heading paths and citation
targets; partitioning does not reparse scientific substrings. Reproduction
discussion excludes the declared bibliography and all supplementary documents.
Reports without the declaration preserve historical reading semantics.

Report tools expose the full offline HTML edition containing the report and its
declared materials. The main report keeps its bibliography after the scientific
account. Separately linked Markdown supporting documents, including the proof
appendix, open as rendered HTML in their own in-app source dialogs, with exact
document anchors and links. A material-specific HTML edition retains the full
offline bundle and the existing optional print selection; it does not hide other
screen content. Verified assets, exact report provenance and review status remain
in the offline edition. Retained Markdown and LaTeX remain available as sources.
The main report uses a compact reading budget without hard word or equation caps.
HTML reading, mathematics, figures, citations and cross-document links are the
acceptance surface; PDF export and pagination checks apply only if explicitly
requested later. These presentation choices do not create a new scientific
generation or confer independent review on revisions.

### Connection guidance beside run controls

Run preparation displays compact team-level credential configuration from the
existing project API projection. It respects provider-file defaults, member
overrides, environment credentials and retained member accounts. A global OpenAI
connection flag is not a universal prerequisite. Configured credentials are not
presented as a verified connection or a ready numerical runtime.

Team Settings is the common action; OpenAI Account appears when account-backed
credentials are missing. Setup details identify affected members. These actions
are ordinary buttons, never form submissions or model probes. Settings open
above the current reader so run drafts and reading position remain intact;
closing settings refreshes the existing project/readiness query. The guidance
adds no scientific gate, automatic paid test, or new onboarding wizard.

### Reader hardening and concise decision presentation

Restoring a saved numerical-run answer restores its origin and revision with its
text. An unknown response remains unknown; an origin-only draft change survives
reopening and is not mistaken for the saved response.

The complete question appears once in its native disclosure heading when opened.
Its defining context, consequences, alternatives and advice remain visible,
including distinct answer consequences in older records. No word-count threshold
hides these fields. Scientific importance, classifications, source identities and
history remain in Context and sources. Authored mathematics, qualifications and
citations stay intact; the renderer does not rewrite scientific prose.
Numerical Summary sources collect exact field links without repeating them
between paragraphs. The underlying implementation and evidence remain available.

Report and recovery anchors use the current measured sticky-toolbar height.
Changing that offset does not scroll or refocus the reader. Supporting-document
dialogs use their own scroll gap. Search selection in the theory graph focuses
the selected inspector, and closing it returns to the originating control;
polling and restored selections do not move focus.

P5 keeps its report-first layout. Indispensable P5 editorial questions have one
conditional answer location within Revise report, before the run settings.
The Next action and compact summary navigate to that same question. Exact model,
source and answer-version filtering applies; an active run pause owns its answer
instead of creating another editor. Scientific and study-design questions remain
at their upstream owners. Ordinary report discussion stays section-based.

### Truthful question and answer states

An unanswered ordinary item is an Open question. Only an actual active run pause
is described as paused, and it takes precedence in Next and phase navigation.
Scientific severity does not imply that the researcher must answer before work
can continue. Missing legacy metadata does not imply optionality. Counts separate
saved answers, saved unknown responses and unanswered questions without counting
mirrored context twice; these labels do not change run readiness.

Each answer has one editor. A first draft never claims that an answer is already
saved. Editing changes future work after Save answer; work already started keeps
its original inputs. Get the Lead's advice and Discuss retain separate targeted
conversations and never save a preference or study fact automatically. Saving a
pause answer and choosing Continue work remain separate actions. Continuation uses
inputs already accepted by the paused step, including earlier pause responses.

Question headings expose inline mathematics without interactive elements inside
the summary. Citation actions remain in the details with their original source.
Stable question, source, draft and reading-anchor keys survive copy and layout
changes. Same-scope updates preserve focus, caret, open disclosures and reading
offsets; user interaction cancels competing restoration. Unknown review status
is shown as unconfirmed, never as a confirmed absence of review.
