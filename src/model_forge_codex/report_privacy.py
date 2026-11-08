"""Derived scientific materials for sharing, separate from retained source bytes.

This boundary removes researcher answer records and machine locations. It does
not paraphrase scientific claims or round measurements. Source integrity is
checked by the caller before a projection is made.
"""
from __future__ import annotations

import html
import base64
import csv
import io
import json
import re
import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import unquote_to_bytes

from .records import ArtifactError
from .storage import sha256_bytes

_PRIVATE_FIELDS = {
    "retained_answers", "saved_answers", "researcher_answers", "answer_routes",
    "answer_text", "answer_markdown", "researcher_note", "researcher_notes",
    "private_notes", "transcript", "transcripts", "conversation", "messages",
    "unamended_instructions", "credentials", "access_token", "refresh_token", "api_key", "password", "private_key",
}
_CREDENTIAL_FIELDS = {"credentials", "access_token", "refresh_token", "api_key", "password", "private_key"}
_POINTER_FIELDS = {"pointer", "scalar_pointer", "json_pointer", "source_pointer"}
_PATH_FIELDS = {"path", "artifact_path", "original_path", "snapshot_path", "source_path",
                "working_directory", "cwd", "directory", "output_dir", "input_dir", "filename"}
_LOCAL_PATH = re.compile(
    r"(?<![\w])(?:file:(?://)?[^\s<>\"']+|[A-Za-z]:[\\/][^\r\n<>\"'\s]+|"
    r"\\\\[A-Za-z0-9][A-Za-z0-9_.-]*\\[A-Za-z0-9][^\r\n{}<>\"'\s]*|~[\\/][^\r\n<>\"'\s]+|"
    r"(?<![:/])/(?:Users|home|root|private|tmp|var|mnt|Volumes|opt|srv|workspace|workspaces|data|etc|usr)"
    r"/[^\r\n<>\"'\s]+)", re.IGNORECASE)
_OMITTED_PATH = "[local path omitted]"
_OMITTED_NOTE = "[researcher note omitted]"
_QUOTED_LOCAL_PATH = re.compile(r"([\"'`])((?:[A-Za-z]:[\\/]|\\\\|/|~[\\/]|file:)[^\r\n]*?)\1")
_INLINE_DATA = re.compile(r"data:([\w.+-]+/[\w.+-]+)(;base64)?,([^\s\"'<>`\)]+)", re.IGNORECASE)
_HOME_PATH = re.compile(r"(?<![\w:/])(?:[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/][^\\/\r\n]+[\\/]|/(?:Users|home)/[^/\r\n]+/)", re.IGNORECASE)
_LOCAL_FILE = re.compile(
    r"(?<![\w:/])(?:file:(?://)?|[A-Za-z]:[\\/]|\\\\[A-Za-z0-9][A-Za-z0-9_.-]*\\|/[A-Za-z0-9_.-]+/)"
    r"[^\r\n<>\"';]*?\.(?:csv|tsv|jsonl?|ndjson|txt|md|ya?ml|toml|ini|cfg|py|r|rds|rdata|xlsx?|pdf|png|svg|jpe?g|"
    r"parquet|feather|sqlite|db|sh|ps1|log|html?|tex|docx?|zip|gz)(?=$|[\s.,;:!?)>])", re.IGNORECASE)
_LOCAL_DIRECTORY = re.compile(
    r"(?<![\w:/])(?:[A-Za-z]:[\\/]|/(?:Users|home|root|private|tmp|var|mnt|Volumes|opt|srv|workspace|workspaces|data|etc|usr)/)"
    r"(?:(?:[^\\/\r\n<>\"'.,;:!?]|\.(?!\s|$))+[\\/])+[^\\/\s.,;:!?<>\"']+(?=$|[.,;:!?](?:\s|$))", re.IGNORECASE)
_MATH_SPAN = re.compile(r"(\$\$[\s\S]*?\$\$|(?<!\\)\$(?:\\.|[^$\n])*?\$|\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\))")


class UnshareableMaterial(ArtifactError):
    """Retained bytes have no inspected scientific projection for sharing."""

    def __init__(self, message, *, reason="uninspected_material"):
        super().__init__(message)
        self.reason = reason


