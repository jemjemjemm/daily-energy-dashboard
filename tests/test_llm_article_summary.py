import unittest
from unittest.mock import patch

from scripts.article_content import extract_article_body
from scripts.llm_article_summary import _build_user_prompt, enrich_article_summaries


class ArticleContentTest(unittest.TestCase):
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
