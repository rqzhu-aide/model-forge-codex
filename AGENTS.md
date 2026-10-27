# Guidance for coding agents

This file applies to any agent or assistant editing this repository. Read [CONTRIBUTING.md](CONTRIBUTING.md) first; it covers repository layout, private files, and verification. This file adds the one requirement that is easy to miss: text a researcher reads has its own acceptance check.

## User-facing text

The researcher reads text from two sources: strings written by hand in the interface, and prose written by the research team models from their instructions. Both must help the researcher answer their question, advance their task, or make a justified decision. A change counts as user-facing when it touches any of:

- `web/src/**` string literals: labels, status copy, button text, empty states, tooltips
- `contracts/contracts/phases/*.json` stage objectives and `contracts/schemas/*.json` field descriptions, which the models write from
- `src/model_forge_codex/researcher_language.py`, the shared writing guidance injected into briefs
- any model-authored field shown in the interface: questions, `context_markdown`, `overview_markdown`, conclusions, report sections, action labels

Before editing these, read the user-facing product reference in the `rqzhu-workflow` skill (`references/user-facing-products.md`) if it is installed. Whether or not it is, fill in the block below and include it in the plan or handoff for the change.

### Reader acceptance (fill for every user-facing change)

- Reading purpose of each changed surface, one line each: what the researcher is trying to learn or decide there.
- The first sentence of each changed model-authored field states the finding, request, or recommendation. Paste one example from a fresh run, not from a historical record.
- Every status or state string is true in the state it is shown: no "answer saved" before a save, no "needs your answer" on an invitation the researcher may skip.
- Optional versus waiting-for-input is shown from run state, not inferred from the author's prose.
- Numbers in prose carry the precision the comparison and its uncertainty need; exact values stay in records and tables.
- Identifiers, revisions, and audit names appear in chips, links, or structured fields, not in sentences.
- Scientific meaning is unchanged: no strengthened claim, no preference assigned to the researcher, no missing evidence turned into a negative finding. Check meaning before readability.
- For an instruction change, a paired probe: the same prompt before and after, judged for meaning first and readability second. Link the probe files.

A plan or handoff without this block filled in is incomplete for a user-facing change. The block records what was checked; it does not add an approval stage, a word list, or a pronoun rule.