_REPRODUCTION_SUFFIXES = {".py", ".r", ".rmd", ".jl", ".m", ".c", ".cc", ".cpp", ".h", ".hpp", ".java",
    ".js", ".mjs", ".ts", ".sh", ".bash", ".ps1", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".json",
    ".jsonl", ".ndjson", ".csv", ".tsv", ".txt", ".md", ".tex", ".svg", ".png"}
_CODE_SUFFIXES = {".py", ".r", ".jl", ".m", ".c", ".cc", ".cpp", ".java", ".js", ".mjs", ".ts", ".sh", ".bash", ".ps1"}
_PRIVATE_MATERIAL_NAMES = re.compile(r"^(?:researcher[_-]answers?|saved[_-]answers?|problem[_-]context|attention[_-]resolutions?|"
    r"open[_-]attention|basis|run|session|events?|messages?|transcripts?|stream|stdout|stderr|debug|"
    r"diagnostic[_-]logs?|credentials?|tokens?|secrets?|accounts?|provider(?:[_-].*)?|team)(?:\.|$)", re.IGNORECASE)
_PRIVATE_MATERIAL_DIRECTORIES = {"logs", "transcripts", "researcher", "providers", "credentials", ".codex", ".aws", ".ssh"}
_LOOPBACK_WORKBENCH = re.compile(r"https?://(?:localhost|127(?:\.\d{1,3}){3}|\[::1\])(?::\d+)?/api/(?:v1/|log\b)[^\s<>\"')]*", re.IGNORECASE)


def private_report_material(name):
    """Explicit private operational sources are not shareable attachments."""
    path = PurePosixPath(str(name).replace("\\", "/"))
    return bool(any(part.casefold() in _PRIVATE_MATERIAL_DIRECTORIES for part in path.parts[:-1])
        or path.suffix.lower() not in _CODE_SUFFIXES and _PRIVATE_MATERIAL_NAMES.match(path.name)
        or path.name.casefold().startswith(".env")
        or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}
        or path.name.casefold() in {"id_rsa", "id_ed25519", ".npmrc", ".pypirc", ".netrc"})


def _shareable_markdown_links(text, omitted):
    def link(match):
        omitted.add("local_workbench_links")
        return match[1] + " (local workbench source omitted)"
    text = re.sub(r"\[([^\]]+)\]\((" + _LOOPBACK_WORKBENCH.pattern + r")\)", link, text, flags=re.IGNORECASE)
    text, count = _LOOPBACK_WORKBENCH.subn("[local workbench source omitted]", text)
    if count:
        omitted.add("local_workbench_links")
    return text


def shareable_reproduction_archive(materials, *, method_identity=None, generation_ref=None, omitted_materials=()):
    """Package already-projected declared files, retaining their authored folders.

    No directories are scanned and no existing archive is copied. The manifest
    distinguishes source digests from the digests of the actual shared bytes.
    """
    materials = list(materials)
    if not any(PurePosixPath(str(name).replace("\\", "/")).suffix.lower() in _CODE_SUFFIXES for name, _ in materials):
        return None
    files = {}
    casefolded_paths = {}
    manifest = []
    for name, projection in materials:
        path = PurePosixPath(str(name).replace("\\", "/"))
        if path.suffix.lower() not in _REPRODUCTION_SUFFIXES and path.name.lower() not in {"makefile", "dockerfile", "requirements"}:
            continue
        if (path.is_absolute() or ".." in path.parts or ":" in str(path) or not path.parts
                or str(path) in {".", "model-forge-shareable-export.json"}):
            raise ArtifactError("Shared reproduction materials require safe authored relative paths")
        if (private_report_material(name)
                or path.suffix.lower() == ".txt" and not re.match(r"^(?:readme|requirements|license|environment)(?:[.\-_]|$)", path.name, re.IGNORECASE)):
            continue
        name = str(path)
        if any(part.endswith((".", " ")) for part in path.parts):
            raise ArtifactError("Shared reproduction materials require portable authored filenames")
        folded = name.casefold()
        if folded in casefolded_paths and casefolded_paths[folded] != name:
            raise ArtifactError("Shared reproduction materials have case-conflicting authored paths")
        casefolded_paths[folded] = name
        if name in files:
            if files[name] != projection.content:
                raise ArtifactError("Shared reproduction materials have conflicting authored paths")
            continue
        files[name] = projection.content
        manifest.append({"path": name, "sha256": projection.sha256, "source_sha256": projection.source_sha256,
            "kind": "scientific_extract" if projection.changed else "verified_source",
            "omitted_categories": list(projection.omitted_categories)})
    if not any(PurePosixPath(name).suffix.lower() in _CODE_SUFFIXES for name in files):
        return None
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
        archive.writestr("model-forge-shareable-export.json", json.dumps({"export_kind": "shareable_scientific_projection",
            "method_identity": method_identity, "report_generation": generation_ref,
            "reproduction_status": "retained_materials_not_rerun", "files": manifest,
            "omitted_materials": list(omitted_materials)}, ensure_ascii=False, indent=2))
    return output.getvalue()


