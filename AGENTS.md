# 상임위 뉴스 리포트 운영

## 사용자 트리거

- `morning`, `모닝 리포트 업데이트`, `morning report update/발간`: 국감의 주요 이슈 Morning을 작성한다.
- `evening`, `이브닝 리포트 업데이트`, `evening report update/발간`: 국감의 주요 이슈 Evening을 작성한다.
- Daily/유가 업데이트가 함께 요청되면 그 기존 작업도 수행한다. 모든 morning/evening 발간 시 Monitoring Report의 원본 完 탭을 최신 동기화한다.
- 별도 날짜가 없으면 실행 시점 KST 날짜. 명시 날짜가 있으면 그 날짜를 우선한다. Morning D-1 17:00~D 08:00, Evening D 08:00~17:00 (경계 포함). 마감 전에는 완결 리포트를 발간하지 않는다.
- 사용자의 online push 지시가 있으면 검증, 커밋, push, Actions 배포 성공 및 온라인 확인까지 수행한다.
- 발간한 시간대만 기본으로 펼친다. Morning 발간 시 Evening을 접고, Evening 발간 시 Morning을 접는다. Daily 생성에는 해당 `--report-slot`을 전달하고 국감은 최신 발간시각의 슬롯을 펼친다. 접힌 보고서도 제목을 눌러 다시 열 수 있어야 한다.

## 웹 수집과 편집

순서는 산업통상자원중소벤처기업위원회(산자위), 기획재정위원회(기재위), 정무위원회(정무위). 현행 기사에 쓰인 재경위/재정경제기획위원회 등 별칭도 검색하되 요청한 화면 명칭은 유지한다. 소관 법안 발의·계류·처리, 본회의 통과, 정책·현안, 국정감사·청문회, 위원장·간사·주요 위원의 발언을 검색한다. 단순 기업 뉴스는 소관 정책과 직접 관련되지 않으면 제외한다.

연합뉴스 → 주요 종합·경제지 → 뉴시스·뉴스1 → 정책전문지 순으로 확인한다. 시간대 안 같은 사안은 우선순위가 높은 매체 대표 1건만 채택한다. 재전송이 아닌 원문 기사 URL, 본문, 최초 보도시각을 직접 확인하고 수정시각·검색 페이지 날짜를 최초 보도시각으로 쓰지 않는다. 시각이 불명확하거나 본문 확인에 실패한 기사는 검증 완료로 표시하지 않는다.

우선산업 태그: 정유·유가/담합, 석유화학, 배터리, LNG·전력, 도시가스, 재생에너지·수소, E&P·해외자원개발, SMR·신재생 원전(신사업). 직접 관련성이 있을 때만 태그를 붙인다. 각 위원회의 우선산업 기사(상위 5~10건 목표)는 태그/제목/사실 기반 한 줄 요약/매체/HH:MM/원문 URL, 전체 뉴스(상위 5~10건 목표)는 제목/매체/HH:MM/원문 링크. 전체 뉴스에는 비우선산업도 반드시 포함한다. 법안 진전, 산업·시장 파급력, 주요 인사 비중으로 중요도를 평가한다. 추측을 사실로 단정하거나 수량을 맞추려고 중복·시간대 밖·무관한 기사를 추가하지 않는다.

## 저장 및 발간

1. `data/committee-news/YYYY-MM-DD-SLOT.review.json`에 date, slot, search_log, articles, exclusions를 저장한다. articles 스키마는 `tools/committee_news.py`의 validate_article 및 기존 검토 파일 참조. summary, committee_reason, category_reason, time_evidence, event_id를 실제 확인 근거로 작성하고 verified는 본문·시각 확인 후 true로 지정한다. 중요도는 legislation/impact/speaker 각 0~3. 매체가 목록에 없으면 분류 근거 검토 후 코드를 확장한다.
2. `python -m tools.committee_news --slot SLOT --date YYYY-MM-DD --input 경로` 실행. 날짜별 두 슬롯을 독립 보존한다. 수집을 완료했으나 없는 섹션은 `해당 시간대 수집된 뉴스 없음`; 미발간은 별도로 표시한다. 수집 장애를 뉴스 없음으로 처리하지 않는다.
3. `docs/reports/YYYY-MM-DD.html` 및 Daily 색인 존재 확인. 없는 날짜는 기존 Daily 생성 절차로 실제 일정과 보고서를 생성·검증하고 색인 갱신한다. 가짜 일정이나 복제 날짜 파일로 대체하지 않는다.
4. `python tools/sync_assembly_content.py`로 https://jemjemjemm.github.io/26GookGam/ 完 탭 동기화. `python tools/assemble_site.py --output .cache/새로운검증경로` 후 `python -m tools.validate_site --site 해당경로`, 관련 unittest 실행.
5. 브라우저에서 국감 1/2/3 순서, Morning/Evening 및 여섯 상임위, 시각/링크, 모바일 줄바꿈과 가로 넘침, 날짜 변경 시 과거 보존, Daily 회귀 오류를 확인한다.
6. 작업 파일만 커밋한다. `.cache` 임시 파일은 추가하지 않는다. push 후 Pages Actions 성공 및 온라인 실제 내용 확인. 검색·개별 기사 미확인 등 제한이 있으면 완료 범위를 정확히 알린다.
