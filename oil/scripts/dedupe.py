"""Deduplicate only identical normalized title + identical normalized source."""
from __future__ import annotations

import re
from urllib.parse import parse_qs, unquote, urlparse

from media_grade import normalize_source

DECORATION = re.compile(
    r"^\s*(?:\[(?:속보|단독|그래픽|포토|사진)\]|\((?:종합|종합\d*보)\))\s*|"
    r"\s*(?:\[(?:속보|단독|그래픽|포토|사진)\]|\((?:종합|종합\d*보)\))\s*$"
)


def normalize_title(title: str) -> str:
    value = re.sub(r"\s+", " ", (title or "").strip())
    previous = None
    while value != previous:
        previous = value
        value = DECORATION.sub("", value).strip()
    return value


def canonicalize_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    for key in ("url", "u", "target", "redirect"):
        candidate = query.get(key, [""])[0]
        if candidate.startswith("http"):
            return unquote(candidate)
    return url


def _prefer_url(current: str, candidate: str) -> str:
    portal_hosts = ("news.naver.com", "search.naver.com", "v.daum.net", "news.daum.net", "news.google.com")
    current_host = urlparse(current).netloc
    candidate_host = urlparse(candidate).netloc
    if current_host.endswith(portal_hosts) and candidate_host and not candidate_host.endswith(portal_hosts):
        return candidate
    return current or candidate


def deduplicate(items: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for original in items:
        item = dict(original)
        normalized = normalize_title(item.get("title", ""))
        source = normalize_source(item.get("source", ""))
        key = f"{source.casefold()}::{normalized.casefold()}"
        item.update(normalized_title=normalized, source_normalized=source, duplicate_key=key)
        item["portals"] = sorted(set(item.get("portals") or [item.get("portal")]), key=lambda x: ["naver", "daum", "google"].index(x) if x in ["naver", "daum", "google"] else 9)
        item["queries"] = sorted(set(item.get("queries") or [item.get("query", "")]) - {""})
        item["duplicate_count"] = 0
        item["canonical_url"] = canonicalize_url(item.get("canonical_url") or item.get("url", ""))
        if key not in merged:
            merged[key] = item
            continue
        target = merged[key]
        target["duplicate_count"] += 1
        target["portals"] = sorted(set(target["portals"] + item["portals"]), key=lambda x: ["naver", "daum", "google"].index(x) if x in ["naver", "daum", "google"] else 9)
        target["queries"] = sorted(set(target["queries"] + item["queries"]))
        target["canonical_url"] = _prefer_url(target.get("canonical_url", ""), item.get("canonical_url", ""))
        target["url"] = target["canonical_url"] or target.get("url") or item.get("url", "")
        if not target.get("published_at") and item.get("published_at"):
            target["published_at"] = item["published_at"]
        if len(item.get("snippet", "")) > len(target.get("snippet", "")):
            target["snippet"] = item["snippet"]
    return list(merged.values())
