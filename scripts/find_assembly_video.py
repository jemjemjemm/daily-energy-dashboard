#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
find_assembly_video.py

간단한 헬퍼: 국회(영상회의록) 사이트에서 회의 제목/날짜로 영상 링크를 탐색합니다.

주의
- 이 스크립트는 인터넷 액세스가 필요합니다. 실행 환경에서 외부 접속을 허용해야 동작합니다.
- 영상회의록 시스템의 HTML 구조가 바꿔지면 선택자(selector)를 조정해야 합니다.
- 자동 스크래핑 전에는 사이트 이용약관/robots.txt를 확인하세요.

사용 예:
  python scripts/find_assembly_video.py --title "정무위원회 법안심사제1소위원회" --date 2026-05-12

출력: 발견된 영상 URL 또는 빈 문자열
"""

from __future__ import annotations

import argparse
import re
from typing import Optional

import requests
from bs4 import BeautifulSoup


SEARCH_URL = "https://w3.assembly.go.kr/main/search.do"


def normalize_text(t: str) -> str:
    return re.sub(r"[\s\W_]+", " ", (t or "").strip()).lower()


def search_assembly_for_title(title: str, date: str | None = None) -> Optional[str]:
    """
    assembly 검색 페이지에서 제목/키워드로 결과를 찾고, 영상 회의록 링크가 있는지 확인합니다.
    반환: 영상 링크(URL) 또는 None
    """
    q = title
    params = {"schWord": q, "schMenu": "1", "pageIndex": 1}
    try:
        resp = requests.get(SEARCH_URL, params=params, timeout=10)
        resp.raise_for_status()
    except Exception:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    # 결과 항목을 순회하며 제목/설명에 키워드가 들어가는 항목을 찾는다.
    for a in soup.select("a"):
        txt = a.get_text(" ", strip=True)
        href = a.get("href") or ""
        if not href:
            continue
        if normalize_text(title) in normalize_text(txt):
            # 상대경로일 수 있으므로 절대 URL 변환 필요
            if href.startswith("/"):
                href = "https://w3.assembly.go.kr" + href
            # 영상회의록 페이지는 보통 '/main/view.do' 또는 '/video' 등의 패턴을 가질 수 있음
            if "video" in href or "view.do" in href or "record" in href:
                return href
    # 포괄적 탐색: 페이지 내 iframe 또는 data-src에 영상 링크가 있는지 확인
    for iframe in soup.find_all("iframe"):
        src = iframe.get("src") or ""
        if title.lower() in (src or "").lower() or "assembly" in src:
            return src
    return None


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--title", required=True)
    p.add_argument("--date", default="")
    args = p.parse_args()
    link = search_assembly_for_title(args.title, args.date or None)
    if link:
        print(link)
        return 0
    print("")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
