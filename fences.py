"""Repair code fences in AI-written Markdown.

Small models sometimes write a bare opening fence right before a fence that names the language,
or indent a code block inside a list. Both break the block, so the commands lose their Copy
text. This module rewrites those fences so each command sits in one complete block.
"""
import re

OPEN = re.compile(r"^(\s*)(`{3,}|~{3,})\s*([\w+.#-]*)\s*$")


def _closes(line, marker):
    """True for a line of only fence characters, at least as long as the opening fence."""
    stripped = line.strip()
    return len(stripped) >= len(marker) and stripped == stripped[:1] * len(stripped) and stripped[:1] == marker[:1]


def repair_fences(text):
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out = []
    i = 0
    while i < len(lines):
        match = OPEN.match(lines[i])
        if not match:
            out.append(lines[i])
            i += 1
            continue
        indent, marker, lang = len(match.group(1)), match.group(2), match.group(3)
        i += 1
        # A bare fence directly followed by a fence that names a language is a stray line:
        # the second fence is the real opener.
        if not lang and i < len(lines):
            following = OPEN.match(lines[i])
            if following and following.group(3):
                lang, marker = following.group(3), following.group(2)
                i += 1
        body = []
        while i < len(lines) and not _closes(lines[i], marker):
            body.append(re.sub(r"^ {0,%d}" % indent, "", lines[i]))
            i += 1
        i += 1  # skip the closing fence
        if any(line.strip() for line in body):  # an empty block is dropped instead of shown empty
            out.append("```" + lang)
            out.extend(body)
            out.append("```")
    return "\n".join(out)