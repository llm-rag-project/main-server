import json
import logging
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.dongguk_priority_action import DonggukPriorityAction
from app.models.dongguk_priority_insight import DonggukPriorityInsight
from app.models.keyword import Keyword
from app.services.dify_service import DifyService

logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")
EDITABLE_FIELDS = ("title", "summary", "section", "sectionLabel", "category", "priority", "score")
ACTION_LABELS = {
    "mail_include": "메일에 다시 포함",
    "mail_exclude": "메일에서 제외",
    "order_change": "기사 순서 변경",
    "article_edit": "기사 정보 수정",
    "trash": "휴지통으로 이동",
    "trash_restore": "휴지통에서 복구",
    "criteria_edit": "관리자 기준 직접 수정",
}


def _loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _article_identity(article: dict, index: int = 0) -> str:
    article_id = article.get("id") or article.get("article_id")
    if article_id:
        return f"id:{article_id}"
    links = article.get("links") or []
    url = article.get("url") or article.get("main_url") or (links[0] if links else "")
    if url:
        return f"url:{str(url).strip().lower()}"
    return f"title:{str(article.get('title') or '').strip().lower()}:{index}"


def _effective_articles(selected_articles: list[dict], preview_data: dict | None) -> list[dict]:
    if isinstance(preview_data, dict) and isinstance(preview_data.get("articles"), list):
        return [item for item in preview_data["articles"] if isinstance(item, dict)]
    return [item for item in selected_articles if isinstance(item, dict)]


def build_draft_action_events(
    before_articles: list[dict],
    after_articles: list[dict],
) -> list[dict]:
    before_map = {_article_identity(item, index): (index, item) for index, item in enumerate(before_articles)}
    after_map = {_article_identity(item, index): (index, item) for index, item in enumerate(after_articles)}
    events: list[dict] = []

    for key in before_map.keys() - after_map.keys():
        index, article = before_map[key]
        events.append(
            {
                "action_type": "mail_exclude",
                "article_key": key,
                "article": article,
                "before": {"included": True, "position": index + 1},
                "after": {"included": False},
                "reason": "관리자가 메일 대표 기사 목록에서 제외했습니다.",
            }
        )
    for key in after_map.keys() - before_map.keys():
        index, article = after_map[key]
        events.append(
            {
                "action_type": "mail_include",
                "article_key": key,
                "article": article,
                "before": {"included": False},
                "after": {"included": True, "position": index + 1},
                "reason": "관리자가 메일 대표 기사 목록에 다시 포함했습니다.",
            }
        )

    for key in before_map.keys() & after_map.keys():
        before_index, before_article = before_map[key]
        after_index, after_article = after_map[key]
        if before_index != after_index:
            events.append(
                {
                    "action_type": "order_change",
                    "article_key": key,
                    "article": after_article,
                    "before": {"position": before_index + 1},
                    "after": {"position": after_index + 1},
                    "reason": "관리자가 메일에서 보이는 기사 순서를 변경했습니다.",
                }
            )
        changed_before: dict[str, Any] = {}
        changed_after: dict[str, Any] = {}
        for field in EDITABLE_FIELDS:
            before_value = before_article.get(field)
            after_value = after_article.get(field)
            if before_value != after_value:
                changed_before[field] = before_value
                changed_after[field] = after_value
        if changed_after:
            events.append(
                {
                    "action_type": "article_edit",
                    "article_key": key,
                    "article": after_article,
                    "before": changed_before,
                    "after": changed_after,
                    "reason": "관리자가 기사 제목, 요약, 분류 또는 우선순위를 수정했습니다.",
                }
            )
    return events


def _normalized_change(change: dict, *, evidence_count: int = 0) -> dict | None:
    rule_text = str(change.get("rule_text") or change.get("after") or "").strip()
    if not rule_text:
        return None
    return {
        "change_type": str(change.get("change_type") or change.get("effect") or "adjust").strip(),
        "target": str(change.get("target") or "전체").strip(),
        "before": str(change.get("before") or "기존 기준 유지").strip(),
        "after": rule_text,
        "rule_text": rule_text,
        "reason": str(change.get("reason") or change.get("explanation") or "사용자 편집 행동에서 반복 패턴이 확인되었습니다.").strip(),
        "evidence_count": int(change.get("evidence_count") or evidence_count or 0),
    }


