"""Deterministic scientific views for independent Phase 2 specialists."""
from copy import deepcopy
import json
import re


def resolve_method_starting_point(project_dir, supplied_method):
    """Verify a selected seed's exact committed sources before starting work.

    Free-text source references retain their historical supplied-method meaning.
    Tagged references identify a starting point, never a focused revision target.
    """
    if not supplied_method:
        return None
    try:
        source = json.loads(supplied_method.get("source_reference", ""))
    except (TypeError, ValueError):
        return None
    if not isinstance(source, dict) or source.get("kind") != "p2_method_starting_point":
        return None
    from .methods import _method_documents
    from .records import committed_packages, generation_path, read_generation

    identity = source.get("method_identity")
    if (not isinstance(identity, dict)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", str(identity.get("stable_id", "")))
            or type(identity.get("version")) is not int or identity["version"] < 1
            or not re.fullmatch(r"[a-fA-F0-9]{64}", str(identity.get("definition_sha256", "")))):
        raise ValueError("The selected method starting point requires its exact published identity")
    store = project_dir / "branches" / "trunk" / "phases" / "p2"

    def exact_source(reference, allowed_families):
        if (not isinstance(reference, dict) or reference.get("branch") != "trunk"
                or reference.get("phase") != "P2" or reference.get("family") not in allowed_families
                or not reference.get("generation_id") or not reference.get("sha256")):
            raise ValueError("The selected method starting point requires an exact P2 source reference")
        family = reference["family"]
        pointer = next((package["records"][family] for package in committed_packages(store)
                        if family in package["records"]
                        and package["records"][family].get("generation_id") == reference["generation_id"]
                        and (package["records"][family].get("content_sha256")
                             or package["records"][family].get("sha256")) == reference["sha256"]
                        and (not reference.get("run_id") or package["records"][family].get("run_id") == reference["run_id"])
                        and (not reference.get("package_id") or package["records"][family].get("package_id") == reference["package_id"])), None)
        if pointer is None:
            raise ValueError("The selected method source does not match a committed P2 publication")
        document = read_generation(store, family, pointer)
        return {"reference": deepcopy(reference), "document": document,
                "bytes": generation_path(store, family, pointer).read_bytes()}

    catalog = exact_source(source.get("catalog_ref"), {"method_catalog", "method_changes", "catalog"})
    methods = [method for method in _method_documents(catalog["document"])
               if (method.get("identity") or method.get("method_identity")) == identity]
    if len(methods) != 1:
        raise ValueError("The selected method identity is absent or ambiguous in its exact catalog source")
    sources = {"catalog": catalog}
    origin = (catalog["document"].get("method_sources", {}).get(identity["stable_id"])
              if isinstance(catalog["document"], dict) else None)
    proposal_families = {"lead_proposal", "theory_proposal", "empirical_proposal"}
    if isinstance(origin, dict) and origin.get("family") in proposal_families and origin.get("run_id"):
        proposal_ref = source.get("proposal_ref") or {}
        if (not isinstance(proposal_ref, dict) or proposal_ref.get("run_id") != origin["run_id"]
                or proposal_ref.get("family") != origin["family"]
                or source.get("proposal_id") != origin.get("proposal_id")
                or origin.get("identity") != identity):
            raise ValueError("The original proposal reference does not match the selected catalog's recorded origin")
    if source.get("proposal_ref") is not None:
        proposal = exact_source(source["proposal_ref"], proposal_families)
        document = proposal["document"]
        if (not isinstance(document, dict) or not source.get("proposal_id")
                or document.get("proposal_id") != source["proposal_id"]
                or document.get("method") != methods[0]):
            raise ValueError("The original proposal does not match the selected catalog definition")
        sources["proposal"] = proposal
    return {"method_identity": deepcopy(identity), "sources": sources}


def freeze_method_starting_point(run_dir, resolved):
    """Retain exact source bytes as lead-directed launch inputs."""
    if resolved is None:
        return None
    from .storage import sha256_bytes

    frozen = {"method_identity": deepcopy(resolved["method_identity"]), "sources": {}}
    for kind, source in resolved["sources"].items():
        path = run_dir / "inputs" / "p2-starting-point" / (kind + ".json")
        path.parent.mkdir(parents=True, exist_ok=True)
        data = source["bytes"]
        if sha256_bytes(data) != source["reference"]["sha256"]:
            raise ValueError("The selected method source changed while preparing its starting point")
        path.write_bytes(data)
        frozen["sources"][kind] = {"reference": source["reference"], "snapshot_path": str(path),
                                    "sha256": source["reference"]["sha256"]}
    return frozen


