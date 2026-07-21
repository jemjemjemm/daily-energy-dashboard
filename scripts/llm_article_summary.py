#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""대표 기사 요약을 Claude API로 보강합니다.

목적
- 기존 apply_news_to_report.py의 규칙 기반(specific_article_summary /
  fallback_article_summary) 요약은 키워드 매칭 캐스케이드라서, 매칭되는
  규칙이 없으면 범용 캐치올 문구("... 정책·시장 동향으로 부각")로 떨어지고,
  서로 다른 기사가 동일한 문구로 중복되는 문제가 있었습니다.
- 이 모듈은 선정된 대표 기사(보통 3건)에 대해 실제 기사 제목/스니펫을 근거로
  서로 연결되고 구체적인 절형 요약을 Claude API로 생성합니다.
- 실패(키 없음/네트워크 오류/응답 파싱 실패 등) 시 항상 None을 반환하여,
  호출부(apply_news_to_report.py)가 기존 규칙 기반 요약으로 자연스럽게
  폴백하도록 설계되어 있습니다. 이 모듈 자체가 pipeline을 실패시키지 않습니다.

주의
- 이 모듈은 apply_news_to_report.py를 import하지 않습니다(순환 참조 방지).
  반환된 문장의 최종 품질 검증(제목과의 일치 여부, 범용 문구 여부 등)은
  호출부에서 기존 검증 함수로 수행합니다.
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

try:
    from scripts.article_content import hydrate_article_bodies
except ImportError:
    from article_content import hydrate_article_bodies  # type: ignore

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_TIMEOUT_SECONDS = 25
MAX_SNIPPET_CHARS = 700
MAX_BODY_CHARS = 4200

SYSTEM_PROMPT = """당신은 정유·석유화학·LNG 업계를 담당하는 국내 에너지 산업 애널리스트입니다.
수집된 기사 원문을 읽고, 각 기사에 대해 한국어 절형 요약을 작성하세요.

작성 원칙:
1. 제공된 제목/언론사/기사 본문에 명시된 사실만 근거로 삼습니다. 없는 사실을 만들거나 추정하지 않습니다.
2. 제목을 바꿔 쓰는 데 그치지 말고 기사 본문의 핵심 사실, 수치, 원인과 결과를 우선 요약합니다. 기사에 없는 업계 영향이나 의미를 임의로 덧붙이지 않습니다.
3. 여러 기사가 같은 사건(예: 같은 지정학적 이슈)을 다루더라도, 절마다 다른 측면(배경/쟁점/파급 효과 등)을 부각시켜 서로 겹치지 않게 씁니다.
4. 완결문 종결어미(~다/~습니다)를 쓰지 말고, 주어·서술 관계가 있는 절을 명사형 종결(~함/~됨/~임)로 마무리하세요.
5. 근거가 빈약하거나 기사 수가 적으면 과장하지 말고 담백하게 씁니다.
6. 문체는 절형 개조식(명사형 종결, 마침표 없이)으로, 40~65자 내외로 씁니다. 단순 명사 나열만으로 끝내지 않습니다.
7. 반드시 JSON만 출력하세요. 다른 설명 문장을 절대 덧붙이지 마세요.

출력 형식(JSON):
{"summaries": ["기사1 요약", "기사2 요약", ...]}
입력된 기사 개수와 summaries 배열 길이가 반드시 같아야 합니다.
"""

FEWSHOT_EXAMPLE = """예시 (참고용 스타일, 실제 내용은 아래 입력 기사로만 작성):
입력 기사 3건이 모두 호르무즈 관련이어도 아래처럼 서로 다른 측면으로 씁니다.
- "호르무즈 피격·미 공습으로 유가가 반등해 최고가격제 종료 시점과 가격 통제 해제 판단이 어려워짐"
- "정유사 손실보전 청구가 담합 수사와 맞물리며 MOPS 기준 보상 범위를 둘러싼 논쟁으로 확대"
- "호르무즈 선박 피격 이후 브렌트유가 74달러대로 뛰며 국내 석유제품 가격 전이 가능성 주시"
"""


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _build_user_prompt(articles: List[Dict[str, Any]], report_slot: str, date_text: str) -> str:
    slot_label = "조간(오전)" if report_slot == "morning" else "석간(오후)"
    lines = [f"기준일: {date_text} / 시간대: {slot_label}", FEWSHOT_EXAMPLE, "입력 기사 목록:"]
    for idx, article in enumerate(articles, start=1):
        title = _clean(article.get("title"))
        press = _clean(article.get("press"))
        body = _clean(article.get("article_body"))
        snippet = _clean(article.get("snippet") or article.get("summary"))
        if len(snippet) > MAX_SNIPPET_CHARS:
            snippet = snippet[:MAX_SNIPPET_CHARS].rsplit(" ", 1)[0].strip() + "..."
        if len(body) > MAX_BODY_CHARS:
            body = body[:MAX_BODY_CHARS].rsplit(" ", 1)[0].strip() + "..."
        if body:
            lines.append(f"{idx}. [{press}] {title}\n   기사 원문 본문: {body}")
        else:
            lines.append(f"{idx}. [{press}] {title}\n   본문 수집 실패 시 보조 자료(검색 스니펫): {snippet}")
    lines.append(f"\n위 {len(articles)}건 각각에 대해 JSON으로만 응답하세요.")
    return "\n".join(lines)


