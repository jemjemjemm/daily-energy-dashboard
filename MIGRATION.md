# Daily / 유가 통합 이전 기록

## 통합 전 기준 커밋

통합 작업은 아래 두 `main` 커밋을 기준으로 시작했습니다.

- `jemjemjemm/daily-energy-dashboard`: `aff84ab3b5d5feb0b728ffc460365da99c8688c1`
- `jemjemjemm/F_Issue`: `2600d47c2ef46751c7b8b23b53eef8da5d276e0e`

문제가 생기면 이 두 커밋에서 통합 전 파일과 자동화 상태를 재현할 수 있습니다.

## 외부 workflow 호출 점검

`F_Issue`의 최근 Actions 실행 100건에는 `schedule` 63건, `workflow_dispatch` 31건, `push` 6건이 있었습니다. 모든 실행의 표시된 실행 주체는 `jemjemjemm`입니다. `workflow_dispatch` 실행이 오전·오후 시간대에 반복되어 저장소 밖 스케줄러나 사용자 계정 토큰을 사용한 호출이 있을 가능성이 있습니다.

사용자 계정의 확인 가능한 네 저장소(`daily-energy-dashboard`, `daily-energy-dashboard2`, `2026GG`, `F_Issue`)에서는 `F_Issue`, `f-issue-report.yml`, `repository_dispatch` 또는 다른 workflow를 호출하는 코드를 찾지 못했습니다. 저장소 외부 서비스의 설정은 GitHub 저장소만으로 식별할 수 없습니다.

외부 호출이 있다면 다음 대상으로 변경해야 합니다.

- 저장소: `jemjemjemm/daily-energy-dashboard`
- workflow 파일: `.github/workflows/oil-report.yml`
- workflow 이름: `F-Issue Report`
- branch/ref: `main`
- 입력값: 기존과 동일한 `report_slot`, `base_date`, `force_refresh`

새 workflow 자체에 기존 08:10·17:10 KST 예약 실행이 포함되어 있으므로, 같은 시간의 외부 호출을 유지하면 중복 실행될 수 있습니다. 전환 전에 외부 스케줄러가 확인되면 새 호출로 바꾸기보다는 내장 예약과 역할을 비교해 하나만 유지합니다.

## 단계별 전환

1. 두 작업 브랜치를 푸시한다. Pages 설정은 유지한다.
2. 통합 브랜치의 공통 배포 workflow를 수동 검증한다.
3. Daily 131개, 유가 253개 및 `/oil/` 경로를 확인한다.
4. 사용자 최종 승인 후에만 Pages Source를 GitHub Actions로 전환한다.