def method_starting_point_brief(frozen):
    if not frozen:
        return ""
    identity = frozen["method_identity"]
    lines = [f"- {kind.title()} source: `{source['snapshot_path']}` (sha256 {source['sha256']})"
             for kind, source in frozen["sources"].items()]
    return (f"## Frozen method starting point\n\n"
            f"The selected source is {identity['stable_id']}, version {identity['version']}, "
            f"definition digest {identity['definition_sha256']}. Open these exact retained sources:\n\n"
            + "\n".join(lines)
            + "\n\nThe editable supplied specification and additional instructions guide your proposal. "
            "The retained source establishes its attribution and original definition. This is a proposal and "
            "comparison run, with independent specialist candidates; the seed does not authorize a focused "
            "revision of its existing identity.\n\n")


def requires_method_sections(catalog) -> bool:
    """Only newly adopted catalogs require the role-authored method sections."""
    if catalog is None:
        return False
    try:
        return tuple(int(part) for part in catalog.version.split(".")[:3]) >= (1, 11, 0)
    except (AttributeError, TypeError, ValueError):
        return False


def requires_reader_summaries(catalog) -> bool:
    """Only adopted catalogs require the authored P2 overview and review titles."""
    if catalog is None:
        return False
    try:
        return tuple(int(part) for part in catalog.version.split(".")[:3]) >= (1, 9, 0)
    except (AttributeError, TypeError, ValueError):
        return False


def _decision_support_p2(catalog) -> bool:
    """Only adopted catalogs enforce authored profiles and modification options."""
    if catalog is None:
        return False
    try:
        return tuple(int(part) for part in catalog.version.split(".")[:3]) >= (1, 10, 0)
    except (AttributeError, TypeError, ValueError):
        return False


def requires_three_proposals(catalog) -> bool:
    """Use the pinned output obligation, preserving historical P2 behavior."""
    if catalog is None:
        return False
    lead = catalog.output_definitions("P2").get("p2.lead_proposal", {})
    return lead.get("requirement") == "always" and lead.get("required") is True


def specialist_view(phase: str, family: str, document, *, role: str | None = None):
    """Omit lead-addressed input, preserving the author's scientific fields.

    None means that the original record can be delivered unchanged. These
    views govern communication, not filesystem access or historical memory.
    """
    if not isinstance(document, dict):
        return None
    if family == "researcher_answers":
        items = document.get("items", [])
        def shared_answer(item):
            if not isinstance(item, dict) or not isinstance(item.get("attention"), dict):
                return True
            attention = item["attention"]
            audience = item.get("audience") or attention.get("audience")
            if role is not None and audience:
                return role in audience
            generation = attention.get("generation_ref")
            return not (attention.get("kind") in ("researcher_decision", "scientific_issue")
                        and (attention.get("target_phase") == "P2"
                             or attention.get("phase") == "P2"
                             or (isinstance(generation, dict) and generation.get("phase") == "P2")))
        shared = [item for item in items if shared_answer(item)]
        if len(shared) != len(items):
            return {**deepcopy(document), "items": deepcopy(shared)}
        return None
    if phase == "P1" and family in ("research_basis", "literature_synthesis", "synthesis_candidate") and "phase2_preparation" in document:
        view = deepcopy(document)
        view.pop("phase2_preparation")
        return view
    if phase == "P2" and family == "lead_proposal":
        if document.get("no_method_proposed") is True:
            return {"schema_version": document.get("schema_version", "1.0.0"), "no_method_proposed": True}
        view = deepcopy(document)
        view.pop("researcher_origin", None)
        return view
    return None


def specialist_method_provenance(entry):
    """Keep historical scientific proposals without their raw lead-only seed."""
    view = deepcopy(entry)
    for material in view.get("materials", {}).values():
        for item in material if isinstance(material, list) else [material]:
            family = (item.get("ref") or {}).get("family", "")
            document = specialist_view("P2", family, item.get("document"))
            if document is not None:
                item["document"] = document
                item["delivery_view"] = "p2_specialist_scientific_fields"
    return view
