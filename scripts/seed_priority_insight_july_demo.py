"""Seed deterministic July 2026 priority-learning actions for the PR dashboard demo."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select

from app.db.session import AsyncSessionLocal, engine
from app.models.dongguk_priority_action import DonggukPriorityAction
from app.models.keyword import Keyword


KST = ZoneInfo("Asia/Seoul")
SOURCE_SCREEN = "demo_seed_july_2026"


def _json(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False)


DEMO_ACTIONS = [
    {
        "day": 2,
        "action_type": "mail_exclude",
        "title": "동국대 신임 보직교수 인사 발표",
        "category": "인사/위촉",
        "priority": "보통",
        "before": {"included": True, "position": 6},
        "after": {"included": False},
        "reason": "[7월 데모] 단순 인사발령 기사는 메일 핵심 소식에서 제외했습니다.",
    },
    {
        "day": 7,
        "action_type": "mail_exclude",
        "title": "동국대학교 산학협력단 전문위원 위촉",
        "category": "인사/위촉",
        "priority": "보통",
        "before": {"included": True, "position": 7},
        "after": {"included": False},
        "reason": "[7월 데모] 위촉 자체보다 학교 성과를 보여주는 기사를 우선하기 위해 제외했습니다.",
    },
    {
        "day": 15,
        "action_type": "trash",
        "title": "동국대 특임교수 신규 임용 소식",
        "category": "인사/위촉",
        "priority": "참고",
        "before": {"trashed": False, "included": False},
        "after": {"trashed": True, "included": False},
        "reason": "[7월 데모] 반복되는 단순 임용 소식이라 휴지통으로 이동했습니다.",
    },
    {
        "day": 24,
        "action_type": "mail_exclude",
        "title": "동국대 겸임교수 위촉장 수여",
        "category": "인사/위촉",
        "priority": "보통",
        "before": {"included": True, "position": 8},
        "after": {"included": False},
        "reason": "[7월 데모] 인사·위촉 기사가 반복돼 대표 메일 기사에서 제외했습니다.",
    },
    {
        "day": 3,
        "action_type": "order_change",
        "title": "동국대 연구팀, 차세대 배터리 원천기술 개발",
        "category": "연구 성과/AI",
        "priority": "주요",
        "before": {"position": 7},
        "after": {"position": 2},
        "reason": "[7월 데모] 연구 성과의 홍보 가치가 높아 기사 순서를 위로 올렸습니다.",
    },
    {
        "day": 9,
        "action_type": "order_change",
        "title": "동국대 AI 연구센터, 의료영상 분석 정확도 향상",
        "category": "연구 성과/AI",
        "priority": "주요",
        "before": {"position": 6},
        "after": {"position": 2},
        "reason": "[7월 데모] AI 연구 성과를 메일 상단에서 보여주도록 순서를 조정했습니다.",
    },
    {
        "day": 14,
        "action_type": "mail_include",
        "title": "동국대 연구진 국제학술지 표지논문 선정",
        "category": "연구 성과/AI",
        "priority": "주요",
        "before": {"included": False},
        "after": {"included": True, "position": 3},
        "reason": "[7월 데모] 대외 연구 경쟁력을 보여주는 기사라 메일에 다시 포함했습니다.",
    },
    {
        "day": 21,
        "action_type": "order_change",
        "title": "동국대 반도체 연구과제 대형 국책사업 선정",
        "category": "연구 성과/AI",
        "priority": "주요",
        "before": {"position": 5},
        "after": {"position": 1},
        "reason": "[7월 데모] 대형 연구사업 선정 성과를 최상단으로 이동했습니다.",
    },
    {
        "day": 28,
        "action_type": "article_edit",
        "title": "동국대 생성형 AI 교육 플랫폼 특허 등록",
        "category": "연구 성과/AI",
        "priority": "최우선",
        "before": {"priority": "보통", "score": 58},
        "after": {"priority": "최우선", "score": 88},
        "reason": "[7월 데모] 연구 파급력이 높다고 판단해 우선순위를 최우선으로 수정했습니다.",
    },
    {
        "day": 4,
        "action_type": "mail_include",
        "title": "동문 기업인, 동국대 발전기금 1억 원 기탁",
        "category": "기부/장학/발전기금",
        "priority": "최우선",
        "before": {"included": False},
        "after": {"included": True, "position": 1},
        "reason": "[7월 데모] 기부 소식은 학교 이미지와 직접 연결돼 메일에 추가했습니다.",
    },
    {
        "day": 11,
        "action_type": "order_change",
        "title": "불교계 인사, 동국대 장학기금 전달",
        "category": "기부/장학/발전기금",
        "priority": "최우선",
        "before": {"position": 4},
        "after": {"position": 1},
        "reason": "[7월 데모] 장학기금 기사를 메일 첫 기사로 이동했습니다.",
    },
    {
        "day": 18,
        "action_type": "mail_include",
        "title": "동국대 후배 사랑 장학금 전달식 개최",
        "category": "기부/장학/발전기금",
        "priority": "최우선",
        "before": {"included": False},
        "after": {"included": True, "position": 2},
        "reason": "[7월 데모] 장학 소식의 지속적인 홍보 가치가 있어 메일에 다시 포함했습니다.",
    },
    {
        "day": 29,
        "action_type": "article_edit",
        "title": "동국대 발전기금 모금 캠페인 목표 조기 달성",
        "category": "기부/장학/발전기금",
        "priority": "최우선",
        "before": {"priority": "주요", "score": 70},
        "after": {"priority": "최우선", "score": 92},
        "reason": "[7월 데모] 발전기금 성과를 최우선으로 직접 상향했습니다.",
    },
    {
        "day": 6,
        "action_type": "mail_exclude",
        "title": "동국대 교수의 여름 독서 추천 칼럼",
        "category": "동문/교수 인터뷰·칼럼",
        "priority": "참고",
        "before": {"included": True, "position": 8},
        "after": {"included": False},
        "reason": "[7월 데모] 학교 공식 성과와 직접 관련이 낮은 교수 칼럼을 제외했습니다.",
    },
    {
        "day": 13,
        "action_type": "trash",
        "title": "동국대 동문 방송인 근황 인터뷰",
        "category": "동문/교수 인터뷰·칼럼",
        "priority": "참고",
        "before": {"trashed": False, "included": False},
        "after": {"trashed": True, "included": False},
        "reason": "[7월 데모] 학교와의 직접 연관성이 약한 동문 근황 기사라 휴지통으로 이동했습니다.",
    },
    {
        "day": 23,
        "action_type": "mail_exclude",
        "title": "동국대 교수 영화평론 기고",
        "category": "동문/교수 인터뷰·칼럼",
        "priority": "참고",
        "before": {"included": True, "position": 7},
        "after": {"included": False},
        "reason": "[7월 데모] 개인 기고보다 대학 공식 성과를 우선하기 위해 제외했습니다.",
    },
    {
        "day": 16,
        "action_type": "article_edit",
        "title": "동국대 총장, 건학 120주년 미래 비전 발표",
        "category": "총장/이사장 메시지",
        "priority": "최우선",
        "before": {"priority": "주요", "score": 72},
        "after": {"priority": "최우선", "score": 98},
        "reason": "[7월 데모] 총장 메시지를 최우선 기사로 직접 상향했습니다.",
    },
    {
        "day": 27,
        "action_type": "article_edit",
        "title": "동국대 이사장, 교육 혁신 방향 제시",
        "category": "총장/이사장 메시지",
        "priority": "최우선",
        "before": {"priority": "보통", "score": 60},
        "after": {"priority": "최우선", "score": 95},
        "reason": "[7월 데모] 이사장 메시지의 대표성을 반영해 최우선으로 수정했습니다.",
    },
]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        keyword = await db.scalar(
            select(Keyword)
            .where(Keyword.keyword_text == "동국대학교")
            .order_by(Keyword.dashboard_mode.desc(), Keyword.id.asc())
        )
        if keyword is None:
            raise RuntimeError("동국대학교 키워드를 찾을 수 없습니다.")

        await db.execute(
            delete(DonggukPriorityAction).where(
                DonggukPriorityAction.user_id == keyword.user_id,
                DonggukPriorityAction.keyword_id == keyword.id,
                DonggukPriorityAction.source_screen == SOURCE_SCREEN,
            )
        )

        for index, item in enumerate(DEMO_ACTIONS, start=1):
            created_at = datetime(2026, 7, item["day"], 9 + (index % 7), index % 60, tzinfo=KST)
            db.add(
                DonggukPriorityAction(
                    user_id=keyword.user_id,
                    keyword_id=keyword.id,
                    article_id=None,
                    mail_date=f"2026-07-{item['day']:02d}",
                    action_type=item["action_type"],
                    source_screen=SOURCE_SCREEN,
                    article_key=f"demo:2026-07:{index:02d}",
                    article_title=item["title"],
                    article_category=item["category"],
                    article_priority=item["priority"],
                    before_body=_json(item["before"]),
                    after_body=_json(item["after"]),
                    reason=item["reason"],
                    created_at=created_at,
                    updated_at=created_at,
                )
            )

        await db.commit()
        print(
            json.dumps(
                {
                    "seed": SOURCE_SCREEN,
                    "keyword_id": keyword.id,
                    "user_id": keyword.user_id,
                    "period": "2026-07",
                    "inserted_actions": len(DEMO_ACTIONS),
                },
                ensure_ascii=False,
            )
        )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
