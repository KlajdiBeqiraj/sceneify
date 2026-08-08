"""Marked region helpers for Level-1 Python source sync."""

from __future__ import annotations

BEGIN_MARKER = "# sceneify:scene-begin"
END_MARKER = "# sceneify:scene-end"


def wrap_with_markers(body: str) -> str:
    text = body.rstrip() + "\n"
    return f"{BEGIN_MARKER}\n{text}{END_MARKER}\n"


def replace_marked_region(source: str, body: str) -> str:
    """Replace an existing marked region, or append one if missing."""
    begin = source.find(BEGIN_MARKER)
    end = source.find(END_MARKER)
    replacement = wrap_with_markers(body)
    if begin == -1 or end == -1 or end < begin:
        if not source.endswith("\n") and source:
            source += "\n"
        return source + ("\n" if source and not source.endswith("\n\n") else "") + replacement
    end_line = end + len(END_MARKER)
    # Consume a trailing newline after the end marker when present.
    if end_line < len(source) and source[end_line] == "\n":
        end_line += 1
    return source[:begin] + replacement + source[end_line:]


def extract_marked_region(source: str) -> str | None:
    begin = source.find(BEGIN_MARKER)
    end = source.find(END_MARKER)
    if begin == -1 or end == -1 or end < begin:
        return None
    start = begin + len(BEGIN_MARKER)
    if start < len(source) and source[start] == "\n":
        start += 1
    return source[start:end]
