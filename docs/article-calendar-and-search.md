# 기사 휴일 조회 및 내부 검색 구현

## 1. 변경 파일

### 백엔드

- `app/api/v1/calendar.py`: 업무일 조회와 학교 휴일 CRUD API
- `app/api/v1/articles.py`: 내부 뉴스 검색, 검색 결과 정규화, URL 기사 등록 연계
- `app/api/v1/reports.py`: 홍보처 메일 후보의 업무일 범위 적용
- `app/api/router.py`: 캘린더 라우터 등록
- `app/models/school_holiday.py`: 학교 휴일 모델
- `app/models/__init__.py`: 학교 휴일 모델 등록
- `app/repositories/article_repository.py`: 기사별 수집 시각(`matched_at`) 조회
- `app/schemas/articles.py`: 수집 시각과 웹 검색 응답 스키마
- `app/schemas/calendar.py`: 휴일과 업무일 범위 스키마
- `app/services/holiday_service.py`: 법정공휴일, 주말, 학교 휴일 계산
- `app/services/crawl_scheduler_service.py`: 휴일 수집 유지 및 다음 업무일 자동 메일 처리
- `alembic/env.py`: 애플리케이션 `DATABASE_URL`을 Alembic에도 적용
- `alembic/versions/d20260726_school_holidays.py`: 학교 휴일 테이블 마이그레이션
- `requirements.txt`: 대한민국 공휴일 계산용 `holidays` 추가

### 프론트엔드

- `react-app/src/api.js`: 캘린더, 학교 휴일, 웹 검색 API 함수
- `react-app/src/App.jsx`: 기간 조회, 날짜별 그룹, 휴일 관리, 내부 검색, 기사 추가·편집
- `react-app/src/styles.css`: 날짜 조회, 휴일 관리, 검색 결과, 고정 편집 영역 UI

### 테스트

- `tests/test_holiday_service.py`: 월요일·연속 휴일·일반 평일 범위
- `tests/test_article_identity.py`: 추적 파라미터가 다른 동일 URL 정규화
- `tests/test_article_search_normalization.py`: 깨진 검색 요약 제외

## 2. 날짜 조회 규칙

`GET /api/v1/calendar/work-window?date=YYYY-MM-DD`가 화면과 메일 발송이 사용할 조회 범위를 계산한다.

- 화요일부터 금요일: 선택한 날짜 하루
- 월요일: 직전 토요일부터 월요일
- 공휴일 또는 학교 휴일 다음 업무일: 직전 업무일 이후 연속된 모든 휴일부터 해당 업무일까지
- 휴일 당일을 직접 선택: 해당 날짜 하루
- 최대 역산 범위: 45일

기사 목록은 키워드의 실제 수집 기록인 `article_matches.matched_at`을 기준으로 조회한다. 화면에는 `matched_at`을 수집일로, `published_at`을 작성일로 각각 표시한다. 날짜별 그룹은 수집일을 우선 사용하고, 과거 데이터에 수집일이 없을 때만 작성일을 보조 기준으로 사용한다.

수집 스케줄은 주말과 휴일에도 계속 실행한다. 자동 메일만 휴일에는 건너뛰고, 다음 업무일에 누적 범위를 사용한다.

## 3. 공휴일과 학교 휴일

법정공휴일은 `holidays.country_holidays("KR")`로 연도별 자동 계산한다. 학교 휴일은 사용자별 DB 테이블에 저장한다.

`school_holidays` 주요 컬럼:

- `user_id`: 휴일을 등록한 사용자
- `name`: 방학, 개교기념일, 재량휴업일 등
- `start_date`, `end_date`: 포함 범위
- `is_active`: 사용 여부
- `created_at`, `updated_at`

API:

- `GET /api/v1/calendar/school-holidays`
- `POST /api/v1/calendar/school-holidays`
- `PATCH /api/v1/calendar/school-holidays/{id}`
- `DELETE /api/v1/calendar/school-holidays/{id}`

학교 휴일은 최대 1년까지 등록할 수 있고, 시작일이 종료일보다 늦으면 422 오류를 반환한다.

## 4. 사용자 지정 기간

‘오늘 수집된 기사’에서 시작일과 종료일을 선택한 뒤 기간 조회를 실행한다.

- 시작일과 종료일을 같은 날짜로 지정하면 하루만 조회
- 최대 조회 기간은 31일
- 잘못된 날짜 순서와 31일 초과는 화면에서 즉시 안내
- ‘업무일 기준’은 선택 기준일의 자동 업무일 범위로 복귀
- ‘오늘’은 오늘 날짜로 복귀
- 결과는 수집일별로 그룹화
- 결과 없음 상태와 로딩 상태를 별도로 표시
- 기존 화면 표시 개수 선택을 유지해 대량 결과 렌더링을 제한

## 5. 서비스 내부 뉴스 검색

프론트엔드는 `GET /api/v1/articles/web-search`를 호출한다.

지원 파라미터:

