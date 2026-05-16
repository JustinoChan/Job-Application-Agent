from __future__ import annotations

import re
from html import unescape

_TAG_RE = re.compile(r"<[^>]+>")
# HN comments use a bare `<p>` as a paragraph SEPARATOR (no closing tag).
# Other sources use the conventional `<p>...</p>` wrapper or `<br>`. Break
# on either side: opening `<p>` (with optional attributes) and standard
# closing tags. Otherwise paragraph text collapses into a single line.
_BLOCK_BREAK_RE = re.compile(
    r"<\s*p(\s[^>]*)?>|</p>|</li>|</h[1-6]>|<br\s*/?>",
    re.IGNORECASE,
)
_HSPACE_RE = re.compile(r"[ \t ]+")
_NEWLINES_RE = re.compile(r"\n{3,}")


def html_to_text(html: str | None) -> str:
    if not html:
        return ""
    text = _BLOCK_BREAK_RE.sub("\n", html)
    text = _TAG_RE.sub("", text)
    text = unescape(text)
    text = _HSPACE_RE.sub(" ", text)
    text = _NEWLINES_RE.sub("\n\n", text)
    lines = [line.strip() for line in text.splitlines()]
    compact = [line for line in lines if line]
    return "\n".join(compact)
