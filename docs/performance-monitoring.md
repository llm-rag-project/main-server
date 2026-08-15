# 성능 모니터링

## 접속 주소

- Grafana: `http://localhost:3000`
- Prometheus: `http://localhost:9090`
- FastAPI 원본 메트릭: `http://localhost:8001/metrics`

Grafana는 로컬 환경에서 별도 로그인 없이 읽기 전용으로 열립니다. `News Intelligence 성능` 대시보드는 컨테이너 시작 시 자동으로 등록됩니다.

## 확인할 수 있는 수치

- API 요청량과 서버 오류율
- API p50, p95, p99 응답시간
- 750ms 이상 느린 요청 수와 느린 API 경로
- 크롤링 서버 및 AI 서버 호출 성공 여부와 p95 응답시간
- 수집 작업 전체 소요시간과 처리 기사 수
- FastAPI 프로세스의 CPU와 메모리 사용량

`p95`가 800ms라면 전체 요청의 95%가 800ms 안에 끝났다는 의미입니다. 평균보다 느린 일부 요청의 영향을 더 잘 보여주므로 성능 개선 전후 비교의 기본 지표로 사용합니다.

## 성능 개선 전후 비교

1. Grafana 우측 상단에서 비교할 시간 범위를 선택합니다.
2. `API 경로` 필터에서 확인할 기능을 고릅니다.
3. 같은 사용자 동작을 여러 번 수행합니다.
4. `API p95 응답시간`, `느린 요청`, `외부 서비스 p95 응답시간`을 비교합니다.
5. 수집 기능은 `크롤링 전체 처리시간`과 `최근 크롤링 처리 기사`를 함께 확인합니다.

메트릭은 모니터링 적용 이후부터 기록됩니다. 과거 실행 시간을 소급 생성하지는 않으며, Prometheus 데이터는 Docker 볼륨에 30일 동안 보관됩니다.

## 실행

```powershell
docker compose up -d --build
```

### 동일 조건 API 벤치마크

Grafana 비교 전후에 같은 URL, 요청 수, 동시성을 사용합니다. 첫 연결 생성 비용이
결과를 흔들지 않도록 워밍업 요청을 먼저 보냅니다.

```powershell
docker compose exec fastapi python scripts/benchmark_api.py `
  --url "http://localhost:8001/api/v1/articles?page=1&size=100&keyword_id=86" `
  --requests 96 `
  --concurrency 12 `
  --warmup 12
```

출력되는 `average_ms`, `p50_ms`, `p95_ms`, `max_ms`를 변경 전후로 기록합니다.
인증이 필요한 환경에서는 `--token`에 액세스 토큰을 전달합니다.

상태 확인:

```powershell
docker compose ps
```

Grafana 화면이 비어 있으면 먼저 서비스에서 기사 목록 조회나 수집 작업을 실행한 뒤 약 5초 후 새로고침합니다.
