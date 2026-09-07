"""Media-name normalization and exact-match A/B/C classification."""
from __future__ import annotations

import re


GRADE_A_ORDER = (
    # 종합지
    "조선일보", "중앙일보", "동아일보", "한국일보", "한겨레", "경향신문",
    "국민일보", "서울신문", "세계일보", "문화일보", "내일신문",

    # 경제지
    "매일경제", "한국경제", "서울경제", "머니투데이", "이데일리",
    "파이낸셜뉴스", "헤럴드경제", "아시아경제", "전자신문", "디지털타임스",

    # 통신사
    "연합뉴스", "뉴시스", "뉴스1",
)

GRADE_B_ORDER = (
    # 통신사 및 기타 지면
    "뉴스핌", "아시아투데이", "아주경제", "이투데이", "뉴스토마토",

    # 방송사
    "KBS", "MBC", "SBS", "JTBC", "채널A", "TV조선", "MBN",

    # IB매체
    "더벨", "인베스트조선", "연합인포맥스",

    # 언론 온라인 중 B 인정 매체
    "조선Biz", "EBN", "뉴데일리", "데일리안",

    # 케이블 중 B 인정 매체
    "YTN", "연합뉴스TV",
)

GRADE_A = set(GRADE_A_ORDER)
GRADE_B = set(GRADE_B_ORDER)

ALIASES = {
    "매경": "매일경제",
    "매경닷컴": "매일경제",
    "한경": "한국경제",
    "한국경제신문": "한국경제",
    "서울경제신문": "서울경제",
    "헤럴드 경제": "헤럴드경제",
    "파이낸셜 뉴스": "파이낸셜뉴스",
    "아시아 경제": "아시아경제",
    "디지털 타임스": "디지털타임스",

    "연합": "연합뉴스",
    "연합 뉴스": "연합뉴스",
    "연합뉴스 tv": "연합뉴스TV",
    "연합뉴스TV": "연합뉴스TV",
    "ytn": "YTN",
    "YTN": "YTN",

    "news1": "뉴스1",
    "News1": "뉴스1",
    "뉴스 1": "뉴스1",

    "조선비즈": "조선Biz",
    "조선 Biz": "조선Biz",
    "조선Biz": "조선Biz",
    "chosunbiz": "조선Biz",
    "ChosunBiz": "조선Biz",

    "이비엔": "EBN",
    "ebn": "EBN",
    "EBN": "EBN",

    "채널 a": "채널A",
    "채널A": "채널A",
    "tv조선": "TV조선",
    "TV조선": "TV조선",
}


def normalize_media_name(source: str) -> str:
    """Normalize a media name without performing partial-string matching."""
    value = re.sub(r"\s+", " ", (source or "").strip())
    value = re.sub(
        r"\s*[|·\-]\s*(네이버뉴스|다음뉴스|Google News)$",
        "",
        value,
        flags=re.I,
    ).strip()
    if not value:
        return "매체 미상"

    folded = value.casefold()
    for alias, canonical in ALIASES.items():
        if folded == alias.casefold():
            return canonical
    return value


def normalize_source(source: str) -> str:
    """Backward-compatible name used by the collection/report pipeline."""
    return normalize_media_name(source)


def get_media_grade(source: str) -> str:
    normalized = normalize_media_name(source)
    if normalized in GRADE_A:
        return "A"
    if normalized in GRADE_B:
        return "B"
    return "C"


def media_sort_index(source: str, grade: str | None = None) -> int:
    normalized = normalize_media_name(source)
    resolved_grade = grade or get_media_grade(normalized)
    values = GRADE_A_ORDER if resolved_grade == "A" else GRADE_B_ORDER if resolved_grade == "B" else ()
    try:
        return values.index(normalized)
    except ValueError:
        return len(values)
