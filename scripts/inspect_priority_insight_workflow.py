"""Print the configured priority insight workflow response shape without exposing its API key."""

from __future__ import annotations

import asyncio
import argparse
import json
from app.services.dify_service import DifyService
from app.services.priority_insight_service import representative_action_samples
from scripts.seed_priority_insight_july_demo import DEMO_ACTIONS


async def _full_inputs() -> dict:
    actions = []
    for index in range(84):
        item = DEMO_ACTIONS[index % len(DEMO_ACTIONS)]
        actions.append(
            {
                "id": index + 1,
                "action_type": item["action_type"],
                "source_screen": "synthetic_diagnostic",
                "mail_date": f"2026-07-{item['day']:02d}",
                "article_title": f"[합성 {index + 1}] {item['title']}",
                "article_category": item["category"],
                "article_priority": item["priority"],
                "before": item["before"],
                "after": item["after"],
                "reason": item["reason"],
            }
        )
    action_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    for item in actions:
        action_counts[item["action_type"]] = action_counts.get(item["action_type"], 0) + 1
        category = item["article_category"]
        category_counts[category] = category_counts.get(category, 0) + 1
    evidence = {
        "total_actions": len(actions),
        "action_counts": action_counts,
        "category_counts": category_counts,
    }
    return {
        "period_key": "2026-07",
        "cadence": "monthly",
        "current_priority_criteria": "총장·이사장 메시지와 기부·연구 성과를 우선한다.",
        "action_summary_json": json.dumps(evidence, ensure_ascii=False),
        "action_samples_json": json.dumps(
            representative_action_samples(actions, limit=30),
            ensure_ascii=False,
        ),
        "max_changes": 3,
    }


async def main(full: bool = False) -> None:
    service = DifyService.from_settings()
    inputs = await _full_inputs() if full else {
        "period_key": "2026-07",
        "cadence": "monthly",
        "current_priority_criteria": "총장·이사장 메시지와 기부·연구 성과를 우선한다.",
        "action_summary_json": json.dumps(
            {
                "total_actions": 4,
                "action_counts": {"mail_exclude": 2, "order_change": 2},
            },
            ensure_ascii=False,
        ),
        "action_samples_json": json.dumps(
            [
                {"action_type": "mail_exclude", "article_category": "인사/위촉"},
                {"action_type": "mail_exclude", "article_category": "인사/위촉"},
                {
                    "action_type": "order_change",
                    "article_category": "연구 성과/AI",
                    "before": {"position": 6},
                    "after": {"position": 2},
                },
                {
                    "action_type": "order_change",
                    "article_category": "연구 성과/AI",
                    "before": {"position": 5},
                    "after": {"position": 1},
                },
            ],
            ensure_ascii=False,
        ),
        "max_changes": 3,
    }
    payload = {
        "inputs": inputs,
        "response_mode": "blocking",
        "user": "diagnostic",
    }
    response = await service._post(
        "/workflows/run",
        service.priority_insight_workflow_api_key,
        payload,
    )
    data = response.get("data") or {}
    print(
        json.dumps(
            {
                "top_keys": list(response.keys()),
                "data_keys": list(data.keys()),
                "workflow_run_id": response.get("workflow_run_id") or data.get("workflow_run_id") or data.get("id"),
                "status": data.get("status"),
                "error": data.get("error"),
                "sample_count": len(json.loads(inputs["action_samples_json"])),
                "sample_bytes": len(inputs["action_samples_json"].encode("utf-8")),
                "outputs": data.get("outputs"),
            },
            ensure_ascii=False,
            default=str,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(full=args.full))
