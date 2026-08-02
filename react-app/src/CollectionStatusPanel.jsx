import React, { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  CalendarRange,
  CheckCircle2,
  ChevronDown,
  Clock3,
  FileSearch,
  GraduationCap,
  Landmark,
  Loader2,
  RefreshCw,
  RotateCcw,
} from "lucide-react";
import { endpoints } from "./api";

const KST_DATE_FORMAT = new Intl.DateTimeFormat("en-CA", {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  timeZone: "Asia/Seoul",
});

const KST_DATE_TIME_FORMAT = new Intl.DateTimeFormat("ko-KR", {
  month: "long",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
  timeZone: "Asia/Seoul",
});

const SOURCE_LABELS = {
  dongguk_official: "동국대학교 공식 채널",
  google_rss: "구글 뉴스",
  media_direct_pool: "홍보처 주요 언론사",
  media_site_direct: "언론사 직접 검색",
  naver: "네이버 뉴스",
  relation_expansion: "연관 기사 검색",
  section_pool: "분야별 뉴스",
  section_pool_buddhism: "불교·종단 뉴스",
  section_pool_education: "대학·교육 뉴스",
};

const COLLECTION_GROUPS = [
  {
    key: "dongguk",
    title: "동국대학교 관련 뉴스",
    description: "학교 공식 채널과 네이버·구글·주요 언론사를 함께 확인합니다.",
    icon: Landmark,
    sourceNames: [
      "dongguk_official",
      "naver",
      "google_rss",
      "media_direct_pool",
      "media_site_direct",
      "relation_expansion",
    ],
  },
  {
    key: "education",
    title: "대학 [교육]",
    description: "입시, 교육부, 대학 정책과 고등교육 기사를 확인합니다.",
    icon: GraduationCap,
    sourceNames: ["section_pool_education"],
  },
  {
    key: "buddhism",
    title: "불교 [종단]",
    description: "조계종, 사찰과 불교계 주요 기사를 확인합니다.",
    icon: FileSearch,
    sourceNames: ["section_pool_buddhism"],
  },
];

function localDateKey(value = new Date()) {
  return KST_DATE_FORMAT.format(new Date(value));
}

function formatDateTime(value) {
  if (!value) return "수집 기록 없음";
  return KST_DATE_TIME_FORMAT.format(new Date(value));
}

function formatDateRange(start, end) {
  if (!start || !end) return "기간 정보 없음";
  const startKey = localDateKey(start);
  const endKey = localDateKey(end);
  return startKey === endKey ? startKey : `${startKey} ~ ${endKey}`;
}

function sourceLabel(value) {
  return SOURCE_LABELS[value] || "추가 뉴스 검색";
}

function runStatus(run) {
  const sources = run?.sources || [];
  const locked = sources.some((source) => source.status === "skipped_locked");
  const automaticRetry = ["auto_retry", "daily_refresh"].includes(run?.trigger_type);
  const automaticPrefix = automaticRetry ? "서버가 자동으로 다시 확인했습니다. " : "";
  if (locked) {
    return {
      tone: "waiting",
      label: "수집 중",
      message: "같은 기간의 수집이 진행 중입니다.",
    };
  }
  if (run?.has_warning) {
    return {
      tone: "warning",
      label: "일부 확인 필요",
      message: run.article_count
        ? `${automaticPrefix}일부 검색 경로가 지연됐지만 확인된 기사는 저장되었습니다.`
        : `${automaticPrefix}일부 검색 경로가 응답하지 않아 다시 확인할 수 있습니다.`,
    };
  }
  return {
    tone: "success",
    label: "수집 완료",
    message: run?.article_count
      ? `${automaticPrefix}선택한 기간의 기사를 정상적으로 확인했습니다.`
      : `${automaticPrefix}수집은 완료됐으며 새로 저장할 기사는 없었습니다.`,
  };
}

