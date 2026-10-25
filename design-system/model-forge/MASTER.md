# Model Forge visual design

Updated October 23, 2026. Current visual contract for the
[shared styles](../../web/src/styles.css) and the
[phase readers](../../architecture/design/07-ui-contract.md). The approved
October 19 refinement sets the title separator and the reading rules below;
the October 23 refresh sets the shared tokens, neutral ink and the surface,
control and navigation direction, and its research-instrument pass sets the
typeface, quiet role markers, the resume header and arrival motion. The
Ironforge pass that followed the same day sets the navy forge frame, the heat
accent, the display face, the forge-gate mark and the artwork, and retires
sage; [DESIGN.md](../../DESIGN.md) holds the full system. Source, browser and
installed-release verification remain separately recorded in the
[implementation status](../../architecture/implementation-status.md).

## Direction

Document windows use a pale system title bar with Close always visible. Only the body
scrolls; long content never takes the window controls out of view.

A compact research reader. Bring the current conclusion forward and keep
project context minimal. Scientific qualifications, source identity and reading
position remain intact. Controls use natural widths rather than filling rows.

## October 23 refresh

Role tints used to fill every card body and every control, so five hues
competed equally. The approved direction gives color a single job per place:

- Card bodies are white (`--panel`; charcoal in dark mode) on 1px
  `--card-line` hairlines. Heading bands are neutral; a card's role is a 6px
  dot and a short label after its title. Flat bands inside a card, such as
  team replies and researcher contributions, keep their role surfaces.
- The system accent (sage then, Illini Blue since the Ironforge pass) marks
  only the selected item. Unselected buttons, tabs and selectors are neutral
  stone.
- Moderate density: 8-10px heading band, 14-16px body padding, 16px between
  cards.
- The sidebar is a project list, on navy iron since the Ironforge pass. Phase
  navigation is a numbered stepper whose states are labeled in text.
- An inline SVG brand mark sits beside the wordmark, set in Marcellus since
  the Ironforge pass. Empty states use drawings, and the theory graph gets a
  polish pass. No remote assets.

Rollout status:

1. Tokens and cleanup, applied October 23: spacing, radius and type tokens;
   neutral ink and lines; one UI font and one code font; charcoal dark panel;
   unused paper-era rules removed.
2. Surfaces, applied October 23: white card bodies with the role tint only in
   the heading band; neutral unselected controls with sage on the selected
   one; 8px heading bands, 14-16px body padding and 16px between cards.
3. Navigation, applied October 23: the sidebar is a plain list on the
   canvas, filled only for the selected project; phase navigation is a
   numbered stepper on its own row under the project title.
4. Art, applied October 23: brand mark and favicon, empty-state drawings and
   theory graph polish.
5. Research instrument, applied October 23: IBM Plex Sans and Plex Mono
   bundled from npm; neutral heading bands with quiet role markers; a quiet
   sage tint for the selected control; the resume header and the arrival
   outline.
6. Ironforge, applied October 23: the sidebar and the project header become
   a navy forge frame (Illini Blue `#13294B`) with stepped rules, bevels and
   two iron brackets; Illini Orange `#FF5F05` heat appears in one place per
   region; Marcellus sets the wordmark and major titles; the forge-gate mark,
   crest, favicon, hall plate, workbench vignette and section accent replace
   the curve mark and line drawings; history records and the report title take
   the library treatment. Sage is retired; the reading room stays white.
7. Card edges, applied October 23: top-level cards take an iron fitting at
   each corner and a carved dentil course along the lower edge of the
   heading band. Card bodies, cards inside cards and forced-colors mode stay
   bare.
8. Iron plating, applied October 23: the frame's ashlar bricks become
   riveted iron plates (`--forge-plating`): staggered 96 by 48 plates with
   beveled seams, a rivet in each corner and a faint brushed grain, under a
   broad sheen on the sidebar and the lintel.
9. Tab plates, applied October 23: the stepper's beveled nodes and the
   groove that joined them become five raised iron tab plates, each with a
   round state well, and the current phase becomes the plate in the fire:
   Illini Orange, white-hot at its foot, with dark forge-0 text.
