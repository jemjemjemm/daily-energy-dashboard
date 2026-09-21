# Daily / 국감 통합 리포트

통합 전환은 2026-09-07에 완료되었습니다. 앞으로 Daily와 유가 리포트의 데이터 생성, 화면 조립, GitHub Pages 배포는 모두 이 저장소에서 운영합니다.

## 운영 주소

- Daily: <https://jemjemjemm.github.io/daily-energy-dashboard/>
- 국감: <https://jemjemjemm.github.io/daily-energy-dashboard/assembly/>
- 두 화면 상단의 `Daily` / `국감` 탭으로 이동합니다.
- 유가는 Daily 하단의 `7. Oil Price Issue Report`에서 Morning / Evening / Night 및 과거 기사 캘린더를 조회합니다.
- 기존 `/oil/` 주소와 개별 리포트 링크는 Daily 유가 영역으로 연결됩니다.

2026-09-18부터 배포 조립기가 모든 날짜의 원본 HTML을 Daily(1–6)와 국감(1. 금일 주요 일정)으로 분리합니다. 국감에는 기존 일정 상세, 본회의·상임위 및 월간 국회일정캘린더가 유지됩니다. 수집 파이프라인의 원본 `docs/reports/`는 기존 통합 형식을 유지하며, 실제 공개 화면은 반드시 `python tools/assemble_site.py`로 생성한 `_site/`로 확인합니다. 유가 JSON·색인·개별 진입 HTML은 원본 그대로 복사하며 CSS/JS 충돌을 막기 위해 Daily에 동일한 유가 화면을 iframe으로 포함합니다.

배포 검증: `python -m tools.validate_site` (전체 날짜 분리, 섹션 순서 및 유가 파일의 바이트 단위 보존 확인). GitHub Pages workflow에서도 매번 실행됩니다.

