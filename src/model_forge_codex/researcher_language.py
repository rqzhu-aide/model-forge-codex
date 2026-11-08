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
    "Follow the supplied frozen user-inquiry reference within this stage's existing output and pause authority. "
    'Invite input on consequential modeling choices even when alternatives fit the original goal, no study fact '
    'is missing and the team recommends one. Check original instructions, applicable saved answers, literature and '
    'affordable analysis within this phase first. Ask when at least two defensible directions remain with a material '
    'difference in formulation, assumptions, model or information set, scientific use, guarantee, or practical '
    'accuracy, interpretability or computational feasibility, not already settled by the agreed goal, requirements '
    'and budget. A different estimator or solver alone is insufficient; '
    'explain the scientific commitment or material tradeoff. An uncertain investigation can be an option if its '
    'uncertainty and development cost are explicit. Request unavailable study facts separately without guessed options. '
    'Members propose in existing owned outputs; the designated Lead consolidates, retaining distinct theoretical '
    'and computational consequences. Explain each mathematical alternative and its scientific meaning in the supplied '
    'setting, what stays fixed, and its decisive benefit and limitation. Check assumptions, units, quantifiers and '
    'claimed implications before ranking. Tractability can justify a recommendation when its scientific cost is clear. '
    'Routine choices that preserve agreed requirements belong to the team; briefly record consequential team choices '
    'and reasons in existing scientific summary fields, not another artifact. Zero new questions is valid. Useful nonblocking invitations remain eligible. '
    'An unanswered or unknown response is not consent: continue only justified authorized work under a stated '
    'provisional team direction, never an invented researcher choice. Pause only through an existing authorized '
    'mechanism when the next action is unjustified without input. Defer dependent questions until useful; do not '
    'bundle independent choices. Reuse exact applicable saved answers and clarify material conflicts or custom '
    'formulations without silently mapping them to an option. Adopting an assumption does not verify it or its proof. '
    'An answer neither changes a published method nor launches a run; substantive changes use the existing revision '
    'route. Preserve phase ownership and P5 editorial-only direct inquiries. Unknown and no-data responses are '
    'legitimate, and unavailable facts need not be requested repeatedly.'
)


def has_researcher_input_policy(objective: str) -> bool:
    """Recognize adopted policy blocks without rewriting frozen instructions."""
    return any(block in objective for block in (
        RESEARCHER_INPUT_POLICY,
        "Consequential researcher input policy:",
        "Invite researcher input when both conditions hold: plausible answers materially change the target or interpretation,",
    ))