10. Running rim, applied October 23: a running phase's tab glows along its
    edge, run-blue on iron and molten gold on the plate in the fire,
    breathing with its run dot.
11. Project plates, applied October 23: project names in the sidebar hold
    to two lines, and each unselected project becomes a quiet raised iron
    plate with a soft edge shadow; the open project stays the recessed slot.
12. Forging mark, applied October 24: the sidebar's brand becomes the mark
    being forged, a canvas scene of the forge-gate M on an anvil that turns
    once every 5 seconds while a hammer strikes it four times, each blow
    throwing sparks. Reduced motion shows one still frame.

Art rules:

- The brand mark (`BrandMark` in Visuals.jsx) is the forge gate: a bold
  angular M built as a foundry entrance, with two broad pillars, clipped
  corners and a small furnace opening at its foot, on a chamfered stone tile.
  Its colors come from `--mark-tile`, `--mark-iron` and `--mark-heat`. The
  favicon in index.html keeps the same silhouette in two solid colors with
  generous openings, switching the iron to a pale blue under a dark browser
  scheme. The wordmark is Marcellus.
- In the sidebar the mark is drawn by `ForgingMark` (ForgingMark.jsx) on a
  canvas: the M extruded in iron on an anvil, turning once every 5 seconds
  while a hammer strikes its top four times, each blow flashing, heating the
  iron and throwing sparks. Every frame depends only on the time within the
  loop, so it repeats without a seam. It pauses off screen, paints one still
  frame under reduced motion, and falls back to `BrandMark` without a canvas.
  The canvas overhangs its 40 by 44px slot so the hammer and sparks can leave
  it.
- `Crest` is the large emblem on the welcome page: the same gate, faceted in
  vector with bevels, a carved band and reflected warmth. It is vector, not a
  painted raster. `ForgeLibraryArt` is the hall plate, a foundry beside a
  library, shown beside the resume header at 1100px and wider and sized to
  its two rows. `SectionAccent` is an engraved boss with double-rule wings
  above the history record. All artwork is decorative (`aria-hidden`).
- `EmptyState` places the workbench vignette above the message, only where a whole
  phase or card has nothing yet: the welcome page, Phase 2 proposals, the
  method choice, the Phase 3 overview, the Phase 4 summary and the Phase 5
  report. Small empty lists keep a plain note. The drawing is decorative
  (`aria-hidden`); the message carries the meaning.
- The theory graph sits on a faint dot grid (`--graph-grid`) and opens
  centred on the main results. Selecting a node elsewhere scrolls it into
  view (instantly under reduced motion), fills it with the selected surface,
  draws its related edges in system ink on top with stronger strokes, and
  keeps the remaining dependencies legible at full opacity in both themes.

Research instrument rules:

- Type. `--font-ui` is IBM Plex Sans Variable and `--font-mono` is IBM Plex
  Mono 400 and 500, imported from `@fontsource-variable/ibm-plex-sans` and
  `@fontsource/ibm-plex-mono` in main.jsx and served with the app.
  `--font-display` is Marcellus 400 from `@fontsource/marcellus`, for the
  wordmark and major titles only. The project title is Marcellus 26px; card
  headings are Plex Sans 17px, weight 600; weights 650 and 680
  are retired outside the protected revision block. Identifiers, tables and
  counts use tabular figures. Small labels are sentence case, and side rules
  are 1px.
- Role markers. Each card title ends with a 6px dot and a 12px muted label:
  Team (`--role-team`, blue) on summary and research cards, Your input
  (`--role-you`, orange) on action and attention cards, Activity and Record
  (`--role-system`, teal-green) on progress and history cards, and Revision (purple)
  on the phase input summary. The label is generated with empty alternative
  text, so assistive technology reads only the title. A legend at the foot of
  the sidebar repeats the three dots: Team findings, System and records, Your
  input.
- Resume header. From Phase 2 onward, the opening paragraph of the trunk
  research goal sits under the stepper at the prose measure: two lines at
  most, whole sentences, never cut inside inline mathematics, with **Read the
  full setting** opening Phase 1. Below it, the Next line names how many
  researcher decisions wait and where, with one forward action, the one
  heat button in the header. It counts
  only the Phase 1 to Phase 4 decision cards; Phase 5 clarification happens in
  report section discussions. Without waiting decisions it says which phase
  waits for direction, that work stopped, that the team is working, or that
  nothing needs a decision.
