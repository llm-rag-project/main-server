"""Generate and persist the July insight using only the seeded synthetic actions."""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timezone

from sqlalchemy import select

from app.db.session import AsyncSessionLocal, engine
from app.models.dongguk_priority_insight import DonggukPriorityInsight
from app.models.keyword import Keyword
from app.services.priority_insight_service import PriorityInsightService
from scripts.seed_priority_insight_july_demo import SOURCE_SCREEN


PERIOD_START = date(2026, 7, 1)
PERIOD_END = date(2026, 7, 31)
PERIOD_KEY = "2026-07"
DEMO_CRITERIA = """홍보처 기본 우선순위 기준
- 총장·이사장 메시지와 기부·장학·발전기금 기사를 우선한다.
- 연구 성과·AI, 협약·사업 선정, 수상·인증, 학교 공식 행사를 주요 기사로 본다.
- 학술활동, 인사·위촉, 동문·교수 인터뷰·칼럼은 참고 기사로 본다.
- 같은 주제의 반복 보도는 대표 기사 1건만 선정한다."""


async def main() -> None:
    async with AsyncSessionLocal() as db:
        keyword = await db.scalar(
            select(Keyword)
            .where(Keyword.keyword_text == "동국대학교")
            .order_by(Keyword.dashboard_mode.desc(), Keyword.id.asc())
        )
        if keyword is None:
            raise RuntimeError("동국대학교 키워드를 찾을 수 없습니다.")

        service = PriorityInsightService(db)
        action_rows = await service._actions_for_period(
            user_id=keyword.user_id,
            keyword_id=keyword.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            source_screen=SOURCE_SCREEN,
        )
        actions = [service._action_dict(row) for row in action_rows]
        if not actions:
            raise RuntimeError("7월 확인용 목 데이터가 없습니다. 시드 스크립트를 먼저 실행해 주세요.")

        evidence = service._evidence(actions)
        changes, summary, rationale, generated_by, workflow_run_id = await service._ai_changes(
            user_id=keyword.user_id,
            period_key=PERIOD_KEY,
            cadence="monthly",
            current_criteria=DEMO_CRITERIA,
            action_dicts=actions,
            evidence=evidence,
            max_changes=3,
        )
        if generated_by != "ai-workflow":
            raise RuntimeError("AI 워크플로우가 아닌 서버 대체 분석이 실행됐습니다.")

        row = await db.scalar(
            select(DonggukPriorityInsight).where(
                DonggukPriorityInsight.user_id == keyword.user_id,
                DonggukPriorityInsight.keyword_id == keyword.id,
                DonggukPriorityInsight.period_key == PERIOD_KEY,
                DonggukPriorityInsight.cadence == "monthly",
            )
        )
        if row is None:
            row = DonggukPriorityInsight(
                user_id=keyword.user_id,
                keyword_id=keyword.id,
                period_key=PERIOD_KEY,
                period_start=PERIOD_START,
                period_end=PERIOD_END,
                cadence="monthly",
                summary=summary,
                criteria_before=DEMO_CRITERIA,
                criteria_after=DEMO_CRITERIA,
            )
            db.add(row)

        overlay = "\n".join(f"- {item['rule_text']}" for item in changes)
        row.status = "applied" if changes else "observed"
        row.summary = summary
        row.rationale = rationale
        row.evidence_body = json.dumps(evidence, ensure_ascii=False)
        row.criteria_before = DEMO_CRITERIA
        row.criteria_after = (
            f"{DEMO_CRITERIA}\n\n월별 AI 소폭 반영 ({PERIOD_KEY}):\n{overlay}"
            if overlay
            else DEMO_CRITERIA
        )
        row.changes_body = json.dumps(changes, ensure_ascii=False)
        row.generated_by = "ai-workflow-demo"
        row.workflow_run_id = workflow_run_id
        row.applied_at = datetime.now(timezone.utc) if changes else None
        row.deleted_at = None
        await db.commit()
        await db.refresh(row)

        print(
            json.dumps(
                {
                    "insight_id": row.id,
                    "period": row.period_key,
                    "actions": len(actions),
                    "changes": len(changes),
                    "generated_by": row.generated_by,
                    "has_workflow_run_id": bool(row.workflow_run_id),
                    "targets": [item.get("target") for item in changes],
                },
                ensure_ascii=False,
            )
        )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
