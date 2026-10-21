# Model Forge visual design

Updated October 19, 2026. Current visual contract for the
[shared styles](../../web/src/styles.css) and the
[phase readers](../../architecture/design/07-ui-contract.md). The approved
October 19 refinement sets the shared type scale, stronger primary card
outline and title separator, and the reading rules below. Source, browser and
installed-release verification remain separately recorded in the
[implementation status](../../architecture/implementation-status.md).

## Direction

Document windows use a sage title bar with Close always visible. Only the body
scrolls; long content never takes the window controls out of view.

A compact research reader. Bring the current conclusion forward and keep
project context minimal. Scientific qualifications, source identity and reading
position remain intact. Controls use natural widths rather than filling rows.

## Purpose palette

Use the same three roles in every phase, current or historical. Team-authored
summaries and scientific detail use blue. System navigation, settings,
selectors, reading disclosures and source controls use muted sage. Researcher
writing, saved instructions, questions, conversations and research launch
actions use warm peach and terracotta. A control's purpose determines its role,
including when it appears inside another role's panel. Publication citations
and their previews use blue in both themes, including inside system-role panels.
Source-opening controls keep sage fills and blue reference labels. Unselected
controls keep their filled backgrounds.

| Purpose | Light heading | Light body | Dark heading | Dark body |
| --- | --- | --- | --- | --- |
| Team-authored conclusion and scientific detail | `#dfeaf6` | `#eef5fc` | `#223f5c` | `#1a3048` |
| Discussion and research-request shell | `#f9e5d5` | `#fff0e3` | `#493227` | `#3b2b23` |
| System activity and history shell | `#edf4e9` | `#edf4e9` | `#263324` | `#263324` |
| Researcher contribution | `#fff0e3` | `#fff0e3` | `#3b2b23` | `#3b2b23` |

Apply card purposes through `data-card-role`, never phase number or scientific
verdict. Summary and research roles share the blue family, including authored
tables and inline code. Discussion and further-research entry points use orange
before expansion, so researcher attention is visible immediately. Their team
explanations and recommendations remain blue. System activity and history remain
sage, including when nested in a research-request card. Every card has a solid
background. Orange denotes researcher interaction; urgency and execution status
use separate labeled indicators. This corrects the earlier exception that
misclassified discussion shells as system UI.

Shared role tokens use the `--team-*`, `--system-*` and `--contribution-*`
families. Existing token aliases retain their shared meaning. The prototype
values below define the controls and contribution regions in both themes:

| Token purpose | Light | Dark |
| --- | --- | --- |
| Team text | `#22354b` | `#e0edfc` |
| Team secondary text | `#4d637b` | `#a9bfd6` |
| Citation link | `#245b82` | `#a5d4f3` |
| Team inner divider | `#c7d6e6` | `#3d5873` |
| Team card outline and title separator | `#8da6c0` | `#6081a1` |
| System button | `#dce9d4` | `#34462e` |
| System text | `#30482f` | `#e3efdc` |
| System secondary text | `#4c6348` | `#b6c9aa` |
| System control border | `#75876b` | `#8ba37b` |
| System selection | `#46623c` | `#b7cea7` |
| System selected text | `#ffffff` | `#1e2c19` |
| System focus | `#405a37` | `#c2d8b2` |
| Contribution field | `#fffaf5` | `#261f1b` |
| Contribution button | `#f9e5d5` | `#493227` |
| Contribution text | `#713a24` | `#ffdab7` |
| Contribution secondary text | `#80503a` | `#d1b49d` |
| Contribution control border | `#ad6b44` | `#c18b64` |
| Primary research action | `#99451f` | `#f0aa76` |
| Primary research-action text | `#fffaf5` | `#2d2018` |

### Discussion ownership and attention

Keep one compact disclosure row per item. Rows requesting a researcher response
use orange, including their focus treatment. Ordinary scientific/history reading
rows remain sage. Inside an expanded row, use flat
color bands rather than more nested cards:

- Team questions, explanations and replies use the blue research
  surface, with a visible author label. Paused questions, their reasons and
  proposed-understanding context use this same flat blue band before the
  warm researcher response area.
- Your instruction, saved contribution, messages and conversation editor use
  the peach contribution surface. Fields use warm cream, labels and borders
  use contribution tokens, and the primary research action uses terracotta.
  In P2, this includes the researcher's original supplied method and source;
  the team's reformulation remains blue.
- The orange row identifies requested researcher input before expansion. Amber
  identifies an unanswered or unknown researcher decision through an
  explicit status label and marker. Team investigation alone does not request
  user input. Explicit blocking/reassessment status keeps its red marker.
- Saved instructions have a neutral status label. Their peach surface denotes
  researcher ownership, not scientific correctness or resolution.

Close, Cancel, selectors, source-opening controls and reading navigation retain sage
system styling inside a warm panel. Source-opening controls retain their sage
fills and blue reference labels. Team replies and citation previews retain
blue reading surfaces there. Inline publication citations retain blue text
regardless of an ancestor's system role. Ordinary saved-status badges use neutral tokens;
unknown, waiting and blocking states keep their explicit amber or red labels.

Color always accompanies text. Header, row, team content and editable fields
must remain distinguishable in both themes. Keep reading anchors, native
disclosures, compact short rows and focus restoration unchanged.

## Layout and reading

- Vertically ordered, full-width reading sections; no four-column dashboard grid.
- A project-name-only heading and compact phase navigation above the cards.
  The name, phase navigation and compact activity indicator share a row when
  they fit. Full work details use a native disclosure. The authored conclusion
  begins the reading area; actionable decisions remain visible.