- Arrival. The Next action opens the phase and scrolls to its decision card:
  a short hop glides, a longer one jumps. The card takes focus, then a 2px Illini Blue
  outline fades over 600ms (`--ease-out`, an exponential ease-out). Under
  reduced motion the scroll is instant and the outline holds briefly, then
  clears. Control transitions stay at 150ms.

## Purpose palette

Use the same three roles in every phase, current or historical. Team-authored
summaries and scientific detail use blue. System navigation, settings,
selectors and source controls are neutral stone until selected, when they use
the blue selected tint; reading disclosures are neutral rows. Researcher
writing, saved instructions, questions, conversations and research launch
actions use warm peach and terracotta. A control's purpose determines its role,
including when it appears inside another role's panel. Publication citations
and their previews use blue in both themes, including inside system-role panels.
Source-opening controls use system styling with blue reference labels.
Unselected controls are neutral stone; the blue selected tint marks the
selected one.

Card bodies use the neutral `--panel` in every role except the revision
summary below. The band columns color flat bands inside a card, such as team
replies and researcher contributions; no inner block takes a fill otherwise.
Card heading bands are neutral (`--panel-subtle`) except the revision summary.
The heading column survives as `--section-soft` on inner strips such as
request questions and attention notes.

| Purpose | Light heading | Light band | Dark heading | Dark band |
| --- | --- | --- | --- | --- |
| Team-authored conclusion and scientific detail | `#dfe6f1` | `#eef2f8` | `#1d3253` | `#162640` |
| Discussion and research-request shell | `#f6e0d0` | `#fcefe6` | `#4a2e1e` | `#3a2519` |
| System activity shell | `#eef1f5` | `#eef1f5` | `#1b2230` | `#1b2230` |
| History record (library parchment) | `#f8f5ee` | `#f8f5ee` | `#171d26` | `#171d26` |
| Researcher contribution | `#fcefe6` | `#fcefe6` | `#3a2519` | `#3a2519` |
| Revise and rerun summary shell | `#e8e0f5` | `#f3effb` | `#3d3050` | `#2e253f` |

The revision summary is an explicit exception: its background, title band,
outline and separators use muted purple (`--revision-*`). This distinguishes
the phase-wide input overview from its source cards. Its research links retain
orange and system controls retain navy; purple does not encode readiness.
There is one preparation card per phase/method scope. Before its first run,
**Instructions and run settings** uses the orange research-input surface and
opens directly to the form. After a scientific run, the purple **Revise and
rerun** card contains the summary and one nested **Edit instructions and
settings** disclosure. P5 retains **Revise report**. The editor is not a second
card; its input surface and controls keep their existing role colors.

Apply card purposes through `data-card-role`, never phase number or scientific
verdict. Summary and research roles share the blue family, including authored
tables and inline code. Discussion and further-research entry points use orange
before expansion, so researcher attention is visible immediately. Their team
explanations and recommendations remain blue. System activity keeps system
styling and history sits on library parchment, including when nested in a
research-request card. Every card has a solid
white body (charcoal in dark mode) and a neutral heading band; the role shows
as the dot and label beside the title. Orange denotes researcher interaction; urgency and execution status
use separate labeled indicators. This corrects the earlier exception that
misclassified discussion shells as system UI.

Shared role tokens use the `--team-*`, `--system-*` and `--contribution-*`
families. Existing token aliases retain their shared meaning. The prototype
values below define the controls and contribution regions in both themes:

