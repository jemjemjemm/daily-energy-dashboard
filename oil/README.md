# F-Issue Report

`유가담합` 관련 뉴스를 네이버뉴스·다음뉴스·구글뉴스에서 매일 두 차례 전수 검색하고, 동일 제목과 동일 언론사인 결과만 합쳐 A/B/C 매체 등급별로 보여주는 정적 뉴스 모니터링 대시보드입니다.

- GitHub Pages: https://jemjemjemm.github.io/daily-energy-dashboard/oil/
- 기준 시간대: `Asia/Seoul`
- 메인 화면: 저장소 루트의 `index.html`

## 검색 범위

모든 포털에서 다음 13개 검색어를 각각 조회합니다.

`유가담합`, `유가 담합`, `정유사 담합`, `기름값 담합`, `석유 담합`, `휘발유 담합`, `경유 담합`, `주유소 담합`, `정유업계 담합`, `석유제품 담합`, `유류가격 담합`, `공정위 유가 담합`, `공정거래위원회 정유사 담합`

네이버 API 자격정보가 있으면 공식 검색 API를 우선 사용하고, 없으면 공개 뉴스 검색을 사용합니다. 다음은 공개 뉴스 검색, 구글은 Google News RSS를 사용합니다. 모든 원본 검색 결과는 `data/raw/`에 보관됩니다. 개별 포털·검색어 수집 실패는 숨기지 않고 구조화된 `collection_warnings`에 기록합니다.

## 실행 시간과 시간 범위

GitHub Actions cron은 주말을 포함해 매일 실행됩니다.

- Morning: 전일 17:00 이상 ~ 기준일 08:00 미만, 08:10 KST 실행 (`23:10 UTC`)
- Evening: 기준일 08:00 이상 ~ 17:00 미만, 17:10 KST 실행 (`08:10 UTC`)

발행시각이 없는 검색 결과는 버리지 않고 `검토필요`로 유지합니다. 발행시각이 확인되며 해당 반개구간 밖인 기사만 현재 리포트에서 제외합니다.

수동 실행:

```bash
pip install -r requirements.txt
python scripts/collect_news.py --slot morning --base-date 2026-06-19 --force-refresh true
python scripts/build_report.py --slot morning --base-date 2026-06-19
python -m unittest discover -s tests -v
```

통합 저장소 Actions 탭의 **F-Issue Report → Run workflow**에서도 `report_slot`, `base_date`, `force_refresh`를 지정할 수 있습니다. 예약 실행은 KST 현재 시각으로 slot과 기준일을 자동 결정합니다.

## 데이터와 중복 기준

```text
data/raw/YYYY-MM-DD-SLOT-raw.json       포털 검색 원본
data/reports/YYYY-MM-DD-SLOT.json       정제된 전체 기사 리포트
data/report-index.json                  Calendar 및 최신 리포트 색인
reports/YYYY-MM-DD-SLOT.html            해당 리포트 진입 링크
```

비교용 제목에서 공백과 `[속보]`, `[단독]`, `(종합)`, `[그래픽]`, `[포토]` 등을 정리한 뒤 `정규화 언론사::정규화 제목`이 같을 때만 하나로 합칩니다. 포털이 달라도 이 두 값이 같으면 `portals`와 `queries`를 합치며, 같은 제목이라도 언론사가 다르면 별개 기사로 유지합니다. 원문 URL을 확인할 수 있으면 포털 URL보다 우선합니다.

## 매체 등급과 품질 상태

- A: 연합뉴스, 한국경제, 매일경제, 서울경제, 이데일리, 머니투데이, 아시아경제, 파이낸셜뉴스, 중앙일보, 조선일보, 동아일보, 한겨레, 경향신문, 한국일보, 뉴스1, 뉴시스
- B: 국민일보, 문화일보, 세계일보, 헤럴드경제, 이투데이, 아시아투데이, 전자신문, 비즈워치, 조세일보, 데일리안, 한스경제, 더구루, 신아일보, 국제신문, 에너지경제, 매일일보, SBS, KBS, MBC, YTN, JTBC, MBN, 채널A, TV조선
- C: 위 목록에 없는 모든 매체. C등급도 누락하지 않습니다.

모든 항목은 언론사별 목록 안에 함께 표시됩니다.

- `정상`: 유가·석유 맥락과 담합·공정위 맥락이 명확함
- `검토필요`: 관련성이 애매하거나 발행시각·언론사·링크 중 일부가 불완전함
- `제외`: 인사·부고·일정·스포츠·연예·생활정보·광고·비관련 담합 등 명백히 비관련/저품질임. 화면에서 숨기지는 않음

## Calendar와 0건 리포트

화면 맨 아래 Calendar는 `data/report-index.json`을 읽습니다. 리포트가 있는 날짜에는 M(Morning), E(Evening), 기사 수가 표시됩니다. 날짜를 누른 뒤 slot 버튼을 선택하면 상단 요약과 언론사별 전체 목록이 해당 과거 리포트로 교체됩니다. 이전 달·다음 달·이번 달 이동을 지원합니다.

검색 결과가 0건이어도 JSON, HTML, 색인을 모두 생성하므로 Calendar에서 조회할 수 있습니다. 0건과 수집 경고가 함께 있으면 누락 가능성을 Telegram으로 알립니다.

## Telegram과 GitHub Secrets

수집 경고 또는 파이프라인/Pages 배포 실패 시 쉬운 한국어 설명을 보냅니다. 성공 알림은 저장소 Variable `TELEGRAM_NOTIFY_ON_SUCCESS=true`일 때만 보냅니다.

- 알림에 필요: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- 선택 API: `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `SERPAPI_KEY`, `GOOGLE_CSE_KEY`, `GOOGLE_CSE_ID`

Telegram 자격정보가 없으면 알림만 건너뛰며 리포트 생성은 계속됩니다. API 관련 값이 없어도 공개 검색/RSS fallback으로 수집합니다.

## GitHub Pages 배포

통합 저장소의 공통 Pages workflow가 `oil/index.html`, `oil/assets/`, 정제된 `oil/data/reports/`, `oil/reports/`를 하나의 사이트에 포함합니다. 수집 원본 `oil/data/raw/`와 실행 코드는 공개 artifact에 포함하지 않습니다.
