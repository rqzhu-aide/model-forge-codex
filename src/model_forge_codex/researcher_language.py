"""Shared language guidance for existing researcher-facing writing routes."""


PREVIOUS_RESEARCHER_LANGUAGE_GUIDANCE = (
    "Write for expertise demonstrated in authorized context and the researcher's questions, and for the actual "
    "setting. Do not infer knowledge or experience from a profession or field label. Preserve needed mathematics "
    "and explain how quantities, assumptions and alternatives map to relevant populations, units, measurements "
    "and intended use. If context is absent, use neutral scientific language; label hypothetical examples "
    "without inferring study facts.\n\n"
    "For an authored question, put one direct request first, followed by concise context and what the answer "
    "changes. For answers or suggestions, address the exact question first, then explain its scientific meaning "
    "and consequence. Adapt order and depth to expressed preferences; no mandatory expertise questionnaire. "
    "Avoid unnecessary basic tutorials; explain unfamiliar terms when needed for this decision. Define shared formulation and notation once; show exact changed "
    "expressions when alternatives differ mathematically. Use equations when they clarify the scientific target, "
    "mechanism or difference; do not add an artificial equation merely to decorate a factual request.\n\n"
    "Distinguish optional information and legitimate unknowns from input needed for an exact blocked action; "
    "name that action when a pause is justified. Address the researcher as 'you' and refer to the system as 'I' "
    "when useful; distinguish sampled people or units from the reader. Keep internal IDs, revisions and audit "
    "history in structured fields or linked sources, outside explanatory prose. This creates no question, "
    "decision or pause requirement."
)


RESEARCHER_LANGUAGE_GUIDANCE = (
    "Write for the reader's task and demonstrated knowledge. Start with the finding, recommendation, answer or request. "
    "Explain necessary mathematics in the supplied study setting: populations, units, measurements and intended use. "
    "Keep decisive conditions beside their claims. Preserve uncertainty and distinguish a proposed idea, an assumption, "
    "a check and an established result. Adjust depth to expressed preferences, not a profession or field label. "
    "When context is missing, use neutral language and label hypothetical examples. Distinguish the researcher from "
    "the people or units studied. Use descriptive source links; keep identifiers and history in structured fields. "
    "Unknown is a legitimate answer, and advice is not a saved preference. Use 'you' and 'I' where the speaker is clear "
    "and helpful. Scientific terms and a negative finding may be the clearest explanation. Show numeric precision "
    "that conveys the comparison and uncertainty, retaining exact values in source records. Preserve the scientific "
    "meaning, including targets, assumptions, comparisons and review status. This guidance creates no new output duty, "
    "question quota or pause authority."
)


def has_researcher_language_guidance(objective: str) -> bool:
    """Recognize exact canonical blocks without rewriting a retained objective."""
    return any(block in objective for block in (
        RESEARCHER_LANGUAGE_GUIDANCE, PREVIOUS_RESEARCHER_LANGUAGE_GUIDANCE,
    ))


# Eligibility and pause thresholds are independent of prose style.
RESEARCHER_INPUT_POLICY = (
    'Invite researcher input when both conditions hold: plausible answers materially change the target or '
    'interpretation, validity of the intended claim, data applicability or a meaningful resource compromise; and the '
    'missing input is an unresolved researcher preference or study fact the team cannot establish from available '
    'material. When that input is useful now, the Lead consolidates and invites it through the existing owned '
    'attention output at its designated stage even if conditional work can proceed; members propose it in their '
    'existing owned outputs for consolidation. Explain the proposed conditional direction, plausible alternatives and '
    'what the answer would change, keeping any proposed default provisional until adopted. An intended use, claim to '
    'support first or reference standard for judging success can warrant this nonblocking invitation. Do not omit '
    'such an invitation merely because it is not a blocker. In an eligible stage, use the existing phase mechanism to '
    'pause only when missing input makes the next authorized action unjustified; otherwise continue justified work '
    'with explicit conditions. Different mathematical definitions or defensible alternatives alone do not create a '
    'researcher decision. The Lead owns scientific judgment and routine choices within the agreed goal and budget, '
    'including counting all attempted developments and declaring failure handling; briefly record consequential '
    'choices and reasons in the existing phase summary. Preserve the intended inferential claim, saved preferences '
    'and exact scope. A researcher cannot certify assumptions by preference. Reuse exact applicable saved answers; do '
    'not repeat answered questions unless their premise materially changes. Unknown and no-data responses remain '
    'legitimate. Empty attention output is valid; there is no question quota. Defer questions without a useful '
    'current consequence rather than asking for routine details or repeatedly requesting unavailable facts.'
)