| Token purpose | Light | Dark |
| --- | --- | --- |
| Team text | `#13294B` | `#dbe6f6` |
| Team secondary text | `#44587a` | `#a7b8d0` |
| Citation link | `#1d4f91` | `#9cc3f2` |
| Team inner divider | `#c5d0e1` | `#34496a` |
| Team card outline and title separator | `#8798b5` | `#5f7aa3` |
| System button | `#dfe5ed` | `#253044` |
| System text | `#1b2a40` | `#e1e8f2` |
| System secondary text | `#4a586d` | `#a9b5c6` |
| System control border | `#7d8aa0` | `#6f7f98` |
| System selection | `#13294B` | `#a9c8f0` |
| System selected text | `#ffffff` | `#0b1a31` |
| System focus (reading room; heat on the iron frame) | `#1d4f91` | `#a9c8f0` |
| Selected control `--tab-selected` | `#dfe6f1` | `#1f3556` |
| Selected control text `--on-tab` | `#13294B` | `#dbe6f6` |
| Selected control outline `--tab-selected-line` | `#1d4f91` | `#a9c8f0` |
| Contribution field | `#fffaf6` | `#22180f` |
| Contribution button | `#f6e0d0` | `#4a2e1e` |
| Contribution text | `#6b2d10` | `#ffd9bd` |
| Contribution secondary text | `#7c4729` | `#d5b09a` |
| Contribution control border | `#bf7647` | `#c9825a` |
| Primary research action | `#b5440d` | `#ff9a5c` |
| Primary research-action text | `#fffaf6` | `#2a1609` |
| Team marker `--role-team` | `#2b5592` | `#8fb3e6` |
| System marker `--role-system` | `#2f7a6b` | `#6fc2ae` |
| Researcher marker `--role-you` | `#c2480b` | `#ff9a5c` |

Body text, dividers and surfaces are neutral in every role, so role hues stay
legible where they carry meaning:

| Neutral token | Light | Dark |
| --- | --- | --- |
| Canvas `--paper` | `#eeebe5` | `#0f141b` |
| Card body `--panel` | `#ffffff` | `#161c25` |
| Body text `--ink` | `#18212f` | `#e4e8ee` |
| Secondary text `--ink-soft` | `#4e5767` | `#a3adbb` |
| Muted text `--muted` | `#596272` | `#9aa4b2` |
| Card divider `--line` | `#e4e0d8` | `#263040` |
| Card outline `--card-line` | `#dfdad1` | `#2a3444` |
| Text selection `--selection` | `#ffe0c9` | `#5a3018` |
| Strong divider `--line-strong` | `#cdc7bb` | `#364254` |
| Unselected control `--control-fill` | `#ebe8e2` | `#1e2632` |
| Control hover `--control-hover` | `#e1ddd5` | `#273141` |
| Control text `--control-ink` | `#1f2b3f` | `#d7dde6` |
| Control border `--control-border` | `#c9c2b5` | `#3a4658` |
| Field `--field-bg` | `#ffffff` | `#121821` |
| Field border `--control-line` | `#857e71` | `#6b7686` |

The forge frame, its heat and the artwork use their own tokens. The iron ramp,
steel, frame text and heat keep the same values in both themes, because the
frame is navy in both; the library and art tokens switch:

| Forge token | Light | Dark |
| --- | --- | --- |
| Iron ramp `--forge-0` to `--forge-5` | `#0b1a31` `#0f2140` `#13294B` `#1b355d` `#24426f` `#3a5786` | same |
| Steel edge `--forge-steel` | `#9db4d8` | same |
| Frame text `--forge-text`, `--forge-text-soft` | `#e8edf5`, `#b4c0d3` | same |
| Frame title `--forge-title` | `#f6f1e7` | same |
| Heat `--heat` (Illini Orange) | `#FF5F05` | same |
| Heat ramp `--heat-deep`, `--heat-soft`, `--heat-pale` | `#C2410C`, `#FFB27A`, `#FFE3C8` | same |
| Mark `--mark-tile`, `--mark-iron`, `--mark-heat` | `#e9e3d6`, `#13294B`, `#FF5F05` | same |
| Library `--library-surface` | `#f8f5ee` | `#171d26` |
| Library rule `--library-line`, `--library-rule` | `#e2dacb`, `#bfb39f` | `#2c3646`, `#435066` |
| Art `--art-wall`, `--art-iron`, `--art-plate` | `#d6cfc2`, `#13294B`, `#24426f` | `#2e3a4c`, `#4f6c98`, `#2c4a78` |

The iron frame redeclares `--system-focus` as heat so focus stays visible on
navy; a white panel opened inside the frame restores the reading-room focus
through `--reading-focus`.

