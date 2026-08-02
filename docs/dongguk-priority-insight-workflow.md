# 동국대학교 홍보처 우선순위 인사이트 AI 워크플로우 명세

## 목적

관리자가 한 달 동안 수행한 기사 포함·제외, 순서 변경, 우선순위 수정 기록을 분석해 홍보처 기사 선정 기준의 변경안을 만든다.

- 매월: 반복 행동만 근거로 최대 3개 기준을 소폭 반영한다.
- 분기: 직전 완료 분기 전체 행동을 다시 분석해 최대 8개 기준을 재조정한다.
- 일회성 조작은 기준 변경 근거로 사용하지 않는다.
- 기사 자체를 다시 선정하는 워크플로우가 아니라, 기사 선정에 전달할 `priority_criteria`의 보정 규칙을 만든다.

## 호출 방식

`POST /workflows/run`, `response_mode=blocking`

환경변수:

```env
PRIORITY_INSIGHT_WORKFLOW_API_KEY=app-...
```

입력 변수:

```json
{
  "period_key": "2026-07",
  "cadence": "monthly",
  "current_priority_criteria": "현재 홍보처 AI 기사 선정 기준 전문",
  "action_summary_json": "{\"total_actions\":12,\"action_counts\":{\"mail_exclude\":5}}",
  "action_samples_json": "[{\"action_type\":\"mail_exclude\",\"article_category\":\"인사/위촉\"}]",
  "max_changes": 3
}
```

## AI 판단 규칙

1. 관리자가 반복적으로 위로 이동하거나 다시 포함한 유형은 상향 후보로 본다.
2. 반복적으로 메일에서 제외하거나 휴지통으로 이동한 유형은 하향 후보로 본다.
3. 사용자가 직접 바꾼 우선순위·분류는 변경 전후를 비교한다.
4. 한 번만 발생한 행동은 월별 기준 변경에 반영하지 않는다.
5. 사용자의 직접 입력 기준과 충돌하는 변경은 만들지 않는다.
6. `monthly`는 최대 `max_changes`개만 제안하고 변화 폭을 작게 유지한다.
7. `quarterly`는 직전 분기 전체 패턴을 요약해 기준을 다시 정리할 수 있다.
8. 이유에는 어떤 행동이 몇 회 반복됐는지 포함한다.

## 출력 형식

`result_json` 또는 `result`에 다음 JSON 객체를 반환한다.

```json
{
  "summary": "7월에는 연구 성과 기사를 위로 이동한 행동이 반복됐습니다.",
  "rationale": "연구 성과 기사 순서 상향 4회와 메일 재포함 2회를 근거로 사용했습니다.",
  "changes": [
    {
      "change_type": "raise",
      "target": "연구 성과/AI",
      "before": "기존 우선순위 기준",
      "rule_text": "연구 성과/AI 기사는 메일 대표 후보에서 한 단계 높게 평가합니다.",
      "reason": "관리자가 해당 유형을 위로 이동하거나 다시 포함한 행동이 6회 반복됐습니다.",
      "evidence_count": 6
    }
  ]
}
```

## 주의 사항

- `changes`는 반드시 배열이어야 한다.
- `rule_text`는 Dify 기사 선정 워크플로우의 `priority_criteria`에 그대로 붙일 수 있는 자연스러운 판단 문장이어야 한다.
- 내부 점수 산식이나 개발자용 설명은 넣지 않는다.
- 근거가 부족하면 `changes`를 빈 배열로 반환한다.
- 서비스는 워크플로우 오류 시 반복 행동 횟수 기반의 제한적 서버 분석으로 대체하고, 화면에 생성 방식을 기록한다.
