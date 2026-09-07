"""Collect every configured query from Naver, Daum and Google News."""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote_plus, urljoin

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from utils_time import KST, get_period, now_kst, resolve_base_date, resolve_slot

ROOT = Path(__file__).resolve().parents[1]
KEYWORDS = [
    "유가담합", "유가 담합", "정유사 담합", "기름값 담합", "석유 담합", "휘발유 담합",
    "경유 담합", "주유소 담합", "정유업계 담합", "석유제품 담합", "유류가격 담합",
    "공정위 유가 담합", "공정거래위원회 정유사 담합",
]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; F-Issue-Report/1.0; +https://jemjemjemm.github.io/F_issue/)"
}
TIMEOUT = 20
RELATIVE_TIME_SOURCE = re.compile(r"^\d+\s*(?:분|시간|일)\s*전$")


def clean_text(value: str) -> str:
    value = html.unescape(value or "")
    if "<" in value and ">" in value:
        value = BeautifulSoup(value, "html.parser").get_text(" ")
    return re.sub(r"\s+", " ", value).strip()


def iso_time(value: str | None) -> str:
    if not value:
        return ""
    relative = re.search(r"(\d+)\s*(분|시간|일)\s*전", value)
    if relative:
        amount = int(relative.group(1))
        delta = {"분": timedelta(minutes=amount), "시간": timedelta(hours=amount), "일": timedelta(days=amount)}[relative.group(2)]
        return (now_kst() - delta).isoformat()
    try:
        parsed = date_parser.parse(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=KST)
        return parsed.astimezone(KST).isoformat()
    except (ValueError, TypeError, OverflowError):
        return ""


def raw_item(portal: str, query: str, title: str, url: str, source: str = "", published_at: str = "", snippet: str = "", raw=None) -> dict:
    return {
        "portal": portal, "query": query, "title": clean_text(title), "url": url,
        "source": clean_text(source), "published_at": iso_time(published_at),
        "snippet": clean_text(snippet), "collected_at": now_kst().isoformat(), "raw": raw or {},
    }


def _source_from_site_name(value: str) -> str:
    site_name = clean_text(value)
    if "|" in site_name:
        site_name = site_name.split("|")[-1].strip()
    return site_name


def _source_needs_enrichment(source: str) -> bool:
    value = clean_text(source)
    return not value or bool(RELATIVE_TIME_SOURCE.fullmatch(value))


def resolve_article_source(url: str) -> str:
    if not url:
        return ""
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        response.raise_for_status()
    except requests.RequestException:
        return ""
    soup = BeautifulSoup(response.text, "html.parser")
    for attrs in (
        {"property": "og:site_name"},
        {"name": "article:media_name"},
        {"name": "twitter:site"},
        {"name": "author"},
    ):
        tag = soup.find("meta", attrs=attrs)
        candidate = _source_from_site_name(tag.get("content", "")) if tag else ""
        if candidate and not _source_needs_enrichment(candidate):
            return candidate
    return ""


