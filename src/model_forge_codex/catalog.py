"""Universal catalog pin + validation (design/06).

The catalog copy under a project's contracts/ dir is synced from
model-forge-contracts (ADR-007) and pinned by catalog-pin.json. Validation
always uses the run's pinned version.
"""

from __future__ import annotations

import json
import hashlib
from copy import deepcopy
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from .domain import Finding

_FMT = FormatChecker()

# Compatibility for metadata introduced before the output registry was
# complete. Declared phase-specific schemas always take precedence.
OUTPUT_SCHEMA_BINDINGS = {
    "protocol": "empirical-protocol.schema.json",
    "evidence": "evidence.schema.json",
    "handoff": "handoff.schema.json",
    "theory_audit": "review-report.schema.json",
    "phase2_handoff": "handoff.schema.json",
    "decision": "decision-record.schema.json",
    "synthesis_compact": "compact-view.schema.json",
    # Collection outputs bind to array-of wrappers (contracts v1.1.0+).
    "attention_items": "attention-item-collection.schema.json",
    # SPEC artifact types (contracts v1.2.0+).
    "lead_paper_cards": "t1-card-collection.schema.json",
    "theory_paper_cards": "t1-card-collection.schema.json",
    "empirical_paper_cards": "t1-card-collection.schema.json",
    "theory_method_cards": "t1-card-collection.schema.json",
    "empirical_method_cards": "t1-card-collection.schema.json",
    "phase_summary": "t2s-summary.schema.json",
    "revision_account": "t2s-summary.schema.json",
    # Diagnostics (contracts v1.3.0, design/15).
    "metrics_long": "metrics-long-row.schema.json",  # JSONL: validated line-wise
    "diagnostics": "p4-diagnostics.schema.json",
    "exhibits": "exhibit-collection.schema.json",
    "claim_map": "claim-map.schema.json",
    "falsification_log": "falsification-log.schema.json",
}

NOTATION_LEAD_OUTPUTS = {
    "p1.research_basis", "p2.catalog_assessment", "p3.complete_theory",
    "p4.empirical_synthesis_candidate", "p5.technical_report_candidate",
}


class CatalogError(ValueError):
    pass


