import unittest
from unittest.mock import patch

from scripts.article_content import extract_article_body
from scripts.apply_news_to_report import build_news_summary, extractive_article_summary
from scripts.llm_article_summary import _build_user_prompt, enrich_article_summaries


class ArticleContentTest(unittest.TestCase):
    def test_byline_removal_preserves_the_opening_article_sentence(self) -> None:
        html = """
        <html><body><div class="article_view">
        (서울=뉴스1) 김지완 기자 = 이란 지원을 받는 예멘 후티 반군이 봉쇄를 선언하자,
        아시아 정유사들이 수에즈 운하 우회 운송을 모색하고 있다.
        이 문장은 본문 길이 기준을 충족하기 위한 기사 세부 내용이다.
        이 문장은 본문 길이 기준을 충족하기 위한 추가 설명이다.
        </div></body></html>
        """

        body = extract_article_body(html)

        self.assertNotIn("김지완 기자", body)
        self.assertIn("이란 지원을 받는 예멘 후티 반군이 봉쇄를 선언하자", body)
        self.assertTrue(body.startswith("이란 지원을 받는 예멘 후티 반군이"))

    def test_extracts_article_body_instead_of_navigation(self) -> None:
        html = """
        <html><body><nav>메뉴 메뉴 메뉴</nav><div class="article_view">
        국제유가는 공급 차질 우려로 배럴당 90달러를 넘어섰다.
        정유업계는 원유 도입 비용과 재고 평가 영향을 점검하고 있다.
        정부는 국내 수급에는 당장 문제가 없다고 설명했다.
        이 문장은 본문 길이 기준을 충족하기 위한 기사 세부 내용이다.
        이 문장은 본문 길이 기준을 충족하기 위한 추가 설명이다.
        </div><footer>회사 소개</footer></body></html>
        """
        body = extract_article_body(html)
        self.assertIn("배럴당 90달러", body)
        self.assertNotIn("메뉴 메뉴", body)

    def test_extractive_fallback_uses_article_fact_not_generic_theme(self) -> None:
        article = {
            "title": "러시아 경유 수출금지에 K정유 공급 확대 기대",
            "press": "연합뉴스",
            "article_body": (
                "러시아가 경유 수출을 전면 금지하면서 국제 제품 마진이 상승했다. "
                "세계 5위 정제능력을 보유한 국내 정유사는 수출 확대 기회를 얻었지만 원유 확보와 국내 수급 안정도 병행해야 한다."
            ),
        }
        summary = extractive_article_summary(article)
        self.assertIn("전면 금지", summary)
        self.assertIn("마진", summary)
        self.assertNotIn("공급망 재편과 수익성 부담", summary)

    def test_hyphenated_company_name_is_not_treated_as_press_suffix(self) -> None:
        summary = build_news_summary({}, [{
            "title": "정유 구조적 강세기에 S-Oil 목표주가 상향",
            "press": "한국경제TV",
            "summary": "탈탄소 투자 축소와 지정학 위험 누적으로 정유 업황이 강세기에 진입했다는 분석에 S-Oil 목표주가 상향",
        }])
        self.assertIn("S-Oil 목표주가 상향", summary)

    def test_prompt_prefers_original_body_over_search_snippet(self) -> None:
        articles = [{
            "title": "국제유가 90달러 돌파",
            "press": "테스트경제",
            "snippet": "짧은 검색 문구",
            "article_body": "공급 차질 우려로 브렌트유가 배럴당 90달러를 넘어섰다.",
        }]
        prompt = _build_user_prompt(articles, "morning", "2026-07-21")
        self.assertIn("기사 원문 본문", prompt)
        self.assertIn("브렌트유가", prompt)
        self.assertNotIn("보조 자료(검색 스니펫)", prompt)

    @patch("scripts.llm_article_summary._call_claude")
    @patch("scripts.llm_article_summary.hydrate_article_bodies")
    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    def test_enrichment_hydrates_bodies_before_calling_model(self, hydrate, call) -> None:
        def add_body(articles, timeout):
            articles[0]["article_body"] = "정부가 최고가격제를 150원 인하하고 손실보전 기준을 검토한다. " * 5
            return 1

        hydrate.side_effect = add_body
        call.return_value = '{"summaries":["최고가격제 150원 인하 뒤 손실보전 기준 검토가 핵심 쟁점"]}'
        articles = [{"title": "최고가격제 150원 인하", "press": "연합뉴스", "url": "https://example.test/a"}]
        result = enrich_article_summaries(articles, "morning", "2026-07-21")
        self.assertEqual(result[0], "최고가격제 150원 인하 뒤 손실보전 기준 검토가 핵심 쟁점")
        hydrate.assert_called_once()
        self.assertIn("기사 원문 본문", call.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