### Discussion ownership and attention

Keep one compact disclosure row per item. Rows requesting a researcher response
use orange, including their focus treatment. Ordinary scientific/history reading
rows are neutral grey. Inside an expanded row, use flat
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

Close, Cancel, selectors, source-opening controls and reading navigation retain
system styling inside a warm panel: neutral when unselected, the blue
selected tint when selected. Source-opening controls retain their blue reference labels. Team replies and citation previews retain
blue reading surfaces there. Inline publication citations retain blue text
regardless of an ancestor's system role. Ordinary saved-status badges use neutral tokens;
unknown, waiting and blocking states keep their explicit amber or red labels.

Color always accompanies text. Header, row, team content and editable fields
must remain distinguishable in both themes. Keep reading anchors, native
disclosures, compact short rows and focus restoration unchanged.

## Layout and reading

- Vertically ordered, full-width reading sections; no four-column dashboard grid.
- The project heading, the phase stepper and the resume header above the
  cards. The name and compact activity indicator share the first row; the
  stepper fills the second. Both sit on the navy lintel, which hangs from the
  top of the workspace with a beveled foot, a heat glow line along its lower
  edge and an iron bracket at each lower corner. The resume header (research question and Next line) follows
  at the prose measure. Full work details use a native disclosure.
- The phase stepper keeps the five phase labels and their order. Each phase
  is a raised iron tab plate, with no rule between them, and a round well
  recessed at the plate's left shows its state: a check when results are
  available, a drawn exclamation mark in an amber rim when the phase needs
  input or holds waiting questions, a pulsing dot while work runs (static
  under reduced motion), and the phase number otherwise, with an amber rim
  when results are interrupted or outdated. The current phase is the plate
  in the fire: Illini Orange, white-hot at its foot with heat rising off it,
  its name in dark forge-0 for contrast. It holds still. A running phase's
  plate glows along its edge and breathes with its dot: a run-blue rim on
  iron, a molten gold rim on the plate in the fire, held at full glow under
  reduced motion. A text cue sits under the label, so state never depends on
  color: the number of waiting questions (`2 questions`), the same count the
  Next line uses, or Needs input, Running, Queued, Failed, Stopped,
  Interrupted or Outdated. A running or stopped state outranks the count.
  From 601px to 1100px, the state well sits above the full-width name so words
  remain intact beside the sidebar. Below 600px, each plate keeps its well and
  concise status; only the current phase's full name is shown beneath the plates.
  At 440px and below, plates wrap into three then two columns so exact status
  words such as Interrupted remain readable at 12px.
- The sidebar is a project list on riveted, brushed navy iron with a
  stepped right edge: pale text, a faint lift on hover, and a recessed slot
  with a heat chevron only for the selected project or workspace view.
  Unselected projects stand off the iron as quiet raised plates with a soft
  edge shadow, and a project's name holds to two lines with the full name on
  hover. New project is an outlined button. The authored conclusion
  begins the reading area; actionable decisions remain visible.
- Spacing comes from `--space-1` to `--space-6` (4, 8, 12, 16, 24 and 32px).
  Radii are `--radius-control` 6px, `--radius-inner` 6px, `--radius-card`
  8px and `--radius-pill`, beveled (`corner-shape: bevel`) where the
  browser supports it and rounded elsewhere. Cards are 16px apart with 14-16px body padding.
- One 17px, weight 600 heading per card (`--text-card-heading`) in an 8-10px
  neutral heading band, followed by its role marker.
  Direct headings and headings inside a shared title strip use the same rule.
  Place the title, tabs and related actions together where they fit. Avoid
  stacked category labels and duplicate titles. Keep method context and
  explanatory notes in the body; allow long headings to wrap on small screens.
- Phase 1 Main Findings keeps the cited cross-paper synthesis visible. Relevant
  approaches begin as compact native disclosure rows with their authored title,
  fit and any support qualification. Opening a row reveals the unchanged
  mathematical account and relevance; extended derivations and evidence retain
  their own disclosure. Preserve the reader's open rows, citation destination
  and focus across refreshes. Do not replace complete mathematics with a word
  cap, teaser generated by another agent, or an ellipsis.
