# Daily / 유가 통합 리포트

두 리포트를 하나의 GitHub Pages 사이트에서 운영합니다.

- `docs/`: Daily Issue Report의 공개 원본
- `oil/`: Oil Price Issue Report의 수집 코드, 데이터, 공개 화면
- `shared/`: 두 화면이 함께 쓰는 탭 스타일
- `tools/assemble_site.py`: 두 공개 화면을 `_site/`에 모으는 배포 도구

공개 주소는 다음과 같습니다.

- Daily: `https://jemjemjemm.github.io/daily-energy-dashboard/`
- 유가: `https://jemjemjemm.github.io/daily-energy-dashboard/oil/`

## 자동화

- `Daily Energy Dashboard - Daily Data Pipeline`: Daily 데이터와 HTML 생성
- `F-Issue Report`: 매일 08:10, 17:10 KST에 유가 데이터와 리포트 생성
- `Deploy unified reports to GitHub Pages`: 두 결과를 한 Pages artifact로 묶어 배포

수집 workflow가 성공하면 공통 배포 workflow가 최신 `main`을 체크아웃해 전체 사이트를 다시 배포합니다. GitHub Pages의 Source는 **GitHub Actions**로 설정합니다.

## Daily 색인

`scripts/generate_report_index.py`는 `data/reports/*.report.json` 전체를 기준으로 `docs/report-index.json`을 생성합니다. 기존 색인에 있던 항목은 라벨과 경로를 그대로 보존하며, 새로 발견한 데이터 파일의 항목만 대응하는 `docs/reports/*.html`에서 복원합니다. 생성 결과는 호환성 확인을 위해 `public/report-index.json`에도 미러링하지만 Pages에는 `docs/` 쪽 파일만 사용합니다.

```bash
python scripts/generate_report_index.py
python tools/assemble_site.py
```

`public/`에는 색인 미러만 유지합니다. 과거의 HTML·일정·자산 복제본은 `docs/`와 중복되므로 사용하지 않습니다.

## 필요한 저장소 설정

Daily 파이프라인은 기존 `OPINET_API_KEY`, `ASSEMBLY_API_KEY`, 선택 항목인 `ANTHROPIC_API_KEY`를 사용합니다. 유가 파이프라인에는 기존 F_Issue 저장소에서 사용하던 Naver·Google·SerpAPI 및 Telegram Secrets/Variables가 필요합니다. Secret 값은 Git 파일과 함께 이동하지 않으므로 저장소 Settings에서 별도로 등록합니다.