- 12px card corners, 10px spacing between cards, 8-10px inner padding.
- One intuitive 18px, weight 650 heading per card, with 4px vertical header padding.
  Direct headings and headings inside a shared title strip use the same rule.
  Place the title, tabs and related actions together where they fit. Avoid
  stacked category labels and duplicate titles. Keep method context and
  explanatory notes in the body; allow long headings to wrap on small screens.
- Preserve the 22px project title. A selected method's document title is 19px;
  ordinary subsection headings are 16px, weight 650. Scientific prose and
  researcher writing, including saved contributions and editable fields, use
  16px with comfortable line height; scientific prose retains 1.65 line height.
  Controls and metadata remain compact at 13px; meaningful status is at least 12px.
- Primary blue cards use a stronger outer outline and separator below the
  title strip. Inner scientific sections keep lighter dividers and flat bands;
  clearer boundaries do not add nested cards, shadows or more whitespace.
- Constrain dense narrative to a readable measure. P4 prose uses 72-76ch;
  plots, equations, tables and code can use the full available card width.
- Decision questions can occupy up to two lines on desktop, with urgency
  markers and status labels in stable positions. Narrow layouts wrap the full
  question. Short questions remain compact.
- Shared segmented evidence tabs in every phase, with visible selection and
  keyboard focus. Method selectors stay beside their scientific reader.
- P4 has three vertically ordered scientific cards: Summary, Implementation
  and Code, and Experiments and Results, followed by Decisions to Discuss and
  Additional Runs and History. Summary gives the mathematical method/work recap;
  Implementation and Code stays compact with full accounts disclosed. Every
  numerical table and figure belongs in topic-based Experiments and Results.
  This supersedes the older side-by-side implementation and theory accounts.
  Older records retain their exact definitions, evidence and explicit unknowns.
- Show one current evaluation plan. Other recorded plans and full setup details
  use disclosures; skipped work and consequential limitations remain visible.
  Review reasoning starts expanded when its qualifications cannot be separated.
- Source links remain secondary. Response fields and work instructions use
  readable text, clear labels and explicit Save or Start actions.
- Returning to a project restores its reading section, valid item and reading
  position. P1 and P2 are shared; P3 through P5 remember each method separately.
  Exact saved assessments and historical sources retain their own identity.

## Navigation and method actions

Use these exact phase labels: **Phase 1 - Define and Explore**,
**Phase 2 - Propose Methods**, **Phase 3 - Theory**, **Phase 4 - Numerical Eval**, and
**Phase 5 - Report**.

P2 begins with **Proposed Methods**, then **Select a Method to Explore**. Its
native selector says **Choose a method**. The summary renders internal proposal
and audit hash links as plain prose, with no raw-record source controls or
shared-setting P1 shortcut. Publication citations remain active; reviews and
exact sources remain available in details and history.

**Run this Method in Phase 3 - Theory** and
**Run this Method in Phase 4 - Numerical Eval** open `LaunchRun` preparation for the exact selected method
branch and version while P2 remains active. Work starts only after explicit
submission. Browsing actions use **Go to** followed by the exact phase label,
such as **Go to Phase 3 - Theory**.

## Shared controls and themes

Use the existing outline action icons. Give the same action the same visual
treatment throughout the application. Desktop controls have 28px minimum
height and 18px icons; secondary source controls use 16px icons with the same
hit area. Coarse-pointer targets retain 44px minimum height. Avoid moving cards or controls on hover.

The existing `ActionButton` emits `data-ui-role="system"` by default.
Research contribution actions opt into `data-ui-role="research"` explicitly:
writing or editing instructions, asking or discussing a research question,
requesting a suggestion or assessment, saving researcher direction, and
preparing or starting research. A generic primary class or a warm ancestor
does not assign the research role. Settings saves and other system actions
remain sage. Existing handlers, disabled states and accessible names remain.

Use local system fonts. A compact sans-serif project heading complements the
reading interface; mathematical notation retains KaTeX. No remote fonts,
images, framework or animation dependency is required.

System selection and focus use sage; contribution controls use their warm
focus tokens. Execution status uses compact pills and
scientific outcomes use a separate Finding badge. Missing outcomes say Not
assessed. A purpose color does not mean that a response is required. Explicit
issue wording distinguishes current requests, team research and saved history.
Disabled controls retain readable labels through dedicated foreground, border
and fill tokens. Code font fallbacks include Cascadia Mono and Consolas.
Field boundaries use the control-line token with at least 3:1 contrast against
the field and its surrounding panel. Card dividers retain their softer token.
Dialogs include native disclosures in keyboard traversal and return focus to
a visible invoker, the remaining parent dialog, or the active reader panel.

Theory assumptions have neutral solid rounded outlines; claims show their
proof status in text. Dashed outlines mean cited proofs. Missing support uses
attention styling, distinct from contradiction. Selection adds an outer focus
outline without replacing the scientific status. Keep the drawn legend and
keyboard inspection available.

The workspace canvas stays neutral, with solid role tints in both themes.
Unselected buttons and tabs retain filled backgrounds; system tabs use sage.
Selected tabs use the system
selection token with contrasting text.
Empty decision sections are omitted; further work begins collapsed.

On small screens, Projects & settings expands the navigation when needed.
Phase buttons wrap rather than requiring sideways page scrolling. Evidence
tables may scroll within their own frame. Keep focus visible after collapsing
the menu. Decorative backgrounds remain static; respect reduced motion for
control transitions and existing progress indicators.

## Validation record

See the [current verification summary](../../architecture/implementation-status.md)
for the checks and their limits. Dated visual audits and screenshots are retained
in the ignored local archive. They describe their own tested revisions.
