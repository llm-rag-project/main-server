import asyncio

import httpx


async def main():
    async with httpx.AsyncClient(base_url="http://localhost:8001", timeout=240) as client:
        draft_response = await client.get(
            "/api/v1/reports/dongguk/draft",
            params={"keyword_id": 86, "mail_date": "2026-07-15"},
        )
        draft_response.raise_for_status()
        draft = draft_response.json()["data"]
        keyword_response = await client.get(
            "/api/v1/keywords",
            params={"dashboard_mode": "dongguk", "page": 1, "size": 20},
        )
        keyword_response.raise_for_status()
        keyword = next(item for item in keyword_response.json()["data"]["items"] if item["id"] == 86)
        articles = [*(draft.get("selected_articles") or []), *(draft.get("removed_articles") or [])]
        response = await client.post(
            "/api/v1/reports/dongguk/preview",
            json={
                "subject": "오늘의 주요 뉴스 2026.07.15.[수]",
                "articles": articles,
                "keyword_id": 86,
                "mail_date": "2026-07-15",
                "exclude_similar_sent": True,
                "force_rebuild": True,
                "priority_criteria": keyword.get("importance_criteria"),
            },
        )
        response.raise_for_status()
        data = response.json()["data"]
        selected = data.get("articles") or []
        excluded = data.get("excluded_articles") or []
        joint_selected = [item for item in selected if "공동학위" in (item.get("title") or "")]
        joint_excluded = [item for item in excluded if "공동학위" in (item.get("title") or "")]
        print({
            "editor_used": data.get("editor_used"),
            "selected": len(selected),
            "excluded": len(excluded),
            "joint_selected": len(joint_selected),
            "joint_excluded": len(joint_excluded),
            "representative": joint_selected[0]["title"] if joint_selected else None,
        })


asyncio.run(main())
