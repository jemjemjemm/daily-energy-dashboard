#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch and extract the readable body of a news article.

The dashboard must summarize the article itself, not a search-result card.  This
module intentionally keeps extraction small and dependency-light so it can run
unchanged in GitHub Actions (requests + BeautifulSoup).
"""
from __future__ import annotations

import json
import re
from html import unescape
from typing import Any, Dict, Iterable


USER_AGENT = "Mozilla/5.0 (compatible; DailyEnergyDashboard/1.0; +https://github.com/jemjemjemm/daily-energy-dashboard)"
DEFAULT_TIMEOUT_SECONDS = 10.0
MAX_BODY_CHARS = 6000
MIN_BODY_CHARS = 120

ARTICLE_SELECTORS = (
    "div.article_view",
    "#harmonyContainer",
    "#dic_area",
    "#newsct_article",
    "article",
    ".article-body",
    ".article_body",
    ".news_body",
    ".news_view",
)

BOILERPLATE_PATTERNS = (
    r"무단전재[^\n]{0,80}",
    r"재배포[^\n]{0,80}",
    r"기자\s*=?\s*[^\n]{0,40}",
    r"제보는\s*카카오톡[^\n]{0,100}",
    r"공유하기",
)


def clean_text(value: Any) -> str:
    text = unescape("" if value is None else str(value))
    text = re.sub(r"[\u200b-\u200f\u2060\ufeff]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    for pattern in BOILERPLATE_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()


def _json_ld_bodies(soup: Any) -> Iterable[str]:
    for node in soup.select('script[type="application/ld+json"]'):
        raw = node.string or node.get_text(" ", strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        stack = payload if isinstance(payload, list) else [payload]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                body = clean_text(item.get("articleBody"))
                if body:
                    yield body
                stack.extend(v for v in item.values() if isinstance(v, (dict, list)))
            elif isinstance(item, list):
                stack.extend(item)


def extract_article_body(html: str | bytes, max_chars: int = MAX_BODY_CHARS) -> str:
    """Return the most likely article body from HTML, or an empty string."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for node in soup.select("script, style, noscript, iframe, svg, figure, figcaption, .ad, .advertisement"):
        node.decompose()

    candidates = list(_json_ld_bodies(soup))
    for selector in ARTICLE_SELECTORS:
        for node in soup.select(selector):
            candidates.append(clean_text(node.get_text(" ", strip=True)))
    for selector in ('meta[property="og:description"]', 'meta[name="description"]'):
        for node in soup.select(selector):
            candidates.append(clean_text(node.get("content")))

    candidates = [text for text in candidates if len(text) >= MIN_BODY_CHARS]
    if not candidates:
        return ""
    body = max(candidates, key=len)
    return body[:max_chars].rsplit(" ", 1)[0].strip() if len(body) > max_chars else body


def fetch_article_body(url: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> str:
    if not str(url or "").startswith(("http://", "https://")):
        return ""
    try:
        import requests
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.5"},
            timeout=timeout,
        )
        response.raise_for_status()
        return extract_article_body(response.content)
    except Exception:
        return ""


def hydrate_article_bodies(articles: list[Dict[str, Any]], timeout: float = DEFAULT_TIMEOUT_SECONDS) -> int:
    """Attach transient ``article_body`` fields and return the success count."""
    success = 0
    for article in articles:
        existing = clean_text(article.get("article_body"))
        body = existing or fetch_article_body(str(article.get("url") or ""), timeout=timeout)
        if body:
            article["article_body"] = body
            success += 1
    return success