def _researcher_item(value):
    return bool(isinstance(value, dict) and (value.get("origin") == "researcher_reported"
                or value.get("answer_refs") or value.get("answer_ref")
                or "attention_id" in value and "note" in value))


@dataclass(frozen=True)
class ShareableAsset:
    content: bytes
    source_sha256: str
    sha256: str
    omitted_categories: tuple[str, ...]

    @property
    def changed(self):
        return self.source_sha256 != self.sha256


class ShareableReportPrivacy:
    def __init__(self, *sources):
        notes = set()

        def collect(value, private=False):
            if isinstance(value, dict):
                researcher = _researcher_item(value)
                for key, child in value.items():
                    if isinstance(child, str) and (private and key in {"note", "statement", "text"}
                                                  or researcher and key in {"note", "statement"}):
                        if child.strip():
                            notes.add(child.strip())
                    collect(child, private or key in {"retained_answers", "saved_answers", "researcher_answers", "answer_routes"})
            elif isinstance(value, list):
                for child in value:
                    collect(child, private)

        for source in sources:
            collect(source)
            snapshot = (source.get("cumulative_inputs") or {}).get("researcher_answers") if isinstance(source, dict) else None
            if isinstance(snapshot, dict) and snapshot.get("snapshot_path"):
                path = Path(snapshot["snapshot_path"])
                try:
                    content = path.read_bytes()
                    document = json.loads(content)
                    # Cumulative inputs use the harness's canonical JSON
                    # digest, unlike artifact pointers' exact-byte digest.
                    digest = sha256_bytes(json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())
                    if digest != snapshot.get("sha256"):
                        raise ValueError("changed digest")
                    collect(document, private=True)
                except (OSError, ValueError, TypeError) as exc:
                    raise ArtifactError("The report's frozen researcher-answer source changed or disappeared") from exc
        # Protect copies in arbitrary scientific fields too, including JSON- or
        # HTML-escaped copies. Short answers are only matched as entire values.
        variants = {variant for note in notes for variant in (note, html.escape(note), json.dumps(note, ensure_ascii=False)[1:-1])}
        self.notes = sorted(variants, key=len, reverse=True)
        self.normalized_notes = {" ".join(note.split()).casefold() for note in self.notes}
        self.note_patterns = [(sum(map(len, note.split())), re.compile(r"\s+".join(re.escape(part) for part in note.split()), re.IGNORECASE))
                              for note in self.notes if len(note) >= 16]
        self._inline_depth = 0

    def _text(self, value, omitted, *, key=""):
        def inline(match):
            if self._inline_depth >= 8:
                raise ArtifactError("A shareable material has too many nested encoded attachments")
            try:
                content = base64.b64decode(match[3], validate=True) if match[2] else unquote_to_bytes(match[3])
            except ValueError as exc:
                raise ArtifactError("A shareable material has an invalid encoded attachment") from exc
            self._inline_depth += 1
            try:
                projected = self.asset(content, match[1].lower())
            finally:
                self._inline_depth -= 1
            omitted.update(projected.omitted_categories)
            return (f"data:{match[1]};base64," + base64.b64encode(projected.content).decode("ascii")) if projected.changed else match[0]
        value = _INLINE_DATA.sub(inline, value)
        if value.lstrip().startswith(("{", "[")):
            try:
                nested = json.loads(value)
            except (ValueError, TypeError):
                pass
            else:
                projected = self._value(nested, omitted, key=key, dependency=key == "context_dependencies")
                if projected != nested:
                    return json.dumps(projected, ensure_ascii=False)
        if " ".join(value.split()).casefold() in self.normalized_notes:
            omitted.add("researcher_notes")
            return _OMITTED_NOTE
        for minimum, pattern in self.note_patterns:
            if len(value) < minimum:
                continue
            value, count = pattern.subn(lambda _: _OMITTED_NOTE, value)
            if count:
                omitted.add("researcher_notes")
        if key not in _POINTER_FIELDS:
            if (key in _PATH_FIELDS and (value.startswith(("/", "~/", "~\\", "\\\\", "file:"))
                                         or re.match(r"^[A-Za-z]:[\\/]", value))):
                omitted.add("local_paths")
                return _OMITTED_PATH
            def quoted(match):
                omitted.add("local_paths")
                return match[1] + _OMITTED_PATH + match[1]
            value = _QUOTED_LOCAL_PATH.sub(quoted, value)
            def paths(part):
                safe, count = _LOCAL_FILE.subn(lambda _: _OMITTED_PATH, part)
                if count:
                    omitted.add("local_paths")
                safe, count = _LOCAL_DIRECTORY.subn(lambda _: _OMITTED_PATH, safe)
                if count:
                    omitted.add("local_paths")
                ambiguous = _HOME_PATH.search(safe)
                if ambiguous and re.search(r"\s", re.split(r"[\r\n<>\"';]", safe[ambiguous.start():], maxsplit=1)[0]):
                    raise UnshareableMaterial("A shareable material has an ambiguous unquoted local directory; use a relative scientific location",
                                              reason="ambiguous_local_directory")
                safe, count = _HOME_PATH.subn(lambda _: _OMITTED_PATH + "/", safe)
                if count:
                    omitted.add("local_paths")
                safe, count = _LOCAL_PATH.subn(lambda _: _OMITTED_PATH, safe)
                if count:
                    omitted.add("local_paths")
                return safe
            if key not in {"latex", "symbol", "formula"}:
                value = "".join(part if index % 2 else paths(part) for index, part in enumerate(_MATH_SPAN.split(value)))
        return value

    def _value(self, value, omitted, *, key="", dependency=False):
        if isinstance(value, list):
            return [self._value(child, omitted, key=key, dependency=dependency) for child in value]
        if isinstance(value, dict):
            researcher = _researcher_item(value)
            result = {}
            for name, child in value.items():
                if (name in _PRIVATE_FIELDS or dependency and name == "statement_used"
                        or researcher and name in {"note", "statement"}):
                    omitted.add("credentials" if name in _CREDENTIAL_FIELDS else "researcher_notes")
                    continue
                safe_name = self._text(name, omitted) if isinstance(name, str) else name
                if safe_name in result:
                    raise ArtifactError("Private locations collide in a shareable scientific extract")
                result[safe_name] = self._value(child, omitted, key=name,
                    dependency=dependency or name == "context_dependencies")
            return result
        if isinstance(value, str):
            return self._text(value, omitted, key=key)
        return value

    def project(self, value):
        """Return the scientific structure without raw answer prose or locations."""
        return self._value(value, set())

    def text(self, value):
        return self._text(value, set())

    def asset(self, content: bytes, media_type: str, filename: str = "") -> ShareableAsset:
        omitted = set()
        source_digest = sha256_bytes(content)
        suffix = filename.rsplit(".", 1)[-1].lower()
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            # Accept only PNG chunks whose contents do not carry arbitrary text.
            # Do not strip color or orientation metadata and change a figure.
            _verify_png(content)
        elif content.startswith(b"\xff\xd8"):
            raise UnshareableMaterial("A shareable JPEG may contain private metadata; declare a metadata-free PNG or SVG figure")
        else:
            if (media_type in {"application/zip", "application/gzip", "application/x-gzip", "application/x-tar", "application/x-7z-compressed", "application/pdf"}
                    or content.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08", b"\x1f\x8b", b"%PDF-"))
                    or suffix in {"zip", "gz", "tgz", "tar", "7z", "pdf", "pickle", "pkl", "npy", "npz"}):
                raise UnshareableMaterial("A shareable report cannot include an opaque archive or document; declare its scientific text, data or code files separately")
            try:
                text = content.decode("utf-8-sig")
            except UnicodeError as exc:
                raise UnshareableMaterial("A shareable report cannot include an opaque binary material") from exc
            if "\x00" in text:
                raise UnshareableMaterial("A shareable report cannot include an opaque binary material")
            if media_type in {"application/json", "application/ld+json"} or suffix == "json":
                try:
                    original = json.loads(text)
                except ValueError as exc:
                    raise ArtifactError("A shareable JSON material is not valid JSON") from exc
                projected = self._value(original, omitted)
                if projected != original:
                    content = (json.dumps(projected, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            elif media_type in {"application/x-ndjson", "application/jsonl"} or suffix in {"jsonl", "ndjson"}:
                try:
                    original = [json.loads(line) for line in text.splitlines() if line.strip()]
                except ValueError as exc:
                    raise ArtifactError("A shareable JSON-lines material is not valid JSON") from exc
                projected = self._value(original, omitted)
                if projected != original:
                    content = ("\n".join(json.dumps(row, ensure_ascii=False) for row in projected) + "\n").encode("utf-8")
            elif media_type in {"text/csv", "text/tab-separated-values"} or suffix in {"csv", "tsv"}:
                delimiter = "\t" if suffix == "tsv" or media_type == "text/tab-separated-values" else ","
                try:
                    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter, strict=True))
                except csv.Error as exc:
                    raise ArtifactError("A shareable table material is malformed") from exc
                if rows:
                    headers = rows[0]
                    included = [index for index, name in enumerate(headers) if name not in _PRIVATE_FIELDS]
                    if len(included) != len(headers):
                        omitted.update("credentials" if name in _CREDENTIAL_FIELDS else "researcher_notes"
                                       for name in headers if name in _PRIVATE_FIELDS)
                    projected = [[self._text(headers[index], omitted) for index in included]]
                    for row in rows[1:]:
                        if not row:
                            projected.append(row)
                            continue
                        if len(row) != len(headers):
                            raise ArtifactError("A shareable table material has inconsistent columns")
                        researcher = _researcher_item(dict(zip(headers, row)))
                        projected.append([_OMITTED_NOTE if researcher and headers[index] in {"note", "statement"}
                            else self._value(row[index], omitted, key=headers[index]) for index in included])
                    if projected != rows:
                        output = io.StringIO(newline="")
                        csv.writer(output, delimiter=delimiter, lineterminator="\n").writerows(projected)
                        content = output.getvalue().encode("utf-8")
            else:
                projected = self._text(text, omitted)
                if media_type == "text/markdown" or suffix in {"md", "markdown"}:
                    projected = _shareable_markdown_links(projected, omitted)
                if projected != text:
                    content = projected.encode("utf-8")
        return ShareableAsset(content, source_digest, sha256_bytes(content), tuple(sorted(omitted)))


def _verify_png(content):
    offset = 8
    while offset < len(content):
        if offset + 12 > len(content):
            raise ArtifactError("A shareable PNG figure is malformed")
        size = struct.unpack(">I", content[offset:offset + 4])[0]
        end = offset + size + 12
        kind = content[offset + 4:offset + 8]
        if end > len(content):
            raise ArtifactError("A shareable PNG figure is malformed")
        if kind not in {b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tRNS", b"gAMA", b"cHRM", b"sRGB", b"pHYs", b"sBIT", b"bKGD", b"hIST"}:
            raise UnshareableMaterial("A shareable PNG has uninspected metadata; declare a metadata-free PNG or SVG figure")
        offset = end
        if kind == b"IEND":
            if offset != len(content):
                raise UnshareableMaterial("A shareable PNG has uninspected trailing data")
            return
    raise ArtifactError("A shareable PNG figure is malformed")
