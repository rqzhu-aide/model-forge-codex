"""One project instruction field, including older split-field snapshots."""


def project_instructions(project: dict) -> str:
    instructions = project.get("research_instructions") or ""
    question = project.get("research_question") or ""
    if not question.strip():
        return instructions
    if not instructions.strip():
        return question
    if question.strip() == instructions.strip():
        return instructions
    return question.rstrip() + "\n\n" + instructions.lstrip()


def normalize_project(project: dict) -> dict:
    normalized = {**project, "research_instructions": project_instructions(project)}
    normalized.pop("research_question", None)
    return normalized