def collect_naver_api(query: str) -> list[dict]:
    response = requests.get(
        "https://openapi.naver.com/v1/search/news.json",
        params={"query": query, "display": 100, "sort": "date"},
        headers={**HEADERS, "X-Naver-Client-Id": os.environ["NAVER_CLIENT_ID"], "X-Naver-Client-Secret": os.environ["NAVER_CLIENT_SECRET"]},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return [raw_item("naver", query, row.get("title", ""), row.get("originallink") or row.get("link", ""), published_at=row.get("pubDate", ""), snippet=row.get("description", ""), raw=row) for row in response.json().get("items", [])]


def collect_naver_public(query: str) -> list[dict]:
    response = requests.get("https://search.naver.com/search.naver", params={"where": "news", "query": query, "sort": "1"}, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    results = []
    # Naver frequently rotates generated class names. Semantic heatmap targets
    # are substantially more stable; legacy selectors remain as a fallback.
    title_links = soup.select("a[data-heatmap-target='.tit'], a.news_tit")
    for link in title_links:
        node = link.parent
        for _ in range(6):
            if node is None:
                break
            if node.select_one("a[data-heatmap-target='.prof'], .info.press"):
                break
            node = node.parent
        node = node or link.parent
        if not link or not clean_text(link.get("title") or link.get_text()):
            continue
        source_nodes = node.select("a[data-heatmap-target='.prof'], .info.press, .sds-comps-profile-info-title-text")
        source_text = next((candidate.get_text(" ", strip=True) for candidate in source_nodes if candidate.get_text(" ", strip=True)), "")
        snippet_node = node.select_one("a[data-heatmap-target='.body'], .news_dsc, .api_txt_lines")
        node_text = node.get_text(" ", strip=True)
        date_match = re.search(r"(?:\d+\s*(?:분|시간|일)\s*전|\d{4}\.\d{1,2}\.\d{1,2}\.?)", node_text)
        results.append(raw_item("naver", query, link.get("title") or link.get_text(), link.get("href", ""), source_text, date_match.group(0) if date_match else "", snippet_node.get_text() if snippet_node else ""))
    if not results and not any(marker in soup.get_text(" ", strip=True) for marker in ("검색결과가 없습니다", "검색 결과가 없습니다")):
        raise ValueError("Naver news result selector returned 0 nodes")
    return results


def collect_daum_public(query: str) -> list[dict]:
    response = requests.get("https://search.daum.net/search", params={"w": "news", "q": query, "sort": "recency"}, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    results = []
    selectors = ".c-list-basic > li, .item-bundle-mid, .wrap_cont, .coll_cont li"
    for node in soup.select(selectors):
        link = node.select_one("a.f_link_b, a.tit-g, a[href].tit_main, a[href*='v.daum.net'], a[href*='news.daum.net']")
        if not link:
            continue
        title = clean_text(link.get_text())
        if not title:
            continue
        source_node = node.select_one(".f_nb, .txt_info, .item-source, .cont_info")
        date_node = node.select_one(".f_nb.date, .gem-subinfo, .txt_date")
        snippet_node = node.select_one(".f_eb, .desc, .item-contents")
        article_url = urljoin("https://search.daum.net", link.get("href", ""))
        source_text = source_node.get_text() if source_node else ""
        if _source_needs_enrichment(source_text):
            source_text = resolve_article_source(article_url) or ""
        results.append(raw_item("daum", query, title, article_url, source_text, date_node.get_text() if date_node else "", snippet_node.get_text() if snippet_node else ""))
    if not results and not any(marker in soup.get_text(" ", strip=True) for marker in ("검색결과가 없습니다", "검색 결과가 없습니다")):
        raise ValueError("Daum news result selector returned 0 nodes")
    return results


def collect_google_rss(query: str) -> list[dict]:
    url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=ko&gl=KR&ceid=KR:ko"
    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    feed = feedparser.parse(response.content)
    if getattr(feed, "bozo", False) and not feed.entries:
        raise ValueError(str(feed.bozo_exception))
    results = []
    for entry in feed.entries:
        title = clean_text(entry.get("title", ""))
        source = clean_text(entry.get("source", {}).get("title", ""))
        if source and title.endswith(f" - {source}"):
            title = title[: -(len(source) + 3)].strip()
        results.append(raw_item("google", query, title, entry.get("link", ""), source, entry.get("published", ""), entry.get("summary", ""), dict(entry)))
    return results


def collect_google_serpapi(query: str) -> list[dict]:
    response = requests.get(
        "https://serpapi.com/search.json",
        params={"engine": "google_news", "q": query, "gl": "kr", "hl": "ko", "api_key": os.environ["SERPAPI_KEY"]},
        headers=HEADERS, timeout=TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise ValueError(payload["error"])
    results = []
    for row in payload.get("news_results", []):
        source = row.get("source", {})
        source_name = source.get("name", "") if isinstance(source, dict) else str(source)
        results.append(raw_item("google", query, row.get("title", ""), row.get("link", ""), source_name, row.get("date", ""), row.get("snippet", ""), row))
    return results


def collect_google_cse(query: str) -> list[dict]:
    response = requests.get(
        "https://www.googleapis.com/customsearch/v1",
        params={"key": os.environ["GOOGLE_CSE_KEY"], "cx": os.environ["GOOGLE_CSE_ID"], "q": query, "sort": "date"},
        headers=HEADERS, timeout=TIMEOUT,
    )
    response.raise_for_status()
    results = []
    for row in response.json().get("items", []):
        metatags = (row.get("pagemap", {}).get("metatags") or [{}])[0]
        results.append(raw_item(
            "google", query, row.get("title", ""), row.get("link", ""),
            metatags.get("og:site_name", ""),
            metatags.get("article:published_time") or metatags.get("date") or "",
            row.get("snippet", ""), row,
        ))
    return results


def warning(portal: str, query: str, message: str, detail: str) -> dict:
    names = {"naver": "네이버뉴스", "daum": "다음뉴스", "google": "구글뉴스"}
    return {
        "level": "warning", "portal": portal, "query": query, "message": message,
        "user_message": f"{names[portal]}에서 '{query}' 검색 결과를 읽지 못했습니다. 검색 서비스가 일시적으로 응답하지 않거나 화면 구조가 바뀌었을 수 있습니다.",
        "technical_detail": detail[:1000], "created_at": now_kst().isoformat(),
    }


def collect_all(delay: float = 0.15) -> tuple[list[dict], list[dict], dict]:
    items, warnings = [], []
    counts = {"naver": 0, "daum": 0, "google": 0}
    naver_api = bool(os.getenv("NAVER_CLIENT_ID") and os.getenv("NAVER_CLIENT_SECRET"))
    if os.getenv("SERPAPI_KEY"):
        google_collector = collect_google_serpapi
    elif os.getenv("GOOGLE_CSE_KEY") and os.getenv("GOOGLE_CSE_ID"):
        google_collector = collect_google_cse
    else:
        google_collector = collect_google_rss
    collectors = {
        "naver": collect_naver_api if naver_api else collect_naver_public,
        "daum": collect_daum_public,
        "google": google_collector,
    }
    for query in KEYWORDS:
        for portal, collector in collectors.items():
            try:
                found = collector(query)
                items.extend(found)
                counts[portal] += len(found)
            except Exception as exc:  # continue other queries/portals; expose every failure
                warnings.append(warning(portal, query, f"{portal} collection failed", f"{type(exc).__name__}: {exc}"))
            if delay:
                time.sleep(delay)
    return items, warnings, counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", default="")
    parser.add_argument("--base-date", default="")
    parser.add_argument("--force-refresh", default="false")
    parser.add_argument("--include-previous-night", default="false")
    parser.add_argument("--delay", type=float, default=0.15)
    args = parser.parse_args()
    slot = resolve_slot(args.slot)
    base_date = resolve_base_date(args.base_date)
    targets = [(base_date, slot)]
    if slot == "morning" and args.include_previous_night.lower() == "true":
        targets.append((base_date - timedelta(days=1), "night"))
    paths = [ROOT / "data" / "raw" / f"{day.isoformat()}-{target_slot}-raw.json" for day, target_slot in targets]
    force_refresh = args.force_refresh.lower() == "true"
    if all(path.exists() for path in paths) and not force_refresh:
        print("Raw files already exist: " + ", ".join(str(path.relative_to(ROOT)) for path in paths))
        return 0
    try:
        existing_path = next((path for path in paths if path.exists()), None)
        if existing_path and not force_refresh:
            existing = json.loads(existing_path.read_text(encoding="utf-8"))
            items = existing.get("items", [])
            warnings = existing.get("collection_warnings", [])
            portal_counts = existing.get("portal_counts", {})
            collected_at = existing.get("collected_at") or now_kst().isoformat()
        else:
            items, warnings, portal_counts = collect_all(args.delay)
            collected_at = now_kst().isoformat()
        for (target_date, target_slot), path in zip(targets, paths):
            if path.exists() and not force_refresh:
                continue
            start, end = get_period(target_date, target_slot)
            payload = {
                "base_date": target_date.isoformat(), "slot": target_slot,
                "period_start": start.isoformat(), "period_end": end.isoformat(),
                "collected_at": collected_at, "keywords": KEYWORDS,
                "portal_counts": portal_counts, "collection_warnings": warnings, "items": items,
            }
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Collected {len(items)} raw results with {len(warnings)} warnings -> {path.relative_to(ROOT)}")
        return 0
    except Exception as exc:
        print(f"Collection failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