function sourceStatus(source) {
  const successRate = Number(source?.success_rate || 0);
  if (!source?.run_count) return { tone: "neutral", label: "기록 없음" };
  if (successRate >= 80) return { tone: "success", label: "정상" };
  if (successRate > 0) return { tone: "warning", label: "일부 지연" };
  return { tone: "danger", label: "확인 필요" };
}

function runSourceStatus(source) {
  if (source.status === "success") return "정상";
  if (source.status === "timeout") return "응답 지연";
  if (source.status === "failed") return "수집 실패";
  if (source.status === "partial") return "일부 수집";
  if (source.status === "skipped_locked") return "수집 중";
  if (source.status === "empty") return "새 기사 없음";
  return "확인 완료";
}

function CollectionStatusPanel({ keywordId, keywordName, showToast }) {
  const today = localDateKey();
  const [days, setDays] = useState("7");
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [replaying, setReplaying] = useState(false);
  const [replayRange, setReplayRange] = useState({ from_date: today, to_date: today });
  const [lastLoadedAt, setLastLoadedAt] = useState(null);

  async function loadHealth({ quiet = false } = {}) {
    if (!keywordId) return;
    if (!quiet) setLoading(true);
    setError("");
    try {
      const result = await endpoints.crawlHealth({
        keyword_id: keywordId,
        days,
        limit: 30,
      });
      setHealth(result);
      setLastLoadedAt(new Date());
    } catch (err) {
      setError(err.message);
    } finally {
      if (!quiet) setLoading(false);
    }
  }

  useEffect(() => {
    setHealth(null);
    if (keywordId) loadHealth();
  }, [keywordId, days]);

  useEffect(() => {
    if (!keywordId) return undefined;
    const timer = window.setInterval(() => loadHealth({ quiet: true }), 60_000);
    return () => window.clearInterval(timer);
  }, [keywordId, days]);

  const sourcesByName = useMemo(
    () => new Map((health?.sources || []).map((source) => [source.name, source])),
    [health]
  );

  const collectionGroups = useMemo(
    () => COLLECTION_GROUPS.map((group) => {
      const sources = group.sourceNames.map((name) => sourcesByName.get(name)).filter(Boolean);
      const discoveredCount = sources.reduce((sum, source) => sum + Number(source.discovered_count || 0), 0);
      const runCount = sources.reduce((sum, source) => sum + Number(source.run_count || 0), 0);
      const successCount = sources.reduce((sum, source) => sum + Number(source.success_count || 0), 0);
      const successRate = runCount ? Math.round((successCount / runCount) * 100) : 0;
      return {
        ...group,
        sources,
        discoveredCount,
        runCount,
        successRate,
        status: sourceStatus({ run_count: runCount, success_rate: successRate }),
      };
    }),
    [sourcesByName]
  );

  const meaningfulRuns = useMemo(
    () => (health?.recent_runs || [])
      .filter((run) => !(run.sources || []).some((source) => source.status === "skipped_locked"))
      .slice(0, 6),
    [health]
  );

  const latestRun = meaningfulRuns[0];
  const latestStatus = latestRun
    ? runStatus(latestRun)
    : { tone: "neutral", label: "기록 없음", message: "아직 확인할 수집 기록이 없습니다." };

  async function replayRangeArticles() {
    if (!keywordId || replaying) return;
    if (!replayRange.from_date || !replayRange.to_date) {
      showToast?.("다시 수집할 시작일과 종료일을 선택해 주세요.", "error");
      return;
    }
    if (replayRange.from_date > replayRange.to_date) {
      showToast?.("시작일은 종료일보다 늦을 수 없습니다.", "error");
      return;
    }

    setReplaying(true);
    setError("");
    showToast?.("기간 기사 수집을 시작했습니다. 완료까지 약 1~2분이 걸릴 수 있습니다.", "info");
    try {
      const result = await endpoints.replayCrawl({
        keyword_id: Number(keywordId),
        from_date: replayRange.from_date,
        to_date: replayRange.to_date,
      });
      showToast?.(
        `기간 수집을 완료했습니다. 기사 ${Number(result?.crawl_count || 0).toLocaleString()}건을 확인했습니다.`,
        "success"
      );
      await loadHealth();
    } catch (err) {
      setError(err.message);
      showToast?.("기간 수집을 완료하지 못했습니다. 잠시 후 다시 시도해 주세요.", "error");
    } finally {
      setReplaying(false);
    }
  }

  function useRunRange(run) {
    setReplayRange({
      from_date: localDateKey(run.window_start),
      to_date: localDateKey(run.window_end),
    });
    document.querySelector(".collection-replay-panel")?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  }

  return (
    <div className="collection-status-page">
      <section className="collection-status-summary">
        <div className="collection-summary-copy">
          <span className={`collection-status-pill ${latestStatus.tone}`}>
            {latestStatus.tone === "success" ? <CheckCircle2 size={15} /> : <AlertCircle size={15} />}
            {latestStatus.label}
          </span>
          <h3>{keywordName || "동국대학교"} 기사 수집 현황</h3>
          <p>{latestStatus.message}</p>
        </div>
        <div className="collection-summary-meta">
          <span>마지막 정상 수집</span>
          <strong>{formatDateTime(health?.last_success_at)}</strong>
          <small>{lastLoadedAt ? `${formatDateTime(lastLoadedAt)}에 화면 갱신` : "상태 확인 중"}</small>
        </div>
      </section>

      <div className="collection-status-controls">
        <label>
          <span>확인 기간</span>
          <select value={days} onChange={(event) => setDays(event.target.value)}>
            <option value="7">최근 7일</option>
            <option value="30">최근 30일</option>
            <option value="90">최근 90일</option>
          </select>
        </label>
        <button className="secondary" disabled={loading} onClick={() => loadHealth()} type="button">
          <RefreshCw className={loading ? "spin" : ""} size={16} />
          상태 새로고침
        </button>
      </div>

      {error && (
        <div className="collection-friendly-error" role="alert">
          <AlertCircle size={18} />
          <div>
            <strong>수집 상태를 불러오지 못했습니다</strong>
            <span>{error}</span>
          </div>
        </div>
      )}

      <div className="collection-auto-retry-note">
        <RefreshCw size={18} />
        <div>
          <strong>자동 재수집 사용 중</strong>
          <span>동국대·대학 교육·불교 종단 중 수집 결과가 비어 있으면 서버가 30분 간격으로 하루 최대 3회 다시 확인합니다.</span>
        </div>
      </div>

      <section className="collection-channel-section">
        <div className="collection-section-heading">
          <div>
            <h3>분야별 수집 상태</h3>
            <p>기사 수가 적거나 수집이 지연된 분야를 한눈에 확인할 수 있습니다.</p>
          </div>
          <span>최근 {days}일 기준</span>
        </div>
        <div className="collection-channel-list">
          {collectionGroups.map((group) => {
            const GroupIcon = group.icon;
            return (
              <article className="collection-channel-row" key={group.key}>
                <div className={`collection-channel-icon ${group.key}`}>
                  <GroupIcon size={20} />
                </div>
                <div className="collection-channel-copy">
                  <strong>{group.title}</strong>
                  <span>{group.description}</span>
                </div>
                <div className="collection-channel-count">
                  <strong>{group.discoveredCount.toLocaleString()}건</strong>
                  <span>검색 결과</span>
                </div>
                <span className={`collection-status-pill ${group.status.tone}`}>
                  {group.status.label}
                </span>
                <details className="collection-channel-details">
                  <summary aria-label={`${group.title} 세부 상태`}>
                    <ChevronDown size={16} />
                  </summary>
                  <div>
                    {group.sources.length ? group.sources.map((source) => (
                      <p key={source.name}>
                        <span>{sourceLabel(source.name)}</span>
                        <strong>성공 {Math.round(Number(source.success_rate || 0))}% · {Number(source.discovered_count || 0).toLocaleString()}건 확인</strong>
                      </p>
                    )) : (
                      <p><span>수집 기록</span><strong>아직 기록이 없습니다</strong></p>
                    )}
                  </div>
                </details>
              </article>
            );
          })}
        </div>
      </section>

      <section className="collection-replay-panel">
        <div className="collection-replay-heading">
          <CalendarRange size={21} />
          <div>
            <h3>기간 다시 수집</h3>
            <p>누락이 의심되는 날짜를 선택하면 해당 기간의 기사를 다시 찾아 저장합니다.</p>
          </div>
        </div>
        <div className="collection-replay-form">
          <label>
            <span>시작일</span>
            <input
              disabled={replaying}
              max={today}
              type="date"
              value={replayRange.from_date}
              onChange={(event) => setReplayRange((current) => ({ ...current, from_date: event.target.value }))}
            />
          </label>
          <label>
            <span>종료일</span>
            <input
              disabled={replaying}
              max={today}
              type="date"
              value={replayRange.to_date}
              onChange={(event) => setReplayRange((current) => ({ ...current, to_date: event.target.value }))}
            />
          </label>
          <button disabled={replaying || !keywordId} onClick={replayRangeArticles} type="button">
            {replaying ? <Loader2 className="spin" size={17} /> : <RotateCcw size={17} />}
            {replaying ? "수집 중..." : "이 기간 다시 수집"}
          </button>
        </div>
        {replaying && (
          <div className="collection-replay-progress" role="status" aria-live="polite">
            <Loader2 className="spin" size={18} />
            <div>
              <strong>선택한 기간의 기사를 다시 찾고 있습니다</strong>
              <span>수집이 끝나면 결과와 기사 수가 자동으로 갱신됩니다.</span>
            </div>
          </div>
        )}
        <p className="collection-replay-note">
          <Clock3 size={14} />
          수집에는 약 1~2분이 걸릴 수 있으며, 이미 저장된 동일 원문은 한 번만 유지됩니다.
        </p>
      </section>

      <section className="collection-history-section">
        <div className="collection-section-heading">
          <div>
            <h3>최근 수집 결과</h3>
            <p>최근에 확인한 날짜와 기사 수를 보여줍니다. 필요한 기간은 다시 수집할 수 있습니다.</p>
          </div>
          <span>{meaningfulRuns.length}건</span>
        </div>
        <div className="collection-history-list">
          {meaningfulRuns.map((run) => {
            const status = runStatus(run);
            return (
              <article className="collection-history-row" key={run.run_id}>
                <div className={`collection-history-state ${status.tone}`}>
                  {status.tone === "success" ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
                </div>
                <div className="collection-history-copy">
                  <strong>{formatDateRange(run.window_start, run.window_end)}</strong>
                  <span>{status.message}</span>
                </div>
                <div className="collection-history-count">
                  <strong>{Number(run.article_count || 0).toLocaleString()}건</strong>
                  <span>기사 확인</span>
                </div>
                <span className={`collection-status-pill ${status.tone}`}>{status.label}</span>
                <button className="secondary compact" onClick={() => useRunRange(run)} type="button">
                  <CalendarRange size={14} /> 기간 선택
                </button>
                <details className="collection-history-details">
                  <summary>세부 결과</summary>
                  <div>
                    {(run.sources || []).length ? (run.sources || []).map((source) => (
                      <p key={`${run.run_id}-${source.name}`}>
                        <span>{sourceLabel(source.name)}</span>
                        <strong>{runSourceStatus(source)} · {Number(source.discovered_count || 0).toLocaleString()}건 확인</strong>
                      </p>
                    )) : (
                      <p><span>수집 결과</span><strong>정상 완료</strong></p>
                    )}
                  </div>
                </details>
              </article>
            );
          })}
          {!loading && !meaningfulRuns.length && (
            <div className="collection-empty-state">
              <FileSearch size={22} />
              <strong>아직 수집 결과가 없습니다</strong>
              <span>기간 다시 수집을 실행하면 결과가 이곳에 표시됩니다.</span>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

export default CollectionStatusPanel;
