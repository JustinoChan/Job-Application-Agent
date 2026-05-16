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
    # Unescape FIRST so HTML-encoded HTML (e.g. `&lt;p&gt;Hello&lt;/p&gt;`,
    # which Greenhouse returns for some boards) is decoded into real tags
    # before we strip them. Otherwise the regex finds nothing to strip,
    # `unescape` decodes the entities afterwards, and literal `<p>...`
    # bleeds into the output.
    text = unescape(html)
    text = _BLOCK_BREAK_RE.sub("\n", text)
    text = _TAG_RE.sub("", text)
    text = _HSPACE_RE.sub(" ", text)
    text = _NEWLINES_RE.sub("\n\n", text)
    lines = [line.strip() for line in text.splitlines()]
    compact = [line for line in lines if line]
    return "\n".join(compact)