- `q`: 검색어
- `page`, `size`: 페이지
- `sort`: `relevance` 또는 `latest`
- `from`, `to`: 작성일 범위
- `publisher`: 언론사 부분 일치

백엔드는 기존 TransNews `/news` 검색을 사용한다. 검색 결과를 제목, 언론사, 작성일, 요약, URL, 대표 이미지로 정규화한다. 원문은 새 창으로 연다.

첫 페이지는 20건만 선조회하고 뒤 페이지에서 필요한 만큼 점진적으로 늘린다. 같은 조건의 검색 결과는 프로세스 메모리에 3분간, 최대 64개 조건까지 보관한다. 크롤링 서버가 깨진 인코딩의 요약을 반환하면 요약을 비워 화면에 깨진 글자가 남지 않게 한다.

필요 환경변수:

```env
TRANSNEWS_BASE_URL=http://host.docker.internal:8000/api/v1
TRANSNEWS_REQUEST_TIMEOUT=60
```

새 API 키나 검색 라이브러리는 추가하지 않았다. 기존 크롤링 서버 연결을 재사용한다.

## 6. 검색 기사 추가와 중복 URL

검색 결과에서 한 건 또는 여러 건을 선택해 추가할 수 있다. 추가는 기존 `POST /api/v1/articles/from-url`을 사용하므로 다음 작업이 한 흐름에서 실행된다.

1. 원문 재수집
2. 제목, 본문, 언론사, 작성일, 대표 이미지 추출
3. Article 및 ArticleMatch 저장
4. 기존 요약·중요도 AI 분석
5. 편집 목록 반영

URL은 `canonicalize_article_url`로 정규화한다. 프로토콜, `www`, fragment, `utm_*` 같은 추적 파라미터 차이만 있는 URL은 같은 기사로 취급한다. 화면에서도 추가 전에 정규화 URL을 비교하고, 서버에서도 기존 canonical URL과 fingerprint를 확인한다.

## 7. 서비스 내부 편집

편집 화면에서 다음 필드를 수정할 수 있다.

- 제목
- 1~2문장 요약
- 작성일
- 대표 URL
- 상위/하위 카테고리
- 우선순위와 점수
- 기사 순서
- 메일 포함 목록에서 삭제

상단의 취소·저장 영역과 URL/검색 영역은 유지하고 기사 목록만 스크롤된다. 수정 후 다른 화면으로 이동하거나 브라우저를 닫으면 저장하지 않은 변경 경고가 나온다.

편집 결과는 홍보처 메일 발송용 초안 테이블에 저장한다. 원문 수집 데이터 전체를 덮어쓰지 않으므로 같은 기사를 다른 화면에서 사용할 때 원본이 손상되지 않는다. URL로 새로 추가한 기사는 원문 기사 테이블에도 저장된다.

## 8. 예외와 로딩 상태

- 날짜 순서 오류, 기간 초과: 입력 하단 안내
- 검색어 2자 미만: 검색 실행 전 안내
- 검색 결과 없음: 전용 빈 상태
- 크롤링 서버 오류·타임아웃: 502 응답과 사용자 토스트
- 검색 및 URL 추가 중: 버튼 비활성화와 로딩 아이콘
- 일부 다중 추가 실패: 성공·중복·실패 건수를 나눠 안내
- 저장 전 이탈: 확인 경고
- 오래된 요청이 늦게 도착한 경우: request id를 비교해 최신 화면을 덮어쓰지 않음

## 9. 실행과 테스트

```powershell
docker compose build fastapi react-app
docker compose up -d
docker compose exec fastapi python -m unittest tests.test_holiday_service tests.test_article_identity tests.test_article_search_normalization
docker compose run --rm react-app npm run build
```

새 DB에서는 다음 명령으로 마이그레이션을 적용한다.

```powershell
docker compose exec fastapi alembic upgrade head
```

현재 개발 DB는 `alembic_version`이 저장소에 없는 과거 revision `c09b0f92d00d`를 가리킨다. 기존 데이터를 보호하기 위해 자동 stamp는 하지 않았다. 이 DB에 Alembic을 다시 적용하려면 해당 과거 migration 파일을 복구하거나 현재 스키마를 검증한 뒤 별도 baseline revision으로 연결해야 한다. 애플리케이션은 시작 시 SQLAlchemy metadata로 누락 테이블을 생성하므로 현재 학교 휴일 기능은 정상 동작한다.

## 10. 확인 결과

- 월요일 `2026-07-27`: `2026-07-25`부터 `2026-07-27`까지 계산
- 광복절 대체휴일 다음 업무일 `2026-08-18`: `2026-08-15`부터 `2026-08-18`까지 계산
- 백엔드 단위 테스트: 7건 통과
- 프론트엔드 Vite 프로덕션 빌드: 통과
- 브라우저: 내부 검색 44건 표시, 원문 링크·필터·페이지·추가 버튼 표시 확인
- 내부 검색 첫 요청: 약 44.6초에서 약 26.7초로 단축
- 동일 검색 재요청: 3분 캐시 사용 시 약 0.22초
