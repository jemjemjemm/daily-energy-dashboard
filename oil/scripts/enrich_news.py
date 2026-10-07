"""Confirm publisher, full title and publication time without collapsing a story's coverage."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup
from dateutil import parser

from collect_news import HEADERS, TIMEOUT, clean_text
from media_grade import normalize_source
from utils_time import KST


def parse_article_html(content: bytes | str, url: str, source: str = "") -> dict:
    soup = BeautifulSoup(content, "html.parser")
    meta = {m.get("property") or m.get("name"): m.get("content", "") for m in soup.select("meta[content]")}
    publisher = meta.get("og:site_name", "")
    if publisher.startswith("Daum | "):
        publisher = publisher.split(" | ", 1)[1]
    # A site label such as 'Daum' or 'Google News' is not a publisher.
    if source in {"", "Daum", "새 창 열림", "매체 미확인", "매체 미상"} and publisher not in {"Daum", "Google News", ""}:
        source = publisher
    title = clean_text(meta.get("og:title", ""))
    for suffix in [" | 연합뉴스", " - 머니투데이", " - 파이낸셜뉴스", " - 뉴스1", " - 조선비즈"]:
        title = title.removesuffix(suffix)
    for node in soup.select("script,style,nav,footer,header"):
        node.decompose()
    text = soup.get_text("\n", strip=True)
    # Newsis sometimes puts its modification timestamp in published_time.
    # Labeled initial registration/input time takes precedence over that metadata.
    labeled = re.search(r"(?:등록|입력|기사입력|송고)[\s:：]*((?:20\d{2})[.\-/]\s*\d{1,2}[.\-/]\s*\d{1,2}\.?\s+(?:오전|오후)?\s*\d{1,2}:\d{2}(?::\d{2})?)", text)
    raw_time = labeled.group(1) if labeled else meta.get("article:published_time") or meta.get("og:published_time")
    basis = "원문 최초 등록·입력" if labeled else "원문 published_time"
    if not raw_time:
        portal = soup.select_one(".info_view .num_date")
        raw_time = portal.get_text(" ", strip=True) if portal else ""
        basis = "포털 본문 최초 입력"
    timestamp = ""
    if raw_time:
        value = re.sub(r"[.]\s*", "-", raw_time.strip()).replace("오전", "AM").replace("오후", "PM") if not re.search(r"T\d", raw_time) else raw_time
        value = re.sub(r"(\d)-(?=\s)", r"\1", value)
        try:
            dt = parser.parse(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=KST)
            timestamp = dt.astimezone(KST).isoformat()
        except (ValueError, TypeError, OverflowError):
            pass
    body_nodes = soup.select("article, .article_view, .article-body, #articleBody, #newsEndContents, .newsct_article, #articeBody, #textBody, #article-view-content-div, #news_body_area, #dic_area, .article_txt")
    body = max((node.get_text(" ", strip=True) for node in body_nodes), key=len, default=text)
    has_body = len(body) > 500 and len(re.findall(r"담합|심사보고서|가격정보", body)) >= 3 and (bool(body_nodes) or len(re.findall(r"(?m)^.{80,}$", text)) >= 3)
    is_portal = urlsplit(url).hostname in {"v.daum.net", "news.daum.net", "n.news.naver.com", "news.naver.com", "news.google.com"}
    return dict(title=title, source=normalize_source(source), published_at=timestamp,
                verified=bool(timestamp and has_body and not is_portal),
                published_at_basis="portal_article" if is_portal else "original_article",
                time_evidence=f"{basis} {raw_time}" if timestamp else "원문 최초시각 확인 실패",
                body_available=has_body)


def enrich_article(item: dict) -> dict:
    result = dict(item)
    url = item.get("canonical_url") or item.get("url", "")
    if "news.google.com/" in url:
        result.update(verified=False, published_at_basis="search_result", verification_reason="Google RSS 검색시각·문맥 확인. 발행사 원문 미확인.")
        result['source'] = normalize_source(item.get('source', '')) if item.get('source') != 'Daum' else '매체 미확인'
        return result
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        evidence = parse_article_html(response.content, response.url, item.get("source", ""))
        if evidence["title"]:
            result["title"] = evidence["title"]
        result["source"] = evidence["source"]
        if evidence["published_at"]:
            result.update(published_at=evidence["published_at"], published_at_basis=evidence["published_at_basis"], time_evidence=evidence["time_evidence"])
        result["verified"] = evidence["verified"]
        result["verification_reason"] = "발행사 본문·최초시각 확인" if evidence["verified"] else ("포털 본문·시각 확인, 발행사 원문 미확인" if evidence["published_at_basis"] == "portal_article" and evidence["body_available"] else "원문 본문 또는 최초시각 미확인")
    except (requests.RequestException, ValueError) as exc:
        result.update(verified=False, verification_reason=f"원문 확인 실패: {type(exc).__name__}")
    return result