국감 보고서는 `1. 금일 주요 일정`, `2. 주요 이슈`, `3. Monitoring Report`로 구성합니다. 주요 이슈는 선택 날짜별 Morning / Evening과 산자위·기재위·정무위 순서로 표시합니다. 각 상임위에는 우선산업 요약과 전체 뉴스 목록이 있으며 미발간과 수집 기사 없음은 구분합니다. Monitoring Report는 [26GookGam](https://jemjemjemm.github.io/26GookGam/)의 完 탭에서 월별 회의 목록·전체 리포트·조회/복사 기능을 가져옵니다. 기존 일정은 유지합니다.

### 국회 상임위 주요 이슈 발간

`morning` / `모닝 리포트 업데이트`, `evening` / `이브닝 리포트 업데이트` 요청은 [AGENTS.md](AGENTS.md)의 수집·검증·배포 절차를 따릅니다. 날짜 미지정 시 KST 현재 날짜를 사용합니다. Morning은 전일 17:00~당일 08:00, Evening은 당일 08:00~17:00이며 명시한 경계 시각을 포함합니다. 원문 최초 보도시각을 기준으로 선별합니다.

원문 검토 기록은 `data/committee-news/YYYY-MM-DD-SLOT.review.json`, 발간 데이터는 `docs/assembly-content/issues/YYYY-MM-DD-SLOT.json`에 보존합니다. 웹 검색 및 본문 검토가 끝난 입력에만 아래 명령을 실행합니다. 이 도구는 뉴스 검색을 대신하지 않으며, 검증된 후보를 시간대·매체 우선순위·사안 중복·중요도로 선별합니다. 기사 부족 시 무관한 기사를 채우지 않고 확인한 건수만 표시합니다.

Morning과 Evening 모두 **1. 산중위 → 2. 기노위 → 3. 재경위** 순서이며 각 시간대에서 번호를 다시 시작합니다. 상임위별 관심사항은 [AGENTS.md](AGENTS.md#상임위별-관심사항-2026-09-21-사용자-지정)에 기록합니다. 구성 변경 전 보고서의 기노위는 `미수집`으로 표시하고, 정무위 기사는 원래 분류를 유지한 접힌 보존 영역에 남깁니다. 기존 명단에는 기노위가 없으므로 의원 발언 수록 전 소속 근거와 명단 보완이 필요합니다.

```powershell
python -m tools.committee_news --slot morning --date 2026-09-18 --input data/committee-news/2026-09-18-morning.review.json
python tools/sync_assembly_content.py
python tools/assemble_site.py
python -m tools.validate_site
python -m unittest discover -s tests -p test_committee_news.py
```

선택 날짜의 원본 Daily 보고서가 `docs/reports/`와 색인에 있어야 국감에서도 해당 날짜를 선택할 수 있습니다. 과거 날짜는 그 날짜의 주요 이슈를 표시하며 최신 이슈를 과거 날짜에 덮어씌우지 않습니다.

`python tools/sync_assembly_content.py`는 원본을 내려받아 모든 보기 버튼의 본문 존재 여부를 검증한 뒤 `docs/assembly-content/`를 갱신합니다. 원본 체크 시각·해시·회의/리포트 수는 `manifest.json`에 기록합니다. Pages 배포는 Daily 및 유가 morning/evening 생성 workflow 성공 후 실행되며, **매 배포마다** 이 동기화를 먼저 수행합니다. 원본 수집/구조 검증 실패 시 배포를 중단하여 직전 정상 온라인 화면을 보존합니다. 과거 일정 날짜를 선택해도 Monitoring Report는 마지막 배포 시 확인한 최신 完 탭을 표시합니다. 수동 검증: `python -m unittest discover -s tests -p test_sync_assembly_content.py`.

## 저장소 구조

```text
data/reports/                  Daily 원본 리포트 JSON
docs/                          Daily 공개 화면과 HTML 리포트
oil/data/reports/              유가 리포트 JSON
oil/reports/                   유가 개별 리포트 진입 HTML
oil/assets/                    유가 화면 CSS와 JavaScript
shared/                        두 화면이 함께 쓰는 탭 스타일
public/report-index.json       Daily 색인의 호환성 미러
tools/assemble_site.py         docs와 oil을 _site에 조립
.github/workflows/             수집·색인·배포 자동화
```

`public/`은 배포 원본이 아닙니다. 중복 HTML·일정·자산은 유지하지 않으며 `docs/`가 Daily 공개 파일의 기준입니다. `_site/`는 Actions 실행 중 생성되는 배포 결과물입니다.

## 자동 운영

- `.github/workflows/fetch_safetimes_schedule.yml`: Daily 데이터와 HTML 생성
- `.github/workflows/oil-report.yml`: 유가 데이터와 리포트 생성
  - Morning: 매일 08:10 KST (`23:10 UTC`)
  - Evening: 매일 17:10 KST (`08:10 UTC`)
- `.github/workflows/deploy-pages.yml`: Daily와 유가 결과를 `_site/`에 조립하고 하나의 Pages artifact로 배포

GitHub Pages Source는 **GitHub Actions**입니다. 수집 workflow가 성공하면 공통 배포 workflow가 최신 `main`을 기준으로 전체 사이트를 다시 배포합니다. 예약 실행은 GitHub 사정에 따라 명목 시각보다 늦게 시작될 수 있습니다.

F_Issue 저장소에는 수집 workflow가 없습니다. 새로운 유가 데이터 생성과 예약 실행은 반드시 이 저장소의 `oil-report.yml`만 사용합니다. 외부 자동화가 과거 `jemjemjemm/F_Issue/.github/workflows/f-issue-report.yml`을 호출했다면 대상은 `jemjemjemm/daily-energy-dashboard/.github/workflows/oil-report.yml`로 변경해야 합니다.

## Daily 색인

`scripts/generate_report_index.py`는 `data/reports/*.report.json` 전체를 기준으로 `docs/report-index.json`을 생성하고 `public/report-index.json`에 동일하게 미러링합니다. 통합 전환 당시 Daily 리포트·날짜·색인은 모두 131개였으며 기존 87개 항목의 라벨과 경로를 보존했습니다.

```bash
python scripts/generate_report_index.py
python tools/assemble_site.py
```

## 저장소 설정

Daily 파이프라인은 `OPINET_API_KEY`, `ASSEMBLY_API_KEY`, 선택 항목인 `ANTHROPIC_API_KEY`를 사용합니다. 유가 파이프라인에는 Naver·Google·SerpAPI 및 Telegram Secrets/Variables가 필요합니다. Secret 값은 Git에 저장하지 않습니다.

## 검증과 롤백

전환 시 `_site/`에서 Daily 131개, 유가 HTML 253개, 유가 JSON 253개와 내부 상대경로를 검증했습니다. 기존 F_Issue 개별 주소는 기간과 slot을 나눈 추가 12개까지 리다이렉트와 렌더링을 확인했습니다.

롤백 기준점, 전환 병합 커밋, 복구 순서는 [ROLLBACK_POINTS_2026-09-07.md](ROLLBACK_POINTS_2026-09-07.md)에 기록합니다.

유가 workflow의 `actor`와 `triggering_actor`는 전환 후 7일간 하루 두 번 관찰하며, 최종 보고 예정일은 **2026-09-14 KST**입니다.