class Catalog:
    def __init__(self, root: Path) -> None:
        self.root = root
        try:
            pin = json.loads((root / "catalog-pin.json").read_text(encoding="utf-8"))
            self.version: str = pin["catalog_version"]
            self.manifest_sha256: str = pin["catalog_manifest_sha256"]
            if not isinstance(self.version, str) or not isinstance(self.manifest_sha256, str):
                raise ValueError("The catalog pin must declare its version and manifest digest")
            registry = Registry().with_resources(
                [
                    (uri, Resource.from_contents(doc))
                    for p in sorted((root / "schemas").glob("*.schema.json"), key=lambda path: path.name)
                    for doc in [json.loads(p.read_text(encoding="utf-8"))]
                    for uri in {p.name, doc.get("$id", p.name)}
                ]
            )
        except Exception as error:
            raise CatalogError("Pinned catalog integrity check failed: its pin or schema definitions could not be loaded") from error
        self._validators: dict[str, Draft202012Validator] = {}
        self._registry = registry
        self._definitions: dict[str, dict] | None = None
        for path in (root / "contracts" / "phases").glob("P*.json"):
            contract = json.loads(path.read_text(encoding="utf-8"))
            capabilities = contract.get("capabilities", [])
            if "project_notation_v1" in capabilities and "research_presentation_v2" not in capabilities:
                raise CatalogError(
                    f"Unsupported catalog capabilities in {path.stem}: "
                    "project_notation_v1 requires research_presentation_v2")

    @property
    def scientific_validation_enabled(self) -> bool:
        """Older project pins retain their original scientific check scope.

        Reading an old generation never upgrades its validation claim. New
        deterministic checks require an explicitly adopted 1.4+ catalog.
        """
        try:
            return tuple(int(p) for p in self.version.split(".")[:3]) >= (1, 4, 0)
        except ValueError:
            return False

    @property
    def snapshot_sha256(self) -> str:
        """Digest the actual pinned catalog files, independent of timestamps."""
        digest = hashlib.sha256()
        for path in sorted(self.root.rglob("*"), key=lambda path: path.relative_to(self.root).as_posix()):
            if not path.is_file() or path.name in {"catalog-pin.json", "MANIFEST.sha256"} or "__pycache__" in path.parts:
                continue
            relative = path.relative_to(self.root).as_posix()
            digest.update(relative.encode("utf-8") + b"\0")
            digest.update(hashlib.sha256(path.read_bytes()).digest())
        return digest.hexdigest()

    def verify_manifest(self) -> list[Finding]:
        """Check the declared catalog bytes without changing a project pin."""
        manifest_path = self.root / "MANIFEST.sha256"
        if not manifest_path.is_file():
            return [Finding("catalog.manifest_missing", "The pinned catalog manifest is missing.", "catalog", "")]
        data = manifest_path.read_bytes()
        findings = []
        if hashlib.sha256(data).hexdigest() != self.manifest_sha256:
            findings.append(Finding("catalog.manifest_digest", "Catalog manifest bytes differ from the pin.", "catalog", ""))
        declared = set()
        root = self.root.resolve()
        for line in data.decode("utf-8").splitlines():
            try:
                expected, relative = line.split("  ", 1)
                path = (root / relative).resolve()
                matches = path.is_relative_to(root) and path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == expected
            except (ValueError, OSError):
                matches = False
                relative = line
            if relative in declared or not matches:
                findings.append(Finding("catalog.file_digest", f"Catalog source does not match its manifest: {relative}", "catalog", ""))
            declared.add(relative)
        actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
                  and path.name not in {"MANIFEST.sha256", "catalog-pin.json"} and "__pycache__" not in path.parts}
        if actual != declared:
            findings.append(Finding("catalog.file_inventory", "Catalog files differ from the manifest inventory.", "catalog", ""))
        return findings

    def output_definitions(self, phase: str | None = None) -> dict[str, dict]:
        """Return full output IDs with schema, ownership and delivery metadata.

        Preserve the union for older pins: cards and diagnostics were present
        in stage writes before they were added to run_local_outputs.
        """
        if self._definitions is None:
            definitions: dict[str, dict] = {}
            for path in sorted((self.root / "contracts" / "phases").glob("P*.json")):
                contract = json.loads(path.read_text(encoding="utf-8"))
                for item in contract.get("run_local_outputs", []):
                    definitions[item["output_id"]] = dict(item)
                for stage in contract.get("role_stages", []):
                    for output_id in stage.get("writes", []):
                        definition = definitions.setdefault(output_id, {"output_id": output_id})
                        definition.update(stage.get("artifact_contracts", {}).get(output_id, {}))
                        definition.setdefault("stage_ids", []).append(stage["stage_id"])
                        suffix = output_id.split(".", 1)[-1]
                        if "schema_uri" not in definition and suffix in OUTPUT_SCHEMA_BINDINGS:
                            definition["schema_uri"] = OUTPUT_SCHEMA_BINDINGS[suffix]
                            definition["schema_application"] = "jsonl" if suffix == "metrics_long" else "object"
                        roles = stage.get("roles", [])
                        if len(roles) == 1:
                            definition.setdefault("producer", roles[0])
            if (self.root / "schemas" / "assessment.schema.json").is_file():
                definitions["p3.assessment"] = {
                    "output_id": "p3.assessment", "producer": "theorist",
                    "schema_uri": "assessment.schema.json", "schema_application": "object",
                    "artifact_type": "t2p_packet", "audience": ["user"],
                    "delivery": "mention", "publication": "none",
                }
            self._definitions = definitions
        prefix = phase.lower() + "." if phase else ""
        return deepcopy({k: v for k, v in self._definitions.items() if k.startswith(prefix)})

    def schema_for_output(self, contract_output_id: str) -> str | None:
        if not self.scientific_validation_enabled and contract_output_id != "p3.assessment":
            return OUTPUT_SCHEMA_BINDINGS.get(contract_output_id.split(".", 1)[-1])
        definition = self.output_definitions().get(contract_output_id, {})
        uri = definition.get("schema_uri")
        return str(uri).rsplit("/", 1)[-1] if uri else None

    def output_schema(self, contract_output_id: str) -> dict | None:
        """Schema for the complete JSON document (or one JSONL row)."""
        name = self.schema_for_output(contract_output_id)
        if name is None:
            return None
        schema = self.schema_doc(name)
        definition = self.output_definitions().get(contract_output_id, {})
        if self._notation_output_required(contract_output_id):
            schema.setdefault("required", []).append("notation_updates")
        if self.scientific_validation_enabled and definition.get("schema_application") == "each_item":
            return {"type": "array", "items": {"$ref": schema.get("$id", name)}}
        return schema

    def schema_doc(self, schema_name: str) -> dict:
        return json.loads(
            (self.root / "schemas" / schema_name).read_text(encoding="utf-8")
        )

    def artifact_contracts(self) -> dict[str, dict]:
        """family -> {artifact_type, audience, delivery} across all phase
        contracts (contracts v1.2.0+, SPEC/D12)."""
        out: dict[str, dict] = {}
        phases_dir = self.root / "contracts" / "phases"
        if not phases_dir.is_dir():
            return out
        for pf in sorted(phases_dir.glob("P*.json")):
            doc = json.loads(pf.read_text(encoding="utf-8"))
            for stage in doc.get("role_stages", []):
                for fam, meta in (stage.get("artifact_contracts") or {}).items():
                    out[fam] = meta
        return out

    def validate_output(self, contract_output_id: str, document: Any) -> list[Finding]:
        schema_name = self.schema_for_output(contract_output_id)
        if schema_name is None:
            if not self.scientific_validation_enabled:
                return []  # Historical pin, not a claim of 1.4 validation.
            return [Finding("output.contract_unbound", "No schema is declared for this output.",
                            contract_output_id, "")]
        if schema_name not in self._validators:
            schema = json.loads(
                (self.root / "schemas" / schema_name).read_text(encoding="utf-8")
            )
            self._validators[schema_name] = Draft202012Validator(
                schema, registry=self._registry, format_checker=_FMT
            )
        findings = []
        application = self.output_definitions().get(contract_output_id, {}).get("schema_application", "object")
        if not self.scientific_validation_enabled:
            application = "object"
        if application in {"each_item", "jsonl"} and not isinstance(document, list):
            return [Finding("schema.type", "Expected an array of records" +
                            (" parsed from JSONL." if application == "jsonl" else "."),
                            contract_output_id, "")]
        items = enumerate(document) if application in {"each_item", "jsonl"} else [(None, document)]
        for index, item in items:
            for error in self._validators[schema_name].iter_errors(item):
                parts = ([] if index is None else [str(index)]) + [str(p) for p in error.absolute_path]
                pointer = "/" + "/".join(parts) if parts else ""
                findings.append(Finding(f"schema.{error.validator}", error.message,
                                        contract_output_id, pointer))
        findings.extend(self._validate_researcher_decisions(contract_output_id, document, schema_name))
        if (self._notation_output_required(contract_output_id) and isinstance(document, dict)
                and "notation_updates" not in document):
            findings.append(Finding("notation.updates_required", "The Lead account must record its adopted notation updates, including empty arrays when there are no additions.",
                                    contract_output_id, "/notation_updates"))
        return findings

    def _notation_output_required(self, output_id: str) -> bool:
        if output_id not in NOTATION_LEAD_OUTPUTS:
            return False
        phase = output_id.split(".", 1)[0].upper()
        path = self.root / "contracts" / "phases" / f"{phase}.json"
        contract = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        return "project_notation_v1" in contract.get("capabilities", [])

    def _validate_researcher_decisions(self, output_id, document, schema_name):
        """Enforce new authoring only under the run's adopted capability."""
        phase = output_id.split(".", 1)[0].upper()
        path = self.root / "contracts" / "phases" / f"{phase}.json"
        contract = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        if "consequential_researcher_decisions_v1" not in contract.get("capabilities", []):
            return []
        if schema_name in {"attention-item-collection.schema.json", "contextual-attention-item.schema.json"}:
            items = list(enumerate(document)) if isinstance(document, list) else [(None, document)]
            prefix = ""
        elif schema_name in {"research-basis.schema.json", "catalog-assessment.schema.json"} and isinstance(document, dict):
            values = document.get("attention_items", [])
            items = list(enumerate(values)) if isinstance(values, list) else []
            prefix = "/attention_items"
        else:
            return []
        findings = []
        for index, item in items:
            if not isinstance(item, dict) or item.get("kind") != "researcher_decision":
                continue
            pointer = prefix + (f"/{index}" if index is not None else "")
            def flag(code, message, field):
                findings.append(Finding("attention." + code, message, output_id, pointer + "/" + field))
            if item.get("decision_priority") not in ("interpretation", "inference", "data", "resources"):
                flag("decision_priority", "Author the highest material decision priority: interpretation, inference, data or resources.", "decision_priority")
            if item.get("response_kind") not in ("choice", "study_fact"):
                flag("response_kind", "Distinguish a researcher choice from a request for study information.", "response_kind")
            options = item.get("options")
            if item.get("response_kind") == "study_fact":
                if options or item.get("recommendation") or item.get("recommended_option_id"):
                    flag("study_fact", "Request the missing fact and its consequence; do not prescribe an answer or offer preference options.", "response_kind")
            elif item.get("response_kind") == "choice":
                if not isinstance(item.get("recommendation"), str) or not item["recommendation"].strip():
                    flag("recommendation", "Give the Lead recommendation and reason, or explain why available evidence does not support one.", "recommendation")
                if options is not None:
                    if (not isinstance(options, list)
                            or any(not isinstance(option, dict)
                                   or any(not isinstance(option.get(key), str) or not option[key].strip()
                                          for key in ("id", "label", "consequence")) for option in options)):
                        flag("options", "Each selectable alternative needs an authored id, label and practical consequence. Omit options for an open-ended choice.", "options")
                    elif len({option["id"] for option in options}) != len(options):
                        flag("option_ids", "Selectable alternatives need distinct option IDs within this exact question.", "options")
                recommended = item.get("recommended_option_id")
                if recommended is not None:
                    option_ids = [option.get("id") for option in options if isinstance(option, dict)] if isinstance(options, list) else []
                    if recommended not in option_ids:
                        flag("recommended_option", "The suggested option must name an option in this exact question.", "recommended_option_id")
                    elif ({"research_presentation_v1", "research_presentation_v2"} & set(contract.get("capabilities", []))) and option_ids[0] != recommended:
                        flag("recommended_option_order", "Place the suggested option first while retaining its authored ID.", "recommended_option_id")
        return findings
