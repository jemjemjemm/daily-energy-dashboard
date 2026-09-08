# Daily / 유가 통합 전환 롤백 기록

## 상태

- 전환 상태: **완료**
- 전환일: 2026-09-07 KST
- 최종 추가 검증일: 2026-09-08 KST
- Daily 운영 주소: <https://jemjemjemm.github.io/daily-energy-dashboard/>
- 유가 운영 주소: <https://jemjemjemm.github.io/daily-energy-dashboard/oil/>
- 기존 F_Issue 주소: 새 유가 주소로 리다이렉트

## 전체 작업 시작 전 기준점

- `jemjemjemm/daily-energy-dashboard` `main`: `bd6532f0d1beb28c8af61afaa3879d6b0f4a30b2`
- `jemjemjemm/F_Issue` `main`: `2600d47c2ef46751c7b8b23b53eef8da5d276e0e`

## 전환 완료 병합 커밋

- Daily 통합 병합: `6aea69d46e6d25a8533ef097100e9fa373e62f2e`
- F_Issue 리다이렉트 병합: `43cea06cebe77de35b05be195b35646578368fce`

F_Issue는 전체 기준점을 기록한 뒤 예약 수집이 한 차례 더 실행됐습니다. 리다이렉트만 되돌릴 때 최신 수집 데이터를 잃지 않도록 다음 지점을 우선 사용합니다.

- F_Issue 리다이렉트 직전: `ab4a1b51759432b782f46e819744ea83d5d9a362`

## Pages 설정

- 전환 전 Daily: `Deploy from a branch`, `main` / `/docs`
- 전환 후 Daily: `GitHub Actions`
- 전환 후 F_Issue: `GitHub Actions`, 이미 배포된 리다이렉트 artifact 유지

## 검증 결과

- Daily 리포트: 131개
- 유가 리포트: HTML 253개, JSON 253개
- 유가 내부 상대경로: 손상 0개
- 기존 F_Issue 개별 리포트: 최초 3개와 추가 12개 모두 정상 리다이렉트 및 렌더링
- 추가 12개 구성: 2026-06-14~2026-09-06, morning/evening/night 각 4개

## Daily 전체 전환 롤백

1. Daily Pages Source를 `Deploy from a branch`, `main` / `/docs`로 되돌립니다.
2. `6aea69d46e6d25a8533ef097100e9fa373e62f2e`를 mainline parent 1로 revert합니다.
3. revert 커밋을 `daily-energy-dashboard/main`에 푸시합니다.
4. 원격 이력과 기존 Daily 운영 URL을 확인합니다.

예시:

```bash
git revert -m 1 6aea69d46e6d25a8533ef097100e9fa373e62f2e
git push origin main
```

## F_Issue 리다이렉트 롤백

1. `43cea06cebe77de35b05be195b35646578368fce`를 mainline parent 1로 revert합니다.
2. revert 커밋을 `F_Issue/main`에 푸시합니다.
3. 필요하면 복구된 기존 Pages workflow를 실행하고 기존 URL을 확인합니다.

예시:

```bash
git revert -m 1 43cea06cebe77de35b05be195b35646578368fce
git push origin main
```

강제 push나 브랜치 reset보다 revert 커밋을 우선합니다. 이 방식이 작업 이력을 보존하고 최신 데이터 손실 위험을 줄입니다.

## 전환 후 관찰

`daily-energy-dashboard/.github/workflows/oil-report.yml`의 `actor`와 `triggering_actor`를 7일간 하루 두 번 확인합니다. 외부 호출, 예상하지 못한 이벤트, 중복 실행 또는 반복 실패가 있으면 즉시 알리고, 최종 관찰 결과는 **2026-09-14 KST**에 보고합니다.
