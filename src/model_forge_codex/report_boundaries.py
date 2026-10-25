"""Authored report boundaries in the scientific reader's root Markdown blocks.

Positions refer to the unchanged source lines. A bibliography declaration never
depends on a heading's wording or on the current project catalog.
"""
from __future__ import annotations

import re

_ANCHOR = re.compile(r'<a id="([A-Za-z0-9_.:-]+)"></a>')
_HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.*)$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_LIST = re.compile(r"^( *)([-+*]|\d+[.)])( +)(.*)$")
_QUOTE = re.compile(r"^ {0,3}> ?")
_DISPLAY = re.compile(r"`[^`]*`|(?<!\\)\$\$|(?<!\\)\\\[|(?<!\\)\\\]")


def _display_state(line, current=None):
    if re.fullmatch(r"[ \t]*\$(?!\$)[ \t]*", line):
        return None if current == "$" else current or "$"
    for match in _DISPLAY.finditer(line):
        token = match[0]
        if token.startswith("`"):
            continue
        if current == token:
            current = None
        elif current is None and token in ("$$", r"\["):
            current = "$$" if token == "$$" else r"\]"
    return current


def _prose(text):
    """Hide code spans and supported math without moving the source positions."""
    # A code span may contain shorter backtick runs, including a single tick.
    # Only a run of the same length closes it.
    start = 0
    while match := re.search(r"`+", text[start:]):
        begin = start + match.start()
        run = match[0]
        closing = re.search(r"(?<!`)" + re.escape(run) + r"(?!`)", text[begin + len(run):])
        if closing is None:
            start = begin + len(run)
            continue
        end = begin + len(run) + closing.end()
        text = text[:begin] + " " * (end - begin) + text[end:]
        start = end
    opaque = re.compile(
        r"(?<!\\)\$\$[\s\S]*?(?<!\\)\$\$"
        r"|(?<!\\)\\\[[\s\S]*?(?<!\\)\\\]"
        r"|(?m:^[ \t]*\$(?!\$)[ \t]*\n[\s\S]*?^[ \t]*\$(?!\$)[ \t]*$)"
        r"|(?<![$\\])\$(?!\$)(?:\\.|[^$\n])+\$(?!\$)"
        r"|(?<!\\)\\\([^\n]*?\\\)"
    )
    return opaque.sub(lambda match: " " * len(match[0]), text)


def _list_marker(line):
    match = _LIST.match(line)
    if match is None:
        return None
    return {"indent": len(match[1]), "ordered": match[2][0].isdigit(), "text": match[4]}


def _table_separator(line):
    cells = line.strip().strip("|").split("|")
    return bool(cells) and all(re.fullmatch(r"\s*:?-{3,}:?\s*", cell) for cell in cells)


