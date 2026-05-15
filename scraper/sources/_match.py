from __future__ import annotations


def title_matches(title: str, needles: list[str] | None) -> bool:
    if not needles:
        return True
    t = (title or "").lower()
    return any(n.lower() in t for n in needles)


def keyword_matches(text: str, needles: list[str] | None) -> bool:
    if not needles:
        return True
    body = (text or "").lower()
    return any(n.lower() in body for n in needles)