def fallback_priority_changes(actions: list[dict], *, cadence: str, max_changes: int) -> list[dict]:
    minimum_evidence = 1 if cadence == "quarterly" else 2
    signals: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"count": 0, "titles": [], "priorities": Counter()}
    )

    for action in actions:
        category = str(action.get("article_category") or "미분류").strip()
        action_type = action.get("action_type")
        if action_type in {"mail_exclude", "trash"}:
            signal_key = ("lower", category)
        elif action_type == "mail_include":
            signal_key = ("raise", category)
        elif action_type == "order_change":
            before_position = int((action.get("before") or {}).get("position") or 0)
            after_position = int((action.get("after") or {}).get("position") or 0)
            if not before_position or not after_position:
                continue
            signal_key = ("raise" if after_position < before_position else "lower", category)
        elif action_type == "article_edit":
            before_priority = str((action.get("before") or {}).get("priority") or "")
            after_priority = str((action.get("after") or {}).get("priority") or "")
            if not after_priority or before_priority == after_priority:
                continue
            signal_key = ("priority", category)
            signals[signal_key]["priorities"][after_priority] += 1
        else:
            continue
        signals[signal_key]["count"] += 1
        if action.get("article_title"):
            signals[signal_key]["titles"].append(action["article_title"])

    ranked = sorted(
        (
            (effect, category, data)
            for (effect, category), data in signals.items()
            if data["count"] >= minimum_evidence
        ),
        key=lambda item: item[2]["count"],
        reverse=True,
    )
    changes: list[dict] = []
    for effect, category, data in ranked[:max_changes]:
        count = data["count"]
        if effect == "raise":
            rule_text = f"{category} 기사는 메일 대표 후보에서 한 단계 높게 평가합니다."
            reason = f"관리자가 {category} 기사에 대해 포함 또는 상향 순서 조정을 {count}회 수행했습니다."
        elif effect == "lower":
            rule_text = f"{category} 기사는 반복적으로 제외되지 않는지 확인하고 우선순위를 한 단계 낮게 평가합니다."
            reason = f"관리자가 {category} 기사에 대해 제외, 휴지통 이동 또는 하향 순서 조정을 {count}회 수행했습니다."
        else:
            preferred_priority = data["priorities"].most_common(1)[0][0] if data["priorities"] else "조정된 우선순위"
            rule_text = f"{category} 기사는 관리자가 반복 지정한 '{preferred_priority}' 수준을 우선 참고합니다."
            reason = f"관리자가 {category} 기사의 우선순위를 {count}회 직접 수정했습니다."
        changes.append(
            {
                "change_type": effect,
                "target": category,
                "before": "관리자 반복 행동을 별도 반영하지 않음",
                "after": rule_text,
                "rule_text": rule_text,
                "reason": reason,
                "evidence_count": count,
            }
        )
    return changes


def previous_month_period(today: date) -> tuple[date, date, str]:
    first_this_month = today.replace(day=1)
    end = first_this_month - timedelta(days=1)
    start = end.replace(day=1)
    return start, end, start.strftime("%Y-%m")


