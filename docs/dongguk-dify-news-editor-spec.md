# 동국대학교 홍보처 맞춤 뉴스 편집 Dify 워크플로우 명세

## 목적

기사 후보 목록을 입력받아 동일 주제 기사를 그룹화하고, 홍보처 메일에 넣을 대표 기사만 선정한다.

같은 보도자료, 연구성과, 행사처럼 동일 주제에 해당하는 기사는 하나의 그룹으로 묶고 대표 기사 1건만 `selected_articles`에 포함한다. 나머지는 `excluded_articles`에 제외 사유와 함께 반환한다.

카테고리, 우선순위, 대표 기사 선정 기준은 서비스 화면에서 확정된 `priority_criteria` 전문을 기준으로 판단한다. 관리자가 기준을 삭제하거나 수정한 경우, 수정된 최종 기준만 적용하며 Dify 또는 서버에서 기본 기준을 다시 보충하지 않는다.

## 호출 방식

서비스는 Dify Workflow `/workflows/run`을 blocking 모드로 호출한다.

```json
{
  "inputs": {
    "mail_date": "2026-07-11",
    "subject": "오늘의 주요 뉴스 2026.07.11.[토]",
    "articles_json": "[...]",
    "priority_criteria": "기본 홍보처 기준 또는 관리자가 수정한 최종 기준"
  },
  "response_mode": "blocking",
  "user": "pr-editor-bot"
}
```

## 입력 변수

- `mail_date`: 메일 기준일, `YYYY-MM-DD`
- `subject`: 메일 제목
- `articles_json`: 기사 후보 배열을 stringify한 JSON 문자열
- `priority_criteria`: 화면에서 확정된 우선순위 및 대표 기사 선정 기준 전문

`articles_json`의 각 항목은 아래 필드를 포함한다.

```json
{
  "id": 123,
  "title": "기사 제목",
  "source": "언론사",
  "summary": "서비스가 가진 기사 요약",
  "url": "https://example.com/news/123",
  "thumbnail_url": "https://example.com/image.jpg",
  "published_at": "2026-07-11 08:15:00+09:00"
}
```

## 판단 규칙

1. `priority_criteria`를 최우선 판단 기준으로 사용한다.
2. 동일 주제, 동일 보도자료, 같은 사건의 반복 보도는 하나의 그룹으로 묶는다.
3. 각 그룹에서는 대표 기사 1건만 `selected_articles`에 포함한다.
4. 대표 기사는 원문 품질, 제목 명확성, 출처 신뢰도, 요약 가능성, 홍보처 기준 부합도를 고려해 선택한다.
5. 같은 그룹에서 제외한 기사는 `excluded_articles`에 넣고 제외 사유를 남긴다.
6. 사용자가 기준에서 특정 항목을 삭제했다면 그 항목은 적용하지 않는다.

## Dify 출력

Dify는 `outputs.result_json` 또는 `outputs.result`에 아래 JSON 객체를 반환한다.

```json
{
  "mail_date": "2026-07-11",
  "subject": "오늘의 주요 뉴스 2026.07.11.[토]",
  "selected_articles": [
    {
      "representative_article_id": 123,
      "title": "대표 기사 제목",
      "source": "언론사",
      "summary": "메일에 넣을 1~2문장 요약",
      "category": "기부/장학/발전기금",
      "priority": "최우선",
      "main_url": "https://example.com/news/123",
      "related_links": [
        "https://example.com/news/123",
        "https://example.com/news/456"
      ],
      "selection_reason": "동일 주제 보도 중 제목이 가장 명확하고 원문 확인이 가능해 대표로 선택"
    }
  ],
  "excluded_articles": [
    {
      "article_id": 456,
      "title": "제외 기사 제목",
      "reason": "대표 기사와 같은 주제의 중복 보도"
    }
  ]
}
```

메인 서버는 Dify raw 응답의 `data.outputs.result_json`을 JSON으로 파싱해 내부 preview/email 데이터로 매핑한다. Dify가 이미 `success/data/error/meta` 형태로 감싼 응답을 반환해도 서버가 `data`를 풀어서 처리한다.

## 주의 사항

- `selected_articles`에는 같은 주제 기사를 여러 개 넣지 않는다.
- `summary`에는 개발자용 설명, 점수 산식 설명, “기존 메일 패턴상” 같은 내부 문구를 넣지 않는다.
- `main_url`과 `related_links`에는 입력으로 받은 실제 원문 URL을 유지한다.
- `selected_articles`와 `excluded_articles`는 반드시 배열이어야 한다.
- `representative_article_id` 또는 `main_url`은 입력 기사 후보 중 하나와 매칭되어야 한다.
