"""Read bounded table previews from already verified exhibit artifacts."""
from __future__ import annotations

import csv
import io
import json
import math
import re
from pathlib import Path

MAX_SOURCE_BYTES = 5_000_000
MAX_PREVIEW_ROWS = 200
MAX_COLUMNS = 40
MAX_ARRAY_ITEMS = 64
MAX_ARRAY_TEXT = 4096


def _display_cell(value):
    def scalar(item):
        return isinstance(item, (str, int, float, bool, type(None))) and not (
            isinstance(item, float) and not math.isfinite(item))

    if isinstance(value, list) and len(value) <= MAX_ARRAY_ITEMS and all(scalar(item) for item in value):
        # Format the exact source value, without flattening or inferring units.
        text = json.dumps(value, ensure_ascii=False, allow_nan=False)
        if len(text) <= MAX_ARRAY_TEXT:
            return text
    elif scalar(value):
        return value
    raise ValueError("Table cells must be finite scalars, explicitly missing, or short flat arrays of scalar values.")


def _markdown_cells(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith(r"\|"):
        line = line[:-1]
    return [part.strip().replace(r"\|", "|") for part in re.split(r"(?<!\\)\|", line)]


def table_preview(path: Path, exhibit: dict, *, offset: int = 0) -> dict:
    if type(offset) is not int or offset < 0:
        raise ValueError("The table row offset must be a nonnegative integer.")
    if path.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError("The table exceeds the inline preview size limit; open its original artifact.")
    source = path.read_text(encoding="utf-8-sig")
    media = exhibit.get("media_type")
    metadata = []
    if media == "text/csv":
        values = list(csv.reader(io.StringIO(source)))
        if not values:
            raise ValueError("The table artifact is empty.")
        keys, raw_rows = values[0], [row for row in values[1:] if row]
    elif media == "application/json":
        def reject_constant(value):
            raise ValueError("The table contains a nonfinite number.")
        document = json.loads(source, parse_constant=reject_constant)
        if isinstance(document, list):
            raw_rows = document
            keys = list(document[0]) if document and isinstance(document[0], dict) else []
        elif isinstance(document, dict) and isinstance(document.get("rows"), list):
            raw_rows = document["rows"]
            columns = document.get("columns", [])
            metadata = [column for column in columns if isinstance(column, dict)]
            keys = [column.get("key") if isinstance(column, dict) else column for column in columns]
        else:
            raise ValueError("JSON table must contain named columns and rows or an array of row objects.")
    elif media == "text/markdown":
        lines = source.splitlines()
        position = next((i for i in range(1, len(lines))
                         if "|" in lines[i - 1] and all(re.fullmatch(r":?-{3,}:?", cell)
                         for cell in _markdown_cells(lines[i]))), None)
        if position is None:
            raise ValueError("No supported Markdown table was found in the artifact.")
        keys = _markdown_cells(lines[position - 1])
        raw_rows = []
        for line in lines[position + 1:]:
            if not line.strip() or "|" not in line:
                break
            raw_rows.append(_markdown_cells(line))
    else:
        raise ValueError("This table format has no inline renderer.")
    if (not keys or len(keys) > MAX_COLUMNS or any(not isinstance(key, str) or not key.strip() for key in keys)
            or len(set(keys)) != len(keys)):
        raise ValueError("The table must have unique named columns within the inline width limit.")
    # Only spacing and initial case are presentation defaults. In particular,
    # do not infer units or expand a scientific abbreviation from its name.
    columns = [{"key": key, "label": key.replace("_", " ")[:1].upper() + key.replace("_", " ")[1:]} for key in keys]
    for declared in (metadata, exhibit.get("table_columns", [])):
        if not isinstance(declared, list) or any(not isinstance(column, dict) for column in declared):
            raise ValueError("Table column labels are malformed.")
        if len({column.get("key") for column in declared}) != len(declared):
            raise ValueError("Table column labels contain duplicate keys.")
        for column in declared:
            if column.get("key") not in keys:
                raise ValueError("A table column label does not match the source artifact.")
            target = columns[keys.index(column["key"])]
            for field in ("label", "unit"):
                if field in column:
                    if not isinstance(column[field], str):
                        raise ValueError("Table labels and units must be text.")
                    target[field] = column[field]
    rows = []
    for position, row in enumerate(raw_rows):
        if isinstance(row, list) and len(row) == len(keys):
            row = dict(zip(keys, row))
        if not isinstance(row, dict) or set(row) != set(keys):
            raise ValueError("A table row does not match the declared source columns.")
        rendered = {key: _display_cell(value) for key, value in row.items()}
        if offset <= position < offset + MAX_PREVIEW_ROWS:
            rows.append(rendered)
    return {"columns": columns, "rows": rows, "total_rows": len(raw_rows),
            "truncated": offset + len(rows) < len(raw_rows),
            "row_offset": offset, "page_size": MAX_PREVIEW_ROWS}
