# 그래프 hover/touch tooltip 복구 적용 방법

## 원인
현재 `scripts/generate_html_report.py`의 `TOOLTIP_SCRIPT` 블록이 비어 있어, 그래프 SVG와 `data-chart` 값은 생성되지만 마우스/터치 이벤트가 HTML에 붙지 않습니다. 그래서 그래프에 마우스를 올려도 날짜별 가격 tooltip이 뜨지 않습니다.

## 적용 파일
- 신규 파일: `scripts/patch_generate_html_tooltip.py`

이 파일은 기존 자동화 로직을 바꾸지 않고, `scripts/generate_html_report.py`의 비어 있는 `TOOLTIP_SCRIPT`만 실제 JavaScript로 교체합니다.

## 적용 순서

```bash
python scripts/patch_generate_html_tooltip.py
python -m py_compile scripts/generate_html_report.py
python scripts/generate_html_report.py --date 2026-05-26 --report-dir data/reports --out-dir docs/reports
python scripts/generate_report_index.py --reports-dir docs/reports --out docs/report-index.json
```

## 전체 과거 리포트에도 반영하려면

```bash
python scripts/generate_reports_range.py \
  --start 2026-05-04 \
  --end 2026-05-26 \
  --skip-weekends \
  --skip-korean-holidays \
  --report-dir data/reports \
  --schedule-dir data/schedules \
  --price-dir data/prices \
  --history data/prices/history.json \
  --html-dir docs/reports \
  --index-out docs/report-index.json \
  --base-report report_sample.json \
  --chart-months 2 \
  --max-pages 80
```

## 확인 포인트

생성된 `docs/reports/2026-05-26.html` 안에 아래 문자열이 있어야 합니다.

- `chart-box data-chart`
- `mousemove`
- `touchmove`
- `pointermove`
- `chart-tooltip`

배포 후 PC에서는 그래프에 마우스를 올리면 날짜별 가격이 뜨고, iPhone Safari에서는 그래프를 터치하거나 손가락으로 움직이면 가격이 떠야 정상입니다.
