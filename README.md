# Daily / 유가 통합 리포트

통합 전환은 2026-09-07에 완료되었습니다. 앞으로 Daily와 유가 리포트의 데이터 생성, 화면 조립, GitHub Pages 배포는 모두 이 저장소에서 운영합니다.

## 운영 주소

- Daily: <https://jemjemjemm.github.io/daily-energy-dashboard/>
- 유가: <https://jemjemjemm.github.io/daily-energy-dashboard/oil/>
- 두 화면 상단의 `Daily` / `유가` 탭으로 이동합니다.
- 이전 F_Issue 주소는 위 유가 주소로 리다이렉트됩니다.

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
