from __future__ import annotations

from urllib.parse import urlparse


def pr_number(selector: str) -> str | None:
    if selector.startswith("#") and selector[1:].isdigit():
        return selector[1:]

    parsed = urlparse(selector)
    if parsed.scheme not in {"http", "https"}:
        return None

    parts = [part for part in parsed.path.split("/") if part]
    for marker in ("pull", "pulls", "merge_requests"):
        if marker in parts:
            index = parts.index(marker) + 1
            if index < len(parts) and parts[index].isdigit():
                return parts[index]
    return None


def is_pr_selector(selector: str) -> bool:
    return pr_number(selector) is not None