def _root_blocks(markdown):
    """Mirror researchBlocks' root structure, retaining source line locations."""
    lines = str(markdown).splitlines()
    blocks = []
    i = 0

    def starts_block(at):
        line = lines[at]
        return (_HEADING.match(line) or _FENCE.match(line) or _LIST.match(line) or _QUOTE.match(line)
                or ("|" in line and at + 1 < len(lines) and _table_separator(lines[at + 1])))

    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        code = _FENCE.match(line)
        if code:
            closing = re.compile(r"^ {0,3}" + re.escape(code[1][0]) + "{" + str(len(code[1])) + r",}\s*$")
            i += 1
            while i < len(lines) and not closing.match(lines[i]):
                i += 1
            i += i < len(lines)
            blocks.append({"kind": "opaque"})
            continue
        if line.startswith(("    ", "\t")):
            i += 1
            while i < len(lines) and (not lines[i].strip() or lines[i].startswith(("    ", "\t"))):
                i += 1
            blocks.append({"kind": "opaque"})
            continue
        title = _HEADING.match(line)
        if title:
            blocks.append({"kind": "heading", "text": title[2], "start_line": i, "heading_line": i})
            i += 1
            continue
        if _QUOTE.match(line):
            while i < len(lines) and _QUOTE.match(lines[i]):
                i += 1
            blocks.append({"kind": "opaque"})
            continue
        first = _list_marker(line)
        if first:
            while i < len(lines):
                item = _list_marker(lines[i])
                if not item or item["indent"] != first["indent"] or item["ordered"] != first["ordered"]:
                    break
                display = _display_state(item["text"])
                i += 1
                while i < len(lines):
                    following = lines[i]
                    marker = _list_marker(following)
                    indent = len(following) - len(following.lstrip())
                    if not display and marker and marker["indent"] <= first["indent"]:
                        break
                    if not display and following.strip() and indent <= first["indent"]:
                        break
                    if not display and not following.strip():
                        at = i + 1
                        while at < len(lines) and not lines[at].strip():
                            at += 1
                        if at == len(lines) or len(lines[at]) - len(lines[at].lstrip()) <= first["indent"]:
                            i = at
                            break
                    display = _display_state(following, display)
                    i += 1
            blocks.append({"kind": "opaque"})
            continue
        if "|" in line and i + 1 < len(lines) and _table_separator(lines[i + 1]):
            i += 2
            while i < len(lines) and lines[i].strip() and "|" in lines[i]:
                i += 1
            blocks.append({"kind": "opaque"})
            continue
        start = i
        body = [line]
        display = _display_state(line)
        i += 1
        while i < len(lines) and not _FENCE.match(lines[i]) and (display or (lines[i].strip() and not starts_block(i))):
            body.append(lines[i])
            display = _display_state(lines[i], display)
            i += 1
        blocks.append({"kind": "paragraph", "text": "\n".join(body), "start_line": start})
    return blocks


def report_anchor_headings(markdown, anchors):
    """Resolve every supplied declaration to one unique genuine root heading."""
    if not isinstance(anchors, dict) or any(not isinstance(anchor, str) or not anchor for anchor in anchors.values()):
        raise ValueError("Each report section must declare a nonempty authored anchor")
    if len(set(anchors.values())) != len(anchors):
        raise ValueError("The references boundary must be distinct from all seven report section anchors")
    blocks = _root_blocks(markdown)
    occurrences = {}
    for index, block in enumerate(blocks):
        if block["kind"] not in ("heading", "paragraph"):
            continue
        for match in _ANCHOR.finditer(_prose(block["text"])):
            occurrences.setdefault(match[1], []).append(index)
    found = {}
    for key, anchor in anchors.items():
        positions = occurrences.get(anchor, [])
        if len(positions) != 1:
            raise ValueError(f"The {key.replace('_', ' ')} anchor must occur exactly once outside code, math, lists and quotations")
        at = positions[0]
        block = blocks[at]
        heading_index = at if block["kind"] == "heading" else None
        if heading_index is None and not _ANCHOR.sub("", block["text"]).strip():
            if at + 1 < len(blocks) and blocks[at + 1]["kind"] == "heading":
                heading_index = at + 1
            elif at > 0 and blocks[at - 1]["kind"] == "heading":
                heading_index = at - 1
        if heading_index is None:
            raise ValueError(f"The {key.replace('_', ' ')} anchor must identify one genuine top-level heading")
        heading = blocks[heading_index]
        found[key] = {"anchor": anchor, "start_line": min(block["start_line"], heading["start_line"]),
                      "heading_line": heading["start_line"],
                      "label": _ANCHOR.sub("", heading["text"]).strip()}
    if len({row["heading_line"] for row in found.values()}) != len(found):
        raise ValueError("The references boundary and seven report sections must identify distinct headings")
    return found


def reference_boundary(markdown, section_anchors, content_sections):
    """Return an explicit trailing bibliography boundary, or None for legacy reports."""
    if not isinstance(section_anchors, dict) or "references" not in section_anchors:
        return None
    keys = (*content_sections, "references")
    found = report_anchor_headings(markdown, {key: section_anchors.get(key) for key in keys})
    boundary = found["references"]
    if any(found[key]["heading_line"] >= boundary["start_line"] for key in content_sections):
        raise ValueError("The references boundary must follow all seven scientific report sections")
    return boundary