def _extract_json_block(text: str) -> Optional[dict]:
    text = text.strip()
    # 코드펜스 제거
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return None


def _call_claude(system: str, user: str, model: str, api_key: str, timeout: float, max_tokens: int = 800) -> Optional[str]:
    try:
        import requests
    except ImportError:
        return None
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    try:
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=timeout)
    except Exception as exc:
        print(f"[WARN] Claude summary request failed: {type(exc).__name__}", file=sys.stderr)
        return None
    if resp.status_code != 200:
        try:
            error_payload = resp.json()
            error_type = error_payload.get("error", {}).get("type", "unknown_error")
            error_message = re.sub(
                r"sk-ant-[A-Za-z0-9_-]+",
                "[redacted]",
                str(error_payload.get("error", {}).get("message", "")),
            )[:300]
        except Exception:
            error_type = "unparseable_error"
            error_message = ""
        print(
            f"[WARN] Claude summary API returned HTTP {resp.status_code}: {error_type} "
            f"(model={model}) {error_message}",
            file=sys.stderr,
        )
        return None
    try:
        data = resp.json()
        parts = data.get("content") or []
        text = "".join(p.get("text", "") for p in parts if isinstance(p, dict) and p.get("type") == "text")
        return text or None
    except Exception as exc:
        print(f"[WARN] Claude summary response parse failed: {type(exc).__name__}", file=sys.stderr)
        return None


def enrich_article_summaries(
    articles: List[Dict[str, Any]],
    report_slot: str = "morning",
    date_text: str = "",
) -> List[Optional[str]]:
    """선정된 대표 기사 각각에 대한 LLM 생성 요약 후보를 반환합니다.

    반환값은 articles와 같은 길이/순서의 리스트이며, 각 원소는 생성된 문장
    문자열이거나(성공) None(실패 - 호출부가 기존 규칙 기반 요약을 그대로 사용해야 함)
    입니다. 이 함수는 예외를 외부로 던지지 않습니다.
    """
    empty_result = [None] * len(articles)
    if not articles:
        return []

    try:
        article_timeout = float(os.environ.get("ARTICLE_FETCH_TIMEOUT", "10"))
    except ValueError:
        article_timeout = 10.0
    hydrate_article_bodies(articles, timeout=article_timeout)

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return empty_result

    model = os.environ.get("CLAUDE_SUMMARY_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    try:
        timeout = float(os.environ.get("CLAUDE_SUMMARY_TIMEOUT", DEFAULT_TIMEOUT_SECONDS))
    except ValueError:
        timeout = DEFAULT_TIMEOUT_SECONDS

    try:
        user_prompt = _build_user_prompt(articles, report_slot, date_text)
        text = _call_claude(SYSTEM_PROMPT, user_prompt, model, api_key, timeout)
        if not text:
            return empty_result
        parsed = _extract_json_block(text)
        if not isinstance(parsed, dict):
            return empty_result
        summaries = parsed.get("summaries")
        if not isinstance(summaries, list) or len(summaries) != len(articles):
            return empty_result

        cleaned = [_clean(s) for s in summaries]
        # 배치 내 완전 중복 문장은 신뢰할 수 없는 응답으로 간주하고 해당 항목만 폐기합니다.
        seen: dict[str, int] = {}
        for item in cleaned:
            key = item.lower()
            if key:
                seen[key] = seen.get(key, 0) + 1
        result: List[Optional[str]] = []
        for item in cleaned:
            key = item.lower()
            if not item or seen.get(key, 0) > 1:
                result.append(None)
            else:
                result.append(item)
        return result
    except Exception:
        return empty_result
