# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

A solo machine learning researcher or statistician working on their own machine. They start a project with a problem and data, then leave an AI research team (Research Lead, Theorist, Data Analyst, Outside Reviewer) to work for hours or days. They come back to read what was produced, compare alternatives, answer the team's questions and make the next consequential decision. Their own writing is short: instructions, answers and corrections. Most of their time is spent reading.

## Product Purpose

Model Forge is a local research workbench for interactive model and algorithm development. It carries one research question through five phases: Phase 1 - Define and Explore, Phase 2 - Propose Methods, Phase 3 - Theory, Phase 4 - Numerical Eval and Phase 5 - Report. Success is a researcher who can resume a project, understand where it stands and what is still uncertain, and make the next meaningful decision without reconstructing the history themselves.

## Positioning

The researcher stays the decision-maker. The team publishes findings, assumptions, limitations and open questions as reviewable artifacts, and asks for the researcher's direction through decision cards instead of deciding silently. Every published result keeps its exact scientific history: earlier generations, the sources behind a statement, corrections and the runs that produced them remain inspectable.

## Operating Context

- Runs locally: a FastAPI backend with the researcher's data root and a React web client, opened in a desktop browser. Phones and tablets are secondary.
- A project holds a trunk (shared problem setting, literature and method proposals) and one branch per chosen method for theory, numerical evaluation and the report.
- Long sessions of reading explanations, equations, theorem graphs, experiment results and technical reports, in light and dark themes.
- Work runs in the background; the client polls and shows activity, interruptions and requests for input as they happen.

## Capabilities and Constraints

- Phase labels are exact and must not change: "Phase 1 - Define and Explore", "Phase 2 - Propose Methods", "Phase 3 - Theory", "Phase 4 - Numerical Eval", "Phase 5 - Report".
- Scientific history is preserved exactly. The interface never rewrites, merges or hides published content; superseded material stays reachable.
- Reading position, reader choices and project context survive navigation between phases, methods and runs.
- Mathematics is rendered with KaTeX from authored LaTeX.
- No remote assets at runtime: scripts, styles, fonts and images ship with the client.
- Three roles carry fixed meaning across the interface: team findings, system controls, researcher input.

## Brand Commitments

- Name: Model Forge, subtitled "Research workbench".
- The brand mark: the forge gate, a bold angular M built as the entrance to a dwarven foundry, with Illini Blue iron and an Illini Orange furnace core. The same silhouette carries the favicon, the mark, the wordmark lockup and the welcome crest.
- The README's role legend is public: blue marks team findings, navy marks system controls, and ember orange marks researcher input. Teal-green dots identify Activity and Record cards; purple identifies revision summaries.

## Evidence on Hand

- Synthetic fixtures exercise research workflows, mathematical reading, source navigation and technical reports.
- README.md, architecture/design/07-ui-contract.md and design-system/model-forge/MASTER.md describe the workflows and current visual rules.
- No customers, testimonials, benchmarks or usage metrics exist; none may be invented.

## Product Principles

1. The researcher decides. Surface what needs their direction before anything else, and never act on their behalf.
2. Show what is known, what is assumed and what is unresolved as different things.
3. History is evidence. Keep every earlier decision and generation reachable and exact.
4. Reading comes first. The scientific content is the product; controls and status support it.
5. Resume without reconstruction. A returning researcher should see where things stand in one look.

## Accessibility & Inclusion

- Color is never the only signal: every role, state and severity also has text.
- Full keyboard operation with visible focus; 44px targets on coarse pointers.
- Respect reduced motion; both light and dark themes meet WCAG AA contrast for text.