def previous_quarter_period(today: date) -> tuple[date, date, str] | None:
    current_quarter_start_month = ((today.month - 1) // 3) * 3 + 1
    current_quarter_start = date(today.year, current_quarter_start_month, 1)
    end = current_quarter_start - timedelta(days=1)
    quarter_start_month = end.month - ((end.month - 1) % 3)
    start = date(end.year, quarter_start_month, 1)
    quarter = ((start.month - 1) // 3) + 1
    return start, end, f"{start.year}-Q{quarter}"


class PriorityInsightService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_action(
        self,
        *,
        user_id: int,
        keyword_id: int | None,
        action_type: str,
        source_screen: str,
        mail_date: str | None = None,
        article: dict | None = None,
        article_key: str | None = None,
        before: dict | None = None,
        after: dict | None = None,
        reason: str | None = None,
    ) -> DonggukPriorityAction:
        article = article or {}
        article_id = article.get("id") or article.get("article_id")
        try:
            article_id = int(article_id) if article_id is not None else None
        except (TypeError, ValueError):
            article_id = None
        row = DonggukPriorityAction(
            user_id=user_id,
            keyword_id=keyword_id,
            article_id=article_id,
            mail_date=mail_date,
            action_type=action_type,
            source_screen=source_screen or "unknown",
            article_key=article_key or _article_identity(article),
            article_title=article.get("title"),
            article_category=article.get("category"),
            article_priority=article.get("priority"),
            before_body=_dumps(before) if before is not None else None,
            after_body=_dumps(after) if after is not None else None,
            reason=reason,
        )
        self.db.add(row)
        return row

    async def record_draft_changes(
        self,
        *,
        user_id: int,
        keyword_id: int | None,
        mail_date: str,
        source_screen: str,
        before_selected_articles: list[dict],
        before_preview_data: dict | None,
        after_selected_articles: list[dict],
        after_preview_data: dict | None,
    ) -> int:
        before_articles = _effective_articles(before_selected_articles, before_preview_data)
        after_articles = _effective_articles(after_selected_articles, after_preview_data)
        events = build_draft_action_events(before_articles, after_articles)
        for event in events:
            await self.record_action(
                user_id=user_id,
                keyword_id=keyword_id,
                mail_date=mail_date,
                source_screen=source_screen,
                action_type=event["action_type"],
                article=event["article"],
                article_key=event["article_key"],
                before=event.get("before"),
                after=event.get("after"),
                reason=event.get("reason"),
            )
        return len(events)

    async def _actions_for_period(
        self,
        *,
        user_id: int,
        keyword_id: int,
        period_start: date,
        period_end: date,
    ) -> list[DonggukPriorityAction]:
        start_at = datetime.combine(period_start, time.min, tzinfo=KST).astimezone(timezone.utc)
        end_at = datetime.combine(period_end + timedelta(days=1), time.min, tzinfo=KST).astimezone(timezone.utc)
        result = await self.db.execute(
            select(DonggukPriorityAction)
            .where(
                DonggukPriorityAction.user_id == user_id,
                DonggukPriorityAction.keyword_id == keyword_id,
                DonggukPriorityAction.created_at >= start_at,
                DonggukPriorityAction.created_at < end_at,
            )
            .order_by(DonggukPriorityAction.created_at.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    def _action_dict(row: DonggukPriorityAction) -> dict:
        return {
            "id": row.id,
            "action_type": row.action_type,
            "action_label": ACTION_LABELS.get(row.action_type, row.action_type),
            "source_screen": row.source_screen,
            "mail_date": row.mail_date,
            "article_id": row.article_id,
            "article_title": row.article_title,
            "article_category": row.article_category,
            "article_priority": row.article_priority,
            "before": _loads(row.before_body, {}),
            "after": _loads(row.after_body, {}),
            "reason": row.reason,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    @staticmethod
    def _evidence(actions: list[dict]) -> dict:
        action_counts = Counter(item["action_type"] for item in actions)
        category_counts = Counter(
            item["article_category"] for item in actions if item.get("article_category")
        )
        return {
            "total_actions": len(actions),
            "action_counts": dict(action_counts),
            "category_counts": dict(category_counts),
            "action_labels": {
                key: ACTION_LABELS.get(key, key)
                for key in action_counts
            },
        }

    async def _ai_changes(
        self,
        *,
        user_id: int,
        period_key: str,
        cadence: str,
        current_criteria: str,
        action_dicts: list[dict],
        evidence: dict,
        max_changes: int,
    ) -> tuple[list[dict], str, str, str, str | None]:
        if settings.priority_insight_workflow_api_key:
            try:
                result = await DifyService.from_settings().run_priority_insight_workflow(
                    period_key=period_key,
                    cadence=cadence,
                    current_priority_criteria=current_criteria,
                    action_summary_json=_dumps(evidence),
                    action_samples_json=_dumps(action_dicts[:120]),
                    max_changes=max_changes,
                    user=f"user-{user_id}",
                )
                changes = [
                    normalized
                    for item in result.get("changes") or []
                    if (normalized := _normalized_change(item))
                ][:max_changes]
                summary = result.get("summary") or f"{len(action_dicts)}건의 관리자 행동을 AI가 분석했습니다."
                rationale = result.get("rationale") or "반복된 포함·제외·순서·우선순위 수정 행동을 기준 변경 근거로 사용했습니다."
                return changes, summary, rationale, "ai-workflow", result.get("workflow_run_id")
            except Exception as exc:
                logger.exception("Priority insight AI workflow failed; using server fallback: %s", exc)

        changes = fallback_priority_changes(action_dicts, cadence=cadence, max_changes=max_changes)
        if changes:
            summary = (
                f"{period_key} 관리자 행동 {len(action_dicts)}건에서 반복 패턴을 찾아 "
                f"우선순위 기준 {len(changes)}개를 {'분기 전체' if cadence == 'quarterly' else '월별 소폭'} 조정했습니다."
            )
            rationale = "반복된 메일 포함·제외, 기사 순서 이동, 우선순위 수정 횟수를 집계해 일회성 조작은 제외했습니다."
        else:
            summary = f"{period_key} 관리자 행동 {len(action_dicts)}건을 분석했지만 반복 근거가 충분하지 않아 기준을 변경하지 않았습니다."
            rationale = "월별 변경은 같은 방향의 행동이 2회 이상 반복될 때만 적용해 일회성 판단이 기준을 흔들지 않도록 했습니다."
        return changes, summary, rationale, "server-analysis", None

    async def generate_insight(
        self,
        *,
        user_id: int,
        keyword_id: int,
        period_start: date,
        period_end: date,
        period_key: str,
        cadence: str,
        force: bool = False,
    ) -> DonggukPriorityInsight:
        existing = await self.db.scalar(
            select(DonggukPriorityInsight).where(
                DonggukPriorityInsight.user_id == user_id,
                DonggukPriorityInsight.keyword_id == keyword_id,
                DonggukPriorityInsight.period_key == period_key,
                DonggukPriorityInsight.cadence == cadence,
            )
        )
        if existing and not force:
            return existing

        keyword = await self.db.get(Keyword, keyword_id)
        if keyword is None or keyword.user_id != user_id:
            raise ValueError("Keyword not found")
        base_criteria = str(keyword.importance_criteria or "").strip()
        current_criteria = await self.effective_criteria(
            user_id=user_id,
            keyword_id=keyword_id,
            base_criteria=base_criteria,
        )
        action_rows = await self._actions_for_period(
            user_id=user_id,
            keyword_id=keyword_id,
            period_start=period_start,
            period_end=period_end,
        )
        action_dicts = [self._action_dict(row) for row in action_rows]
        evidence = self._evidence(action_dicts)
        max_changes = 8 if cadence == "quarterly" else 3
        changes, summary, rationale, generated_by, workflow_run_id = await self._ai_changes(
            user_id=user_id,
            period_key=period_key,
            cadence=cadence,
            current_criteria=current_criteria,
            action_dicts=action_dicts,
            evidence=evidence,
            max_changes=max_changes,
        )
        overlay = "\n".join(f"- {item['rule_text']}" for item in changes)
        criteria_after = current_criteria
        if overlay:
            heading = "분기 AI 전체 재조정" if cadence == "quarterly" else "월별 AI 소폭 반영"
            criteria_after = f"{current_criteria}\n\n{heading} ({period_key}):\n{overlay}".strip()
        now = datetime.now(timezone.utc)
        row = existing or DonggukPriorityInsight(
            user_id=user_id,
            keyword_id=keyword_id,
            period_key=period_key,
            period_start=period_start,
            period_end=period_end,
            cadence=cadence,
        )
        if existing is None:
            self.db.add(row)
        row.status = "applied" if changes else "observed"
        row.summary = summary
        row.rationale = rationale
        row.evidence_body = _dumps(evidence)
        row.criteria_before = current_criteria
        row.criteria_after = criteria_after
        row.changes_body = _dumps(changes)
        row.generated_by = generated_by
        row.workflow_run_id = workflow_run_id
        row.applied_at = now if changes else None
        row.deleted_at = None
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def _active_insights(self, *, user_id: int, keyword_id: int) -> list[DonggukPriorityInsight]:
        result = await self.db.execute(
            select(DonggukPriorityInsight)
            .where(
                DonggukPriorityInsight.user_id == user_id,
                DonggukPriorityInsight.keyword_id == keyword_id,
                DonggukPriorityInsight.status == "applied",
            )
            .order_by(DonggukPriorityInsight.period_end.asc(), DonggukPriorityInsight.id.asc())
        )
        rows = list(result.scalars().all())
        quarterly = [row for row in rows if row.cadence == "quarterly"]
        if quarterly:
            latest_quarter = quarterly[-1]
            return [
                latest_quarter,
                *[
                    row for row in rows
                    if row.cadence == "monthly" and row.period_start > latest_quarter.period_end
                ],
            ]
        monthly = [row for row in rows if row.cadence == "monthly"]
        return monthly[-3:]

    async def effective_criteria(
        self,
        *,
        user_id: int,
        keyword_id: int | None,
        base_criteria: str,
    ) -> str:
        if keyword_id is None:
            return base_criteria
        rows = await self._active_insights(user_id=user_id, keyword_id=keyword_id)
        rules: list[str] = []
        for row in rows:
            for change in _loads(row.changes_body, []):
                rule = str(change.get("rule_text") or change.get("after") or "").strip()
                if rule and rule not in rules:
                    rules.append(rule)
        if not rules:
            return base_criteria
        overlay = "\n".join(f"- {rule}" for rule in rules)
        return f"{base_criteria}\n\nAI 학습으로 반영된 우선순위 기준:\n{overlay}".strip()

    @staticmethod
    def serialize_insight(row: DonggukPriorityInsight) -> dict:
        return {
            "id": row.id,
            "keyword_id": row.keyword_id,
            "period_key": row.period_key,
            "period_start": row.period_start.isoformat(),
            "period_end": row.period_end.isoformat(),
            "cadence": row.cadence,
            "cadence_label": "분기 전체 재조정" if row.cadence == "quarterly" else "월별 소폭 반영",
            "status": row.status,
            "summary": row.summary,
            "rationale": row.rationale,
            "evidence": _loads(row.evidence_body, {}),
            "criteria_before": row.criteria_before,
            "criteria_after": row.criteria_after,
            "changes": _loads(row.changes_body, []),
            "generated_by": row.generated_by,
            "workflow_run_id": row.workflow_run_id,
            "applied_at": row.applied_at.isoformat() if row.applied_at else None,
            "deleted_at": row.deleted_at.isoformat() if row.deleted_at else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    async def list_insights(self, *, user_id: int, keyword_id: int, limit: int = 24) -> dict:
        result = await self.db.execute(
            select(DonggukPriorityInsight)
            .where(
                DonggukPriorityInsight.user_id == user_id,
                DonggukPriorityInsight.keyword_id == keyword_id,
            )
            .order_by(DonggukPriorityInsight.period_end.desc(), DonggukPriorityInsight.id.desc())
            .limit(limit)
        )
        items = [self.serialize_insight(row) for row in result.scalars().all()]
        active_rows = await self._active_insights(user_id=user_id, keyword_id=keyword_id)
        active_rules = []
        for row in active_rows:
            for change in _loads(row.changes_body, []):
                active_rules.append(
                    {
                        "insight_id": row.id,
                        "period_key": row.period_key,
                        "cadence": row.cadence,
                        **change,
                    }
                )
        return {
            "items": items,
            "active_rules": active_rules,
            "cadence": {
                "monthly": "매월 지난달 행동을 학습해 최대 3개 기준만 소폭 반영",
                "quarterly": "1·4·7·10월에 직전 분기 전체 행동으로 기준을 재조정",
            },
        }

    async def insight_detail(self, *, user_id: int, insight_id: int) -> dict:
        row = await self.db.scalar(
            select(DonggukPriorityInsight).where(
                DonggukPriorityInsight.id == insight_id,
                DonggukPriorityInsight.user_id == user_id,
            )
        )
        if row is None:
            raise ValueError("Insight not found")
        actions = await self._actions_for_period(
            user_id=user_id,
            keyword_id=row.keyword_id,
            period_start=row.period_start,
            period_end=row.period_end,
        )
        return {
            **self.serialize_insight(row),
            "actions": [self._action_dict(action) for action in actions],
        }

    async def delete_insight(self, *, user_id: int, insight_id: int) -> DonggukPriorityInsight:
        row = await self.db.scalar(
            select(DonggukPriorityInsight).where(
                DonggukPriorityInsight.id == insight_id,
                DonggukPriorityInsight.user_id == user_id,
            )
        )
        if row is None:
            raise ValueError("Insight not found")
        row.status = "deleted"
        row.deleted_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(row)
        return row