- The project title is Marcellus 26px (`--font-display`; 21px below 600px). A selected method's
  document title uses the card heading size; subsection headings are 16px,
  weight 600 (`--text-subsection`). Markdown headings inside a research
  document step down from there: h4 and h5 at 16px, weight 600, and h6 at the
  same size in muted ink, never browser defaults. Scientific prose and researcher writing,
  including saved contributions and editable fields, use 16px with comfortable
  line height; scientific prose retains 1.65 line height (`--text-prose`).
  Controls and metadata remain compact at 13px (`--text-meta`); meaningful
  status is at least 12px.
- Every card uses the same hairline outline and a separator below the title
  strip; the role marker, not the outline, names the role. Inner scientific
  sections keep lighter dividers and flat bands; clearer boundaries do not add
  nested cards, shadows or more whitespace.
- Top-level cards are bound in iron at their edges: a 24px navy fitting with
  a steel rim and one rivet at each corner (`--card-fit-tl`, `-tr`, `-bl`,
  `-br`, drawn by the card's `::after` and cut by its bevel), and a dentil
  course of 4 by 3 blocks every 8px along the lower edge of the heading band
  (`--card-carve`). Fittings shrink to half the height of very short cards.
  The body stays plain; nested cards and forced-colors mode go without.
- Constrain dense narrative to a readable measure (`--measure-prose`, 36em,
  about 72 characters of Plex Sans);
  plots, equations, tables and code can use the full available card width.
  A display equation wider than its column scrolls inside its own block with
  a thin scrollbar and fades at the hidden edge (a scroll-driven mask where
  supported), so a cut equation never reads as complete.
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
use the neutral control style. Existing handlers, disabled states and accessible names remain.

Use three bundled faces through three tokens: `--font-ui` (IBM Plex Sans
Variable) for headings, prose and controls, `--font-mono` (IBM Plex Mono)
for code, identifiers and logs, and `--font-display` (Marcellus 400) for the
wordmark, project and page titles, the welcome title, history records and the
report title only. All three ship with the app from npm. Mathematical
notation retains KaTeX. No remote fonts,
images, framework or animation dependency is required.

System selection and focus use Illini Blue in the reading room and heat on
the iron frame; contribution controls use their warm focus tokens. Execution status uses compact pills and
scientific outcomes use a separate Finding badge. Missing outcomes say Not
assessed. A purpose color does not mean that a response is required. Explicit
issue wording distinguishes current requests, team research and saved history.
Disabled controls retain readable labels through dedicated foreground, border
and fill tokens. `--font-mono` falls back through Cascadia Mono and Consolas.
Field boundaries use the control-line token with at least 3:1 contrast against
the field and its surrounding panel. Card dividers retain their softer token.
Dialogs include native disclosures in keyboard traversal and return focus to
a visible invoker, the remaining parent dialog, or the active reader panel.

Theory assumptions have neutral solid rounded outlines; claims show their
proof status in text. Dashed outlines mean cited proofs. Missing support uses
attention styling, distinct from contradiction. Selection adds an outer focus
outline without replacing the scientific status. Keep the drawn legend and
keyboard inspection available.

The workspace canvas stays neutral. Role hues belong to role markers, flat
role bands, researcher fields and the selected control; heading bands, body
text and card dividers use the neutral tokens. Unselected buttons and tabs are
neutral stone, and the selected tab uses the quiet blue `--tab-selected` tint
with navy text and outline. Dark mode uses a slate panel on a near-black
canvas; navy belongs to the frame.
Empty decision sections are omitted; further work begins collapsed.

On small screens, Projects & settings expands the navigation when needed.
Phase buttons wrap rather than requiring sideways page scrolling. Evidence
tables may scroll within their own frame. Keep focus visible after collapsing
the menu. Decorative backgrounds remain static; respect reduced motion for
control transitions, existing progress indicators and the forging brand mark,
which holds one still frame.

## Validation record

See the [current verification summary](../../architecture/implementation-status.md)
for the checks and their limits. Dated visual audits and screenshots are retained
in the ignored local archive. They describe their own tested revisions.
