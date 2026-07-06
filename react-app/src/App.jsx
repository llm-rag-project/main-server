import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  BarChart3,
  Bot,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Download,
  ExternalLink,
  Eye,
  Loader2,
  Mail,
  MessageSquare,
  Maximize2,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { authStore, endpoints } from "./api";
import "./styles.css";

const sortOptions = [
  ["최신순", "published_at_desc"],
  ["오래된순", "published_at_asc"],
  ["중요도 높은순", "importance_desc"],
  ["중요도 낮은순", "importance_asc"],
  ["부정 기사 우선", "sentiment_negative_first"],
  ["긍정 기사 우선", "sentiment_positive_first"],
  ["홍보성 우선", "promotion_first"],
  ["일반 기사 우선", "organic_first"],
];

const medals = ["1", "2", "3", "4", "5"];
const chatStorageKey = "news_console_default_chat_id";

function makeJobId() {
  return crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
}

function keywordName(keyword) {
  return keyword?.keyword || keyword?.keyword_text || "이름 없음";
}

function formatCrawlInterval(minutes) {
  const value = Number(minutes || 1440);
  if (value % 1440 === 0) return `${value / 1440}일마다`;
  if (value % 60 === 0) return `${value / 60}시간마다`;
  return `${value}분마다`;
}

function emailSummary(keyword) {
  if (!keyword?.email_auto_send) return "이메일 발송 꺼짐";
  const count = keyword.email_recipients?.length || 0;
  return `${keyword.email_send_time || "08:30"} · 수신자 ${count}명`;
}

function emailConditionSummary(keyword) {
  const labels = {
    daily_summary: "매일 정기 리포트",
    risk_only: "위험 신호 발생 시",
    negative_or_risk: `부정 ${keyword?.alert_negative_rate_threshold ?? 25}% 이상 또는 고위험 기사`,
    activity_threshold: `기사 ${keyword?.alert_article_count_threshold ?? 10}건 이상`,
  };
  return labels[keyword?.email_condition_type] || labels.daily_summary;
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("ko-KR", { dateStyle: "medium", timeStyle: "short" });
}

function localDateKey(value = new Date()) {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function getArticleUrl(article) {
  return article?.original_url || article?.url || article?.link || "";
}

function normalizeScore(score) {
  if (score == null) return null;
  const value = Number(score);
  if (!Number.isFinite(value)) return null;
  return value <= 1 ? value * 100 : value;
}

function normalizeSentiment(value) {
  const text = String(value || "").toLowerCase();
  if (text.includes("부정") || text.includes("negative")) return "negative";
  if (text.includes("긍정") || text.includes("positive")) return "positive";
  if (text.includes("중립") || text.includes("neutral")) return "neutral";
  return "unknown";
}

function sumCounts(rows, predicate = () => true) {
  return rows.filter(predicate).reduce((total, row) => total + Number(row.count || row.article_count || row.total_count || 0), 0);
}

function sourceLabel(source) {
  const labels = {
    x: "X/Twitter",
    instagram: "Instagram",
    youtube: "YouTube",
    reddit: "Reddit",
    community: "Community",
  };
  return labels[source] || source || "Unknown";
}

function normalizeChatMessages(messages = []) {
  return messages.map((message) => ({
    role: message.role,
    content: message.content,
    created_at: message.created_at,
  }));
}

function EmptyState({ title, body }) {
  return (
    <div className="empty-state">
      <Sparkles size={20} />
      <strong>{title}</strong>
      <span>{body}</span>
    </div>
  );
}

function Toast({ toast, onClose }) {
  useEffect(() => {
    if (!toast) return undefined;
    const timer = setTimeout(onClose, 4200);
    return () => clearTimeout(timer);
  }, [toast, onClose]);
  if (!toast) return null;
  return <div className={`toast ${toast.type || "info"}`}>{toast.message}</div>;
}

function Sidebar({
  keywords,
  selectedKeywordId,
  setSelectedKeywordId,
  onCreateKeyword,
  onUpdateKeyword,
  onDeleteKeyword,
  loading,
  collapsed,
  setCollapsed,
}) {
  const defaultForm = {
    keyword: "",
    client_name: "",
    group_name: "",
    monitoring_type: "brand",
    priority_level: "normal",
    crawl_interval_minutes: 1440,
    crawl_limit: 10,
    email_auto_send: false,
    email_recipients: "",
    email_send_time: "08:30",
    email_condition_type: "daily_summary",
    alert_negative_rate_threshold: 25,
    alert_importance_threshold: 80,
    alert_article_count_threshold: 10,
    importance_criteria: "",
    competitor_keywords: "",
  };
  const [modalOpen, setModalOpen] = useState(false);
  const [editingKeyword, setEditingKeyword] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [keywordInput, setKeywordInput] = useState(defaultForm);
  const activeCount = keywords.filter((item) => item.is_active).length;

  function closeModal() {
    setModalOpen(false);
    setEditingKeyword(null);
    setKeywordInput(defaultForm);
  }

  function openCreateModal() {
    setEditingKeyword(null);
    setKeywordInput(defaultForm);
    setModalOpen(true);
  }

  function openEditModal(keyword) {
    setEditingKeyword(keyword);
    setKeywordInput({
      keyword: keywordName(keyword),
      client_name: keyword.client_name || "",
      group_name: keyword.group_name || "",
      monitoring_type: keyword.monitoring_type || "brand",
      priority_level: keyword.priority_level || "normal",
      crawl_interval_minutes: keyword.crawl_interval_minutes || 1440,
      crawl_limit: keyword.crawl_limit || 10,
      email_auto_send: Boolean(keyword.email_auto_send),
      email_recipients: (keyword.email_recipients || []).join("\n"),
      email_send_time: keyword.email_send_time || "08:30",
      email_condition_type: keyword.email_condition_type || "daily_summary",
      alert_negative_rate_threshold: keyword.alert_negative_rate_threshold ?? 25,
      alert_importance_threshold: keyword.alert_importance_threshold ?? 80,
      alert_article_count_threshold: keyword.alert_article_count_threshold ?? 10,
      importance_criteria: keyword.importance_criteria || "",
      competitor_keywords: "",
    });
    setModalOpen(true);
  }

  function submitKeyword(event) {
    event.preventDefault();
    const keyword = keywordInput.keyword.trim();
    if (!keyword) return;
    const recipients = keywordInput.email_recipients
      .replaceAll(",", "\n")
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);
    const competitorKeywords = keywordInput.competitor_keywords
      .replaceAll(",", "\n")
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);
    const groupName = keywordInput.group_name.trim() || (competitorKeywords.length ? `${keyword} 경쟁사 그룹` : "");

    const payload = {
      keyword,
      client_name: keywordInput.client_name.trim(),
      group_name: groupName,
      monitoring_type: keywordInput.monitoring_type,
      priority_level: keywordInput.priority_level,
      crawl_interval_minutes: Number(keywordInput.crawl_interval_minutes),
      crawl_limit: Number(keywordInput.crawl_limit),
      email_auto_send: keywordInput.email_auto_send,
      email_recipients: keywordInput.email_auto_send ? recipients : [],
      email_send_time: keywordInput.email_send_time,
      email_condition_type: keywordInput.email_condition_type,
      alert_negative_rate_threshold: Number(keywordInput.alert_negative_rate_threshold),
      alert_importance_threshold: Number(keywordInput.alert_importance_threshold),
      alert_article_count_threshold: Number(keywordInput.alert_article_count_threshold),
      importance_criteria: keywordInput.importance_criteria.trim(),
      competitor_keywords: competitorKeywords,
    };

    if (editingKeyword) onUpdateKeyword(editingKeyword.id, payload);
    else onCreateKeyword(payload);
    closeModal();
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    const deleted = await onDeleteKeyword(deleteTarget);
    if (deleted) setDeleteTarget(null);
  }

  return (
    <>
      <aside className={`sidebar ${collapsed ? "collapsed" : ""}`}>
        <div className="brand">
          <div className="brand-mark">N</div>
          {!collapsed && (
            <div>
              <strong>News Intelligence</strong>
              <span>AI 기사 모니터링</span>
            </div>
          )}
        </div>

        <section className="side-section">
          <button className="section-toggle" title={collapsed ? "키워드 목차 펼치기" : "키워드 목차 접기"} onClick={() => setCollapsed((value) => !value)}>
            {collapsed ? (
              <ChevronRight size={17} />
            ) : (
              <>
                <span>키워드 목차</span>
                {loading ? <Loader2 className="spin" size={15} /> : <em>{keywords.length}</em>}
                <ChevronDown size={17} />
              </>
            )}
          </button>

          {!collapsed && (
            <>
              <div className="keyword-toolbar">
                <div>
                  <strong>{activeCount}개 활성</strong>
                  <span>등록 키워드 {keywords.length}개</span>
                </div>
                <button className="primary compact" onClick={openCreateModal} type="button">
                  <Plus size={16} /> 키워드 추가
                </button>
              </div>

              <div className="keyword-checklist">
                {keywords.map((keyword) => {
                  const selected = keyword.id === selectedKeywordId;
                  const monitoringLabels = {
                    brand: "브랜드",
                    competitor: "경쟁사",
                    campaign: "캠페인",
                    issue: "이슈",
                  };
                  const priorityLabels = {
                    low: "낮음",
                    normal: "일반",
                    high: "중요",
                    critical: "긴급",
                  };
                  return (
                    <div className={`toc-row ${selected ? "selected" : ""}`} key={keyword.id}>
                      <button className="toc-select" onClick={() => setSelectedKeywordId(keyword.id)} type="button">
                        <span className="toc-title">{keywordName(keyword)}</span>
                        <span className="toc-meta">
                          <em>{keyword.client_name || "클라이언트 미지정"}</em>
                          <em>{keyword.group_name || "그룹 미지정"}</em>
                        </span>
                        <span className="toc-chips">
                          <b>{monitoringLabels[keyword.monitoring_type] || keyword.monitoring_type || "브랜드"}</b>
                          <b className={`priority-${keyword.priority_level || "normal"}`}>{priorityLabels[keyword.priority_level] || "일반"}</b>
                          {keyword.email_auto_send && <b className="mail-chip">메일</b>}
                        </span>
                        <span className="toc-settings">
                          <small>확인 범위 {formatCrawlInterval(keyword.crawl_interval_minutes)}</small>
                          <small>한 번에 {keyword.crawl_limit || 10}개</small>
                          {keyword.importance_criteria && <small>중요도 기준 설정됨</small>}
                          <small>{emailSummary(keyword)}</small>
                        </span>
                      </button>
                      <div className="toc-actions">
                        <button className="ghost" title="설정 수정" onClick={() => openEditModal(keyword)} type="button">
                          <Pencil size={14} />
                        </button>
                        <button className="ghost danger" title="삭제" onClick={() => setDeleteTarget(keyword)} type="button">
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}

        </section>
      </aside>

      {modalOpen && (
        <div className="modal-backdrop" role="presentation">
          <form className="keyword-modal" onSubmit={submitKeyword}>
            <div className="modal-heading">
              <div>
                <strong>{editingKeyword ? "키워드 설정 수정" : "키워드 추가"}</strong>
                <span>{editingKeyword ? "확인 범위, 기사 수, 리포트 발송 조건을 수정합니다." : "모니터링 범위와 리포트 발송 조건을 함께 설정합니다."}</span>
              </div>
              <button className="ghost" onClick={closeModal} title="닫기" type="button">
                <X size={18} />
              </button>
            </div>

            <label className="field full">
              <span>키워드</span>
              <input
                autoFocus
                value={keywordInput.keyword}
                onChange={(event) => setKeywordInput((prev) => ({ ...prev, keyword: event.target.value }))}
                placeholder="예: 반도체 수출, OpenAI, 환율"
              />
            </label>

            {!editingKeyword && (
              <label className="field full">
                <span>경쟁사 키워드</span>
                <textarea
                  value={keywordInput.competitor_keywords}
                  onChange={(event) => setKeywordInput((prev) => ({ ...prev, competitor_keywords: event.target.value }))}
                  placeholder={"예: 경쟁사 A\n경쟁사 B\n경쟁 브랜드 캠페인명"}
                />
                <small>입력한 키워드는 같은 그룹의 경쟁사 비교 키워드로 함께 등록되고, 초기 기사 수집까지 실행됩니다.</small>
              </label>
            )}

            <div className="modal-grid">
              <label className="field">
                <span>클라이언트</span>
                <input
                  value={keywordInput.client_name}
                  onChange={(event) => setKeywordInput((prev) => ({ ...prev, client_name: event.target.value }))}
                  placeholder="예: A브랜드, B기업"
                />
              </label>
              <label className="field">
                <span>그룹</span>
                <input
                  value={keywordInput.group_name}
                  onChange={(event) => setKeywordInput((prev) => ({ ...prev, group_name: event.target.value }))}
                  placeholder="예: 경쟁사 비교, 신제품 캠페인"
                />
              </label>
            </div>

            <div className="modal-grid">
              <label className="field">
                <span>모니터링 목적</span>
                <select
                  value={keywordInput.monitoring_type}
                  onChange={(event) => setKeywordInput((prev) => ({ ...prev, monitoring_type: event.target.value }))}
                >
                  <option value="brand">단일 브랜드 현황</option>
                  <option value="competitor">경쟁사 비교</option>
                  <option value="campaign">캠페인 성과</option>
                  <option value="issue">이슈/위기 감지</option>
                </select>
              </label>
              <label className="field">
                <span>업무 우선순위</span>
                <select
                  value={keywordInput.priority_level}
                  onChange={(event) => setKeywordInput((prev) => ({ ...prev, priority_level: event.target.value }))}
                >
                  <option value="normal">일반</option>
                  <option value="high">중요</option>
                  <option value="critical">긴급</option>
                  <option value="low">낮음</option>
                </select>
              </label>
            </div>

            <div className="modal-grid">
              <label className="field">
                <span>확인 범위</span>
                <select
                  value={keywordInput.crawl_interval_minutes}
                  onChange={(event) => setKeywordInput((prev) => ({ ...prev, crawl_interval_minutes: Number(event.target.value) }))}
                >
                  <option value={60}>최근 1시간 기사 확인</option>
                  <option value={180}>최근 3시간 기사 확인</option>
                  <option value={360}>최근 6시간 기사 확인</option>
                  <option value={720}>최근 12시간 기사 확인</option>
                  <option value={1440}>최근 1일 기사 확인</option>
                  <option value={10080}>최근 7일 기사 확인</option>
                </select>
              </label>
              <label className="field">
                <span>한 번에 가져올 기사 수</span>
                <input
                  min="1"
                  max="100"
                  type="number"
                  value={keywordInput.crawl_limit}
                  onChange={(event) => setKeywordInput((prev) => ({ ...prev, crawl_limit: Number(event.target.value) }))}
                />
              </label>
            </div>

            <label className="field full">
              <span>중요도 기준</span>
              <textarea
                value={keywordInput.importance_criteria}
                onChange={(event) => setKeywordInput((prev) => ({ ...prev, importance_criteria: event.target.value }))}
                placeholder={"예: 임원/기관장 발언, 위기 이슈, 경쟁사 직접 비교, 매출 영향 가능성이 있는 기사는 높게 평가\n단순 행사 안내나 반복 보도자료는 낮게 평가"}
              />
            </label>

            <div className="setting-block">
              <label className="toggle-line">
                <input
                  checked={keywordInput.email_auto_send}
                  onChange={(event) => setKeywordInput((prev) => ({ ...prev, email_auto_send: event.target.checked }))}
                  type="checkbox"
                />
                <span>리포트 이메일 자동 발송</span>
              </label>

              <div className="modal-grid">
                <label className="field">
                  <span>발송 시간</span>
                  <input
                    disabled={!keywordInput.email_auto_send}
                    type="time"
                    value={keywordInput.email_send_time}
                    onChange={(event) => setKeywordInput((prev) => ({ ...prev, email_send_time: event.target.value }))}
                  />
                </label>
                <label className="field">
                  <span>수신 이메일</span>
                  <textarea
                    disabled={!keywordInput.email_auto_send}
                    value={keywordInput.email_recipients}
                    onChange={(event) => setKeywordInput((prev) => ({ ...prev, email_recipients: event.target.value }))}
                    placeholder="team@example.com&#10;ops@example.com"
                  />
                </label>
              </div>

              <div className="condition-box">
                <label className="field full">
                  <span>리포트 발송 조건</span>
                  <select
                    disabled={!keywordInput.email_auto_send}
                    value={keywordInput.email_condition_type}
                    onChange={(event) => setKeywordInput((prev) => ({ ...prev, email_condition_type: event.target.value }))}
                  >
                    <option value="daily_summary">매일 정기 리포트 발송</option>
                    <option value="risk_only">위험 신호가 있을 때만 발송</option>
                    <option value="negative_or_risk">부정 비중 또는 고위험 기사 기준 발송</option>
                    <option value="activity_threshold">기사량이 기준 이상일 때 발송</option>
                  </select>
                </label>
                <div className="modal-grid">
                  <label className="field">
                    <span>부정 비중 기준</span>
                    <input
                      disabled={!keywordInput.email_auto_send}
                      min="0"
                      max="100"
                      type="number"
                      value={keywordInput.alert_negative_rate_threshold}
                      onChange={(event) => setKeywordInput((prev) => ({ ...prev, alert_negative_rate_threshold: Number(event.target.value) }))}
                    />
                  </label>
                  <label className="field">
                    <span>고위험 기사 기준</span>
                    <input
                      disabled={!keywordInput.email_auto_send}
                      min="0"
                      max="100"
                      type="number"
                      value={keywordInput.alert_importance_threshold}
                      onChange={(event) => setKeywordInput((prev) => ({ ...prev, alert_importance_threshold: Number(event.target.value) }))}
                    />
                  </label>
                </div>
                <label className="field full">
                  <span>기사량 기준</span>
                  <input
                    disabled={!keywordInput.email_auto_send}
                    min="1"
                    max="1000"
                    type="number"
                    value={keywordInput.alert_article_count_threshold}
                    onChange={(event) => setKeywordInput((prev) => ({ ...prev, alert_article_count_threshold: Number(event.target.value) }))}
                  />
                </label>
                <p className="condition-help">자동 리포트는 선택한 조건을 기준으로 발송 여부를 판단합니다. 정기 발송 외에는 부정 비중, 중요도, 기사량 신호를 함께 참고합니다.</p>
              </div>
            </div>

            <div className="modal-actions">
              <button className="secondary" onClick={closeModal} type="button">취소</button>
              <button className="primary" disabled={loading || !keywordInput.keyword.trim()} type="submit">
                {loading ? <Loader2 className="spin" size={16} /> : editingKeyword ? <Pencil size={16} /> : <Plus size={16} />}
                {editingKeyword ? "수정" : "등록"}
              </button>
            </div>
          </form>
        </div>
      )}

      {deleteTarget && (
        <div className="modal-backdrop" role="presentation">
          <div className="keyword-modal delete-modal" role="dialog" aria-modal="true" aria-labelledby="delete-keyword-title">
            <div className="modal-heading">
              <div>
                <strong id="delete-keyword-title">키워드 삭제 확인</strong>
                <span>삭제 요청을 처리하기 전에 영향 범위를 한 번 더 확인합니다.</span>
              </div>
              <button className="ghost" onClick={() => setDeleteTarget(null)} title="닫기" type="button">
                <X size={18} />
              </button>
            </div>

            <div className="delete-summary">
              <strong>{keywordName(deleteTarget)}</strong>
              <span>확인 범위: {formatCrawlInterval(deleteTarget.crawl_interval_minutes)}</span>
              <span>한 번에 가져올 기사 수: {deleteTarget.crawl_limit || 10}개</span>
              <span>{emailSummary(deleteTarget)}</span>
              <span>발송 조건: {emailConditionSummary(deleteTarget)}</span>
            </div>

            <div className="delete-notice">
              <strong>삭제하면 이렇게 정리됩니다.</strong>
              <p>좌측 키워드 목차에서 제거되고, 이후 자동 확인과 이메일 보고 대상에서 제외됩니다.</p>
              <p>이 키워드로 등록된 Dify 지식 문서도 함께 삭제를 시도합니다.</p>
              <p>이미 수집된 기사와 요약 데이터는 다른 키워드와 연결되어 있을 수 있어 즉시 일괄 삭제하지 않습니다.</p>
            </div>

            <div className="modal-actions">
              <button className="secondary" onClick={() => setDeleteTarget(null)} type="button">취소</button>
              <button className="danger solid" disabled={loading} onClick={confirmDelete} type="button">
                {loading ? <Loader2 className="spin" size={16} /> : <Trash2 size={16} />}
                삭제
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
function LoginGate({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await endpoints.login(email, password);
      authStore.setTokens(result.access_token || result.accessToken, result.refresh_token || result.refreshToken);
      onLogin();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-shell">
      <form className="login-card" onSubmit={submit}>
        <div className="brand-mark large">N</div>
        <h1>News Intelligence</h1>
        <p>키워드 기반 기사 수집, AI 중요도 분석, 리포트 발송까지 한 곳에서 관리합니다.</p>
        <input autoComplete="email" placeholder="이메일" type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
        <input
          autoComplete="current-password"
          placeholder="비밀번호"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        {error && <div className="form-error">{error}</div>}
        <button className="primary" disabled={busy} type="submit">
          {busy ? <Loader2 className="spin" size={17} /> : <CheckCircle2 size={17} />}
          로그인
        </button>
      </form>
    </main>
  );
}

function Summary({ selectedKeyword, articlePage, importancePage }) {
  return (
    <section className="summary-grid">
      <div className="metric-panel">
        <span>모니터링 설정</span>
        <strong>{selectedKeyword ? formatCrawlInterval(selectedKeyword.crawl_interval_minutes) : "-"}</strong>
        <small>한 번에 {selectedKeyword?.crawl_limit || 10}개 확인</small>
      </div>
      <div className="metric-panel">
        <span>수집 기사</span>
        <strong>{articlePage?.total ?? 0}</strong>
        <small>중요도 분석 {importancePage?.total ?? 0}건</small>
      </div>
      <div className="metric-panel">
        <span>리포트 발송</span>
        <strong>{selectedKeyword?.email_auto_send ? "자동" : "수동"}</strong>
        <small>{selectedKeyword ? `${emailSummary(selectedKeyword)} · ${emailConditionSummary(selectedKeyword)}` : "키워드를 선택하세요"}</small>
      </div>
    </section>
  );
}

function Articles({ selectedKeywordId, topItems, showToast, refreshSummary }) {
  const [articles, setArticles] = useState([]);
  const [pageInfo, setPageInfo] = useState(null);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState(sortOptions[0][1]);
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(20);
  const [busy, setBusy] = useState(false);
  const [running, setRunning] = useState("");
  const [details, setDetails] = useState({});
  const [deleteArticleTarget, setDeleteArticleTarget] = useState(null);
  const rankMap = useMemo(() => new Map(topItems.map((item, index) => [item.article_id, index + 1])), [topItems]);

  async function loadArticles() {
    if (!selectedKeywordId) return;
    setBusy(true);
    try {
      const data = await endpoints.articles({
        keyword_id: selectedKeywordId,
        page,
        size,
        sort,
        ...(query.trim() ? { q: query.trim() } : {}),
      });
      setArticles(data.items || []);
      setPageInfo(data.page_info);
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    loadArticles();
  }, [selectedKeywordId, page, size, sort]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setPage(1);
      loadArticles();
    }, 350);
    return () => clearTimeout(timer);
  }, [query]);

  async function runCrawl() {
    setRunning("crawl");
    try {
      const result = await endpoints.runCrawl(selectedKeywordId);
      await loadArticles();
      refreshSummary?.();
      showToast(`오늘 날짜 기준 새 기사 확인을 요청했습니다. 수집 ${result.crawl_count ?? 0}건`, "success");
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      setRunning("");
    }
  }

  async function toggleDetail(articleId) {
    if (details[articleId]) {
      setDetails((prev) => ({ ...prev, [articleId]: null }));
      return;
    }
    try {
      const data = await endpoints.articleDetail(articleId);
      setDetails((prev) => ({ ...prev, [articleId]: data }));
    } catch (err) {
      showToast(err.message, "error");
    }
  }

  async function confirmDeleteArticle() {
    if (!deleteArticleTarget) return;
    setRunning("delete");
    try {
      await endpoints.deleteArticle(deleteArticleTarget.id);
      showToast("기사와 관련 분석 데이터를 삭제했습니다.", "success");
      setDeleteArticleTarget(null);
      await loadArticles();
      refreshSummary?.();
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      setRunning("");
    }
  }

  return (
    <section className="workspace">
      <div className="article-top-grid">
        <div className="toolbar article-toolbar">
          <button className="secondary" disabled={running === "crawl"} onClick={runCrawl}>
            {running === "crawl" ? <Loader2 className="spin" size={16} /> : <RefreshCw size={16} />}
            새 기사 확인
          </button>
          <div className="searchbox">
            <Search size={16} />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="기사 검색" />
          </div>
          <select value={sort} onChange={(event) => setSort(event.target.value)}>
            {sortOptions.map(([label, value]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <select value={size} onChange={(event) => setSize(Number(event.target.value))}>
            {[10, 20, 50].map((value) => (
              <option key={value} value={value}>
                {value}개씩
              </option>
            ))}
          </select>
        </div>

        <div className="article-priority-panel">
          <div className="panel-heading">
            <strong>우선 확인 기사</strong>
            <span>AI 중요도 Top 5</span>
          </div>
          <div className="ranking-list article-ranking-list">
            {topItems.length === 0 ? (
              <span className="muted">아직 중요도 데이터가 없습니다.</span>
            ) : (
              topItems.slice(0, 5).map((item, index) => (
                <a href={item.url || "#"} className="rank-item" key={`${item.article_id}-${index}`} target="_blank" rel="noreferrer">
                  <b>{medals[index]}</b>
                  <span>{item.title || "제목 없음"}</span>
                  <em>{Number(normalizeScore(item.score) || 0).toFixed(1)}</em>
                </a>
              ))
            )}
          </div>
        </div>
      </div>

      {busy ? (
        <div className="loading-line">
          <Loader2 className="spin" size={18} /> 기사 목록을 불러오는 중
        </div>
      ) : articles.length === 0 ? (
        <EmptyState title="표시할 기사가 없습니다" body="키워드를 확인하거나 새 기사 확인을 실행해 보세요." />
      ) : (
        <div className="article-list">
          {articles.map((article) => {
            const articleId = article.id;
            const url = getArticleUrl(article);
            const rank = rankMap.get(articleId);
            const score = normalizeScore(article.importance ?? article.score);
            const summary = article.summary;
            const detail = details[articleId];
            return (
              <article className="article-card" key={articleId}>
                <div className={`article-main ${rank ? "has-rank" : "no-rank"}`}>
                  {rank && <div className="rank-badge">{rank}</div>}
                  <div>
                    <h3>{article.title || "제목 없음"}</h3>
                    <div className="meta">
                      <span>{article.source || article.publisher || "출처 없음"}</span>
                      <span>{formatDate(article.published_at)}</span>
                      {article.sentiment && <span className="pill">{article.sentiment}</span>}
                      {article.is_promotion === true && <span className="pill warning">광고성</span>}
                    </div>
                    {summary && <p className="article-summary">{summary}</p>}
                  </div>
                  <div className="score-chip">
                    <span>중요도</span>
                    <strong>{score == null ? "-" : score.toFixed(1)}</strong>
                  </div>
                </div>

                <div className="article-actions refined">
                  <button title="기사 내용을 펼쳐봅니다" onClick={() => toggleDetail(articleId)}>
                    <Eye size={15} />
                    {detail ? "닫기" : "내용 보기"}
                  </button>
                  {url && (
                    <a className="button-link source-link" href={url} target="_blank" rel="noreferrer" title="원문 열기">
                      <ExternalLink size={15} />
                      원문
                    </a>
                  )}
                  <button className="danger ghost-action" title="기사 삭제" onClick={() => setDeleteArticleTarget(article)} type="button">
                    <Trash2 size={15} />
                    삭제
                  </button>
                </div>

                {detail && (
                  <div className="reader-panel">
                    <strong>기사 내용</strong>
                    <p>{detail.content || detail.summary || article.summary || "표시할 본문이 없습니다."}</p>
                  </div>
                )}

              </article>
            );
          })}
        </div>
      )}

      <div className="pagination">
        <button disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>
          이전
        </button>
        <span>
          {page} / {Math.max(1, Math.ceil((pageInfo?.total || 0) / size))}
        </span>
        <button disabled={!pageInfo?.has_next} onClick={() => setPage((value) => value + 1)}>
          다음
        </button>
      </div>

      {deleteArticleTarget && (
        <div className="modal-backdrop" role="presentation">
          <div className="keyword-modal delete-modal" role="dialog" aria-modal="true" aria-labelledby="delete-article-title">
            <div className="modal-heading">
              <div>
                <strong id="delete-article-title">기사 삭제 확인</strong>
                <span>삭제하면 기사 목록과 관련 분석 결과에서 제거됩니다.</span>
              </div>
              <button className="ghost" onClick={() => setDeleteArticleTarget(null)} title="닫기" type="button">
                <X size={18} />
              </button>
            </div>
            <div className="delete-summary">
              <strong>{deleteArticleTarget.title || "제목 없음"}</strong>
              <span>{deleteArticleTarget.source || "출처 없음"} · {formatDate(deleteArticleTarget.published_at)}</span>
            </div>
            <div className="delete-notice">
              <strong>삭제 범위</strong>
              <p>기사 원문, 키워드 연결, 요약, 중요도, 감성/홍보성 분석, 피드백 데이터가 함께 정리됩니다.</p>
              <p>삭제 후에는 현재 목록과 통계에서 제외됩니다.</p>
            </div>
            <div className="modal-actions">
              <button className="secondary" disabled={running === "delete"} onClick={() => setDeleteArticleTarget(null)} type="button">취소</button>
              <button className="danger solid" disabled={running === "delete"} onClick={confirmDeleteArticle} type="button">
                {running === "delete" ? <Loader2 className="spin" size={16} /> : <Trash2 size={16} />}
                삭제
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function Chat({
  chatId,
  conversationId,
  setConversationId,
  messages,
  setMessages,
  ensureChat,
  onReset,
  selectedKeywordName,
  selectedKeywordId,
  showToast,
}) {
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    ensureChat();
  }, [selectedKeywordId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function submit(event) {
    event.preventDefault();
    if (!input.trim()) return;
    const activeChatId = chatId || (await ensureChat());
    if (!activeChatId) return;

    const prompt = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: prompt }]);
    setBusy(true);
    try {
      const data = await endpoints.sendMessage(activeChatId, { message: prompt, article_id: null, conversation_id: conversationId });
      setConversationId(data.conversation_id || "");
      setMessages((prev) => [...prev, { role: "assistant", content: data.answer || "응답이 비어 있습니다." }]);
    } catch (err) {
      showToast(err.message, "error");
      setMessages((prev) => [...prev, { role: "assistant", content: `요청 실패: ${err.message}` }]);
    } finally {
      setBusy(false);
    }
  }

  function ChatMessageContent({ content }) {
    const blocks = String(content || "")
      .split(/\n{2,}/)
      .map((block) => block.trim())
      .filter(Boolean);

    return (
      <>
        {(blocks.length ? blocks : [""]).map((block, index) => (
          <p key={`${block.slice(0, 18)}-${index}`}>{block}</p>
        ))}
      </>
    );
  }

  return (
    <section className="chat-panel single-session">
      <div className="panel-heading chat-heading">
        <div>
          <strong>{selectedKeywordName ? `${selectedKeywordName} AI 채팅` : "AI 채팅"}</strong>
          <span>선택한 키워드별로 별도 대화 세션이 유지됩니다.</span>
        </div>
        <button className="secondary" disabled={!chatId || busy} onClick={onReset} type="button">
          <RefreshCw size={15} /> 초기화
        </button>
      </div>
      <div className="chat-scroll">
        {messages.length === 0 && <EmptyState title="대화를 시작하세요" body="이 키워드의 기사 흐름, 리스크, 보고 방향을 바로 물어볼 수 있습니다." />}
        {messages.map((message, index) => (
          <div className={`message ${message.role}`} key={`${message.role}-${index}`}>
            <div className="message-avatar">{message.role === "user" ? "나" : "AI"}</div>
            <div className="message-body">
              <span>{message.role === "user" ? "내 질문" : "AI 브리핑"}</span>
              <div className="message-bubble">
                <ChatMessageContent content={message.content} />
              </div>
            </div>
          </div>
        ))}
        {busy && (
          <div className="message assistant">
            <div className="message-avatar">AI</div>
            <div className="message-body">
              <span>AI 브리핑</span>
              <div className="message-bubble loading-bubble">
                <p><Loader2 className="spin inline" size={16} /> 응답 생성 중</p>
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <form className="chat-input" onSubmit={submit}>
        <input value={input} onChange={(event) => setInput(event.target.value)} placeholder="뉴스 흐름, 리스크, 요약 방향을 질문하세요" />
        <button className="primary" disabled={busy} type="submit">
          전송
        </button>
      </form>
    </section>
  );
}

function Stats({ selectedKeywordId, selectedKeywordName, showToast }) {
  const [briefTab, setBriefTab] = useState("current");
  const [days, setDays] = useState(7);
  const [articleStats, setArticleStats] = useState({});
  const [analysisStats, setAnalysisStats] = useState({});
  const [volume, setVolume] = useState([]);
  const [volumeTrend, setVolumeTrend] = useState([]);
  const [dailyHourlyArticles, setDailyHourlyArticles] = useState([]);
  const [dailySocialMetrics, setDailySocialMetrics] = useState([]);
  const [priorityArticles, setPriorityArticles] = useState([]);
  const [dailyArticles, setDailyArticles] = useState([]);
  const [dailyPage, setDailyPage] = useState(null);
  const [expandedDailyArticleId, setExpandedDailyArticleId] = useState(null);
  const [dailyArticleDetails, setDailyArticleDetails] = useState({});
  const [pending, setPending] = useState(0);
  const [busy, setBusy] = useState(false);
  const [emails, setEmails] = useState("");
  const [expandedChart, setExpandedChart] = useState(null);

  async function load() {
    setBusy(true);
    try {
      const yesterdayKey = localDateKey(new Date(Date.now() - 24 * 60 * 60 * 1000));
      const dailyArticleParams = {
        page: 1,
        size: 100,
        sort: "importance_desc",
        from: yesterdayKey,
        to: yesterdayKey,
      };
      if (selectedKeywordId) dailyArticleParams.keyword_id = selectedKeywordId;
      const [articles, analysis, searchVolume, searchTrend, pendingData, priorityData, dailyData, dailyHourlyData, dailySocialData] = await Promise.all([
        endpoints.articleStats(days),
        endpoints.analysisStats(days),
        endpoints.searchVolume(),
        endpoints.searchVolumeTrend(days * 24),
        endpoints.pendingAnalysis(),
        selectedKeywordId
          ? endpoints.articles({ keyword_id: selectedKeywordId, page: 1, size: 8, sort: "importance_desc" })
          : Promise.resolve({ items: [] }),
        endpoints.articles(dailyArticleParams),
        endpoints.articleHourlyStats(yesterdayKey, selectedKeywordId),
        endpoints.dailySocialStats(yesterdayKey, selectedKeywordId),
      ]);
      setArticleStats(articles || {});
      setAnalysisStats(analysis || {});
      setVolume(searchVolume || []);
      setVolumeTrend(searchTrend || []);
      setDailyHourlyArticles(dailyHourlyData || []);
      setDailySocialMetrics(dailySocialData || []);
      setPending(pendingData?.pending_count || 0);
      setPriorityArticles(priorityData.items || []);
      setDailyArticles(dailyData.items || []);
      setDailyPage(dailyData.page_info || null);
      setExpandedDailyArticleId(null);
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    load();
  }, [days, selectedKeywordId]);

  async function downloadReport() {
    try {
      const response = await endpoints.report(selectedKeywordId);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      const safeKeyword = (selectedKeywordName || "news_report").replace(/[\\/:*?"<>|]/g, "_");
      anchor.download = `${safeKeyword}_report_${new Date().toISOString().slice(0, 10)}.xlsx`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      showToast(err.message, "error");
    }
  }

  async function sendEmail() {
    const toEmails = emails.replaceAll(",", "\n").split("\n").map((item) => item.trim()).filter(Boolean);
    if (!toEmails.length) {
      showToast("수신 이메일을 입력해 주세요.", "error");
      return;
    }
    setBusy(true);
    try {
      await endpoints.emailReport({ to_emails: toEmails, keyword_id: selectedKeywordId, keyword_name: selectedKeywordName });
      showToast("리포트 이메일을 발송했습니다.", "success");
      setEmails("");
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function toggleDailyArticle(article) {
    const articleId = article?.id;
    if (!articleId) return;

    if (expandedDailyArticleId === articleId) {
      setExpandedDailyArticleId(null);
      return;
    }

    setExpandedDailyArticleId(articleId);
    if (dailyArticleDetails[articleId]) return;

    try {
      const detail = await endpoints.articleDetail(articleId);
      setDailyArticleDetails((prev) => ({ ...prev, [articleId]: detail }));
    } catch (err) {
      showToast(err.message, "error");
    }
  }

  const byKeyword = articleStats.by_keyword || [];
  const byDate = articleStats.by_keyword_date || [];
  const totalByDate = articleStats.by_date || [];
  const byCollectedDate = articleStats.by_keyword_collected_date || [];
  const totalCollectedDate = articleStats.by_collected_date || [];
  const keywordInsights = articleStats.keyword_insights || [];
  const sentiment = analysisStats.sentiment_by_keyword || [];
  const promotion = analysisStats.promotion_by_keyword || [];
  const selectedKeywordLabel = selectedKeywordName || "전체 브랜드";
  const selectedKeywordStats = selectedKeywordName ? byKeyword.filter((row) => row.keyword_text === selectedKeywordName) : byKeyword;
  const selectedTrend = selectedKeywordName ? byDate.filter((row) => row.keyword_text === selectedKeywordName) : byDate;
  const selectedSentiment = selectedKeywordName ? sentiment.filter((row) => row.keyword_text === selectedKeywordName) : sentiment;
  const selectedPromotion = selectedKeywordName ? promotion.filter((row) => row.keyword_text === selectedKeywordName) : promotion;
  const selectedVolume = selectedKeywordName ? volume.find((row) => row.keyword_text === selectedKeywordName) : null;
  const selectedVolumeTrend = (selectedKeywordName ? volumeTrend.filter((row) => row.keyword_text === selectedKeywordName) : volumeTrend)
    .map((row) => ({
      ...row,
      hour: row.sampled_at
        ? new Date(row.sampled_at).toLocaleString("ko-KR", { month: "2-digit", day: "2-digit", hour: "2-digit" })
        : "",
    }));
  const selectedInsight = selectedKeywordName ? keywordInsights.find((row) => row.keyword_text === selectedKeywordName) : null;
  const socialSources = (selectedVolume?.social_sources || []).map((item) => ({ ...item, source_label: sourceLabel(item.source) }));
  const dailySocialRows = dailySocialMetrics.map((item) => ({
    ...item,
    source_label: sourceLabel(item.source),
    count: Number(item.mention_count || 0),
  }));
  const dailySocialTotal = dailySocialRows.reduce((total, item) => total + Number(item.count || 0), 0);
  const socialTotal = selectedVolume?.social_total_count || 0;
  const socialNegative = selectedVolume?.social_negative_hint_count || 0;
  const socialPositive = selectedVolume?.social_positive_hint_count || 0;
  const socialNegativeRate = socialTotal ? Math.round((socialNegative / socialTotal) * 100) : 0;
  const mentionCount = sumCounts(selectedKeywordStats);
  const positiveCount = sumCounts(selectedSentiment, (row) => normalizeSentiment(row.sentiment) === "positive");
  const negativeCount = sumCounts(selectedSentiment, (row) => normalizeSentiment(row.sentiment) === "negative");
  const neutralCount = sumCounts(selectedSentiment, (row) => normalizeSentiment(row.sentiment) === "neutral");
  const analyzedSentimentCount = positiveCount + negativeCount + neutralCount;
  const negativeRate = analyzedSentimentCount ? Math.round((negativeCount / analyzedSentimentCount) * 100) : 0;
  const positiveRate = analyzedSentimentCount ? Math.round((positiveCount / analyzedSentimentCount) * 100) : 0;
  const promotionCount = sumCounts(
    selectedPromotion,
    (row) => row.is_promotion === true || String(row.promotion || "").includes("광고")
  );
  const promotionTotal = sumCounts(selectedPromotion);
  const promotionRate = promotionTotal ? Math.round((promotionCount / promotionTotal) * 100) : 0;
  const earnedRate = promotionTotal ? Math.max(0, 100 - promotionRate) : 0;
  const newsSearchCount = Number(selectedVolume?.total_count || 0);
  const snsToNewsRatio = newsSearchCount ? Math.round((socialTotal / newsSearchCount) * 100) : null;
  const latestTrendCount = selectedTrend.length ? Number(selectedTrend[selectedTrend.length - 1].article_count || 0) : 0;
  const previousTrendCount = selectedTrend.length > 1 ? Number(selectedTrend[selectedTrend.length - 2].article_count || 0) : 0;
  const trendDelta = latestTrendCount - previousTrendCount;
  const baseDateKey = localDateKey(new Date(Date.now() - 24 * 60 * 60 * 1000));
  const previousBaseDateKey = localDateKey(new Date(Date.now() - 2 * 24 * 60 * 60 * 1000));
  const yesterdayKey = baseDateKey;
  const publishedDateRows = selectedKeywordName ? selectedTrend : totalByDate;
  const baseDateArticleTotal = dailyPage?.total ?? publishedDateRows.find((row) => row.date === baseDateKey)?.article_count ?? 0;
  const previousBaseDateTotal = publishedDateRows.find((row) => row.date === previousBaseDateKey)?.article_count ?? 0;
  const dailyDelta = Number(baseDateArticleTotal || 0) - Number(previousBaseDateTotal || 0);
  const baseDateArticleHourlyRows = dailyHourlyArticles.map((row) => ({
    ...row,
    hour: row.hour ? `${row.hour.slice(11, 13)}시` : "",
    total_count: Number(row.article_count || 0),
  }));
  const baseDateArticleHourlyTotal = baseDateArticleHourlyRows.reduce((total, row) => total + Number(row.total_count || 0), 0);
  const baseDateArticlePeak = baseDateArticleHourlyRows.reduce((max, row) => Math.max(max, Number(row.article_count || 0)), 0);
  const dailyImportantArticles = dailyArticles;
  const dailyLeadArticle = dailyImportantArticles[0];
  const dailyPositiveCount = dailyArticles.filter((article) => normalizeSentiment(article.sentiment) === "positive").length;
  const dailyNegativeCount = dailyArticles.filter((article) => normalizeSentiment(article.sentiment) === "negative").length;
  const dailyNeutralCount = dailyArticles.filter((article) => normalizeSentiment(article.sentiment) === "neutral").length;
  const dailyPromotionCount = dailyArticles.filter((article) => article.is_promotion === true).length;
  const dailyAnalyzedCount = dailyPositiveCount + dailyNegativeCount + dailyNeutralCount;
  const dailyUnknownCount = Math.max(0, Number(baseDateArticleTotal || 0) - dailyAnalyzedCount);
  const dailyNegativeRate = dailyAnalyzedCount ? Math.round((dailyNegativeCount / dailyAnalyzedCount) * 100) : 0;
  const dailyPromotionRate = baseDateArticleTotal ? Math.round((dailyPromotionCount / baseDateArticleTotal) * 100) : 0;
  const dailySignalData = [
    { label: "긍정", count: dailyPositiveCount },
    { label: "중립", count: dailyNeutralCount },
    { label: "부정", count: dailyNegativeCount },
    { label: "미분석", count: dailyUnknownCount },
  ];
  const dailyRisks = [
    dailyNegativeRate >= 25 ? `기준일 기사에서 부정 기사 비중이 ${dailyNegativeRate}%로 높게 잡힙니다.` : null,
    socialNegativeRate >= 12 ? `SNS 부정 힌트가 ${socialNegativeRate}%입니다. 댓글/커뮤니티 확산 여부를 확인하세요.` : null,
    dailyPromotionRate >= 20 ? `기준일 홍보성 기사 비중이 ${dailyPromotionRate}%입니다. 자연 노출과 유료성 노출을 분리해서 보고하세요.` : null,
    dailyDelta >= 5 ? `기준일 발행 기사 수가 직전일 대비 ${dailyDelta}건 늘었습니다.` : null,
  ].filter(Boolean);
  const dailyBriefLines = [
    `${selectedKeywordLabel} 기준 ${baseDateKey} 발행 기사는 ${baseDateArticleTotal}건입니다.`,
    dailyDelta > 0 ? `직전일보다 ${dailyDelta}건 증가해 관심도가 올라가는 흐름입니다.` : dailyDelta < 0 ? `직전일보다 ${Math.abs(dailyDelta)}건 감소해 노출은 다소 안정된 상태입니다.` : "직전일과 비슷한 수집 흐름입니다.",
    baseDateArticleHourlyRows.length ? `기준일 시간대별 발행 기사 합계는 ${baseDateArticleHourlyTotal}건이고, 피크는 ${baseDateArticlePeak}건입니다.` : "기준일 시간대별 발행 기사 데이터는 아직 충분하지 않습니다.",
    socialTotal ? `최근 SNS 샘플은 ${socialTotal}건이고, 부정 힌트는 ${socialNegativeRate}%입니다.` : "SNS 샘플은 아직 수집되지 않았습니다.",
    dailyLeadArticle?.title ? `먼저 확인할 기사는 "${dailyLeadArticle.title}"입니다.` : "우선 확인 기사 후보는 아직 없습니다.",
  ];
  const focusSignals = [
    { label: "전일 대비", value: selectedInsight ? `${selectedInsight.delta >= 0 ? "+" : ""}${selectedInsight.delta}건` : "데이터 없음", tone: selectedInsight?.spike ? "warn" : "stable" },
    { label: "언론 노출 흐름", value: trendDelta > 0 ? `전일 대비 +${trendDelta}` : trendDelta < 0 ? `전일 대비 ${trendDelta}` : "전일 수준 유지", tone: trendDelta > 0 ? "good" : trendDelta < 0 ? "muted" : "stable" },
    { label: "SNS 확산 강도", value: snsToNewsRatio == null ? "뉴스 기준 없음" : `뉴스 대비 ${snsToNewsRatio}%`, tone: snsToNewsRatio >= 120 ? "warn" : "stable" },
    { label: "Earned Media", value: promotionTotal ? `${earnedRate}%` : "분석 대기", tone: earnedRate >= 75 ? "good" : earnedRate >= 50 ? "stable" : "warn" },
    { label: "부정 리스크", value: `${Math.max(negativeRate, socialNegativeRate)}%`, tone: Math.max(negativeRate, socialNegativeRate) >= 25 ? "warn" : "good" },
  ];
  const avgImportance = priorityArticles
    .map((article) => normalizeScore(article.importance ?? article.score))
    .filter((score) => score != null)
    .reduce((total, score, _, arr) => total + score / arr.length, 0);
  const healthScore = Math.max(0, Math.min(100, Math.round(70 + positiveRate * 0.25 - negativeRate * 0.45 - promotionRate * 0.15 + (avgImportance || 0) * 0.05)));
  const healthTone = healthScore >= 75 ? "양호" : healthScore >= 55 ? "주의" : "위험";
  const riskSignals = [
    selectedInsight?.spike ? selectedInsight.summary : null,
    negativeRate >= 25 ? `부정 반응 비중이 ${negativeRate}%로 높습니다.` : null,
    socialNegativeRate >= 12 ? `SNS 부정 키워드 힌트가 ${socialNegativeRate}%로 감지됐습니다.` : null,
    promotionRate >= 20 ? `광고성/홍보성 기사 비중이 ${promotionRate}%입니다.` : null,
    pending > 0 ? `AI 분석 대기 기사가 ${pending}건 남아 있습니다.` : null,
  ].filter(Boolean);
  const opportunities = [
    positiveRate >= 40 ? `긍정 언급이 ${positiveRate}%로 캠페인 확산 소재로 활용하기 좋습니다.` : null,
    socialPositive > socialNegative && socialTotal > 0 ? "SNS 긍정 힌트가 부정 힌트보다 많아 확산 반응 확인에 적합합니다." : null,
    mentionCount >= 20 ? `${days}일간 언급량이 ${mentionCount}건으로 모니터링 가치가 높습니다.` : null,
    priorityArticles[0]?.summary ? "상위 중요 기사에 요약문이 있어 내부 공유 자료로 바로 전환할 수 있습니다." : null,
  ].filter(Boolean);
  const actions = [
    negativeRate >= 25 ? "부정 기사 제목과 원문을 우선 확인하고 Q&A 또는 대응 메시지를 준비하세요." : "부정 신호는 낮습니다. 긍정/중립 기사 중심으로 소재를 선별하세요.",
    socialTotal > mentionCount ? "SNS 언급량이 기사량보다 큽니다. 댓글/공유/커뮤니티 확산 여부를 별도로 확인하세요." : "언론 보도와 SNS 반응의 차이를 클라이언트 보고서에 함께 표기하세요.",
    promotionRate >= 20 ? "광고성으로 분류된 기사 표현을 점검하고 자연 노출과 유료 노출을 분리 보고하세요." : "홍보성 비중은 과하지 않습니다. earned media 관점의 성과를 정리하세요.",
    "중요도 상위 기사 3건을 클라이언트 데일리 리포트의 첫 페이지 후보로 검토하세요.",
  ];
  const chartConfigs = [
    { title: `${selectedKeywordLabel} 기사 추이`, data: selectedTrend.slice(-30), xKey: "date", yKey: "article_count", type: "line", color: "#2271b1", note: "선택 키워드의 일자별 실제 수집 기사 수" },
    { title: `${selectedKeywordLabel} 뉴스 조회 기사 수 시간별 추이`, data: selectedVolumeTrend.slice(-72), xKey: "hour", yKey: "total_count", type: "line", color: "#d63638", note: "매시간 실제 뉴스 검색으로 조회된 기사 수" },
    { title: `${selectedKeywordLabel} 감성 분포`, data: selectedSentiment, xKey: "sentiment", yKey: "count", color: "#00a32a", note: "AI가 분류한 긍정/중립/부정 기사 수" },
    { title: `${selectedKeywordLabel} 광고성 비중`, data: selectedPromotion, xKey: "promotion", yKey: "count", color: "#dba617", note: "유료/홍보성 노출과 earned media 구분" },
    { title: "SNS 플랫폼별 최신 스냅샷", data: socialSources, xKey: "source_label", yKey: "mention_count", color: "#3858e9", note: "YouTube 공식 API, 그 외 공개 검색 샘플" },
  ];

  const currentBrief = (
    <>
      <div className="marketing-brief">
        <div className="brief-head">
          <div>
            <span className="eyebrow">Marketing Intelligence Brief</span>
            <h2>{selectedKeywordLabel} 현황 브리핑</h2>
          </div>
          <div className={`health-score ${healthTone}`}>
            <span>브랜드 지수</span>
            <strong>{healthScore}</strong>
            <em>{healthTone}</em>
          </div>
        </div>

        <div className="brief-metrics">
          <div><span>언급 기사</span><strong>{mentionCount}</strong><small>{days}일 기준</small></div>
          <div><span>뉴스 조회 기사</span><strong>{selectedVolume?.total_count ?? "-"}</strong><small>최근 1시간 검색 결과</small></div>
          <div><span>SNS 최신 스냅샷</span><strong>{socialTotal || "-"}</strong><small>YouTube 공식 API 포함</small></div>
          <div><span>부정 비중</span><strong>{negativeRate}%</strong><small>AI 감성 분석</small></div>
          <div><span>SNS 부정 힌트</span><strong>{socialNegativeRate}%</strong><small>제목/요약 키워드 힌트</small></div>
        </div>

        <div className="focus-strip">
          {focusSignals.map((item) => (
            <div className={`focus-chip ${item.tone}`} key={item.label}>
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          ))}
        </div>

        <div className="brief-columns">
          <div>
            <strong>리스크 신호</strong>
            {(riskSignals.length ? riskSignals : ["현재 뚜렷한 리스크 신호는 없습니다."]).map((item) => <p key={item}>{item}</p>)}
          </div>
          <div>
            <strong>기회 신호</strong>
            {(opportunities.length ? opportunities : ["긍정/중립 기사에서 캠페인 소재를 선별해 볼 수 있습니다."]).map((item) => <p key={item}>{item}</p>)}
          </div>
          <div>
            <strong>추천 액션</strong>
            {actions.map((item) => <p key={item}>{item}</p>)}
          </div>
        </div>
      </div>

      {chartConfigs.map((chart) => (
        <ChartCard key={chart.title} {...chart} onExpand={() => setExpandedChart(chart)} />
      ))}
    </>
  );

  const dailyBrief = (
    <>
      <div className="marketing-brief daily-brief">
        <div className="brief-head">
          <div>
            <span className="eyebrow">Daily Briefing</span>
            <h2>{selectedKeywordLabel} 일일 브리핑</h2>
          </div>
          <div className="daily-date">
            <span>기준일</span>
            <strong>{baseDateKey}</strong>
          </div>
        </div>

        <div className="brief-metrics daily">
          <div><span>기준일 발행 기사</span><strong>{baseDateArticleTotal}</strong><small>{dailyDelta >= 0 ? `직전일 대비 +${dailyDelta}` : `직전일 대비 ${dailyDelta}`}</small></div>
          <div><span>시간별 발행 피크</span><strong>{baseDateArticlePeak || "-"}</strong><small>저장 기사 기준</small></div>
          <div><span>최근 SNS 샘플</span><strong>{socialTotal || "-"}</strong><small>부정 힌트 {socialNegativeRate}%</small></div>
          <div><span>AI 분석 대기</span><strong>{pending}</strong><small>자동 분석 큐</small></div>
        </div>

        <div className="daily-brief-layout">
          <div className="daily-summary-card">
            <strong>기준일 요약</strong>
            {dailyBriefLines.map((line) => <p key={line}>{line}</p>)}
          </div>
          <div className="daily-summary-card">
            <strong>기준일 리스크</strong>
            {(dailyRisks.length ? dailyRisks : ["기준일 데이터에서 즉시 대응이 필요한 리스크 신호는 낮습니다."]).map((line) => <p key={line}>{line}</p>)}
          </div>
          <div className="daily-summary-card">
            <strong>보고서 작성 포인트</strong>
            <p>기사량, 검색량, SNS 신호를 한 문단으로 묶어 클라이언트용 상황 설명을 작성하세요.</p>
            <p>중요도 상위 기사와 부정 기사 여부를 분리해 담당자가 빠르게 확인할 수 있게 정리하세요.</p>
          </div>
        </div>
      </div>

      <div className="daily-chart-grid">
        <ChartCard
          title={`${selectedKeywordLabel} 기준일 발행 기사 추이`}
          data={baseDateArticleHourlyRows}
          xKey="hour"
          yKey="total_count"
          type="bar"
          color="#2271b1"
          note={`${baseDateKey} KST 00시~23시 발행 기사 수, 합계 ${baseDateArticleHourlyTotal}건`}
          onExpand={() => setExpandedChart({
            title: `${selectedKeywordLabel} 기준일 발행 기사 추이`,
            data: baseDateArticleHourlyRows,
            xKey: "hour",
            yKey: "total_count",
            type: "bar",
            color: "#2271b1",
            note: `${baseDateKey} KST 00시~23시 발행 기사 수, 합계 ${baseDateArticleHourlyTotal}건`,
          })}
        />
        <ChartCard
          title={`${selectedKeywordLabel} 기준일 SNS 조회 수`}
          data={dailySocialRows}
          xKey="source_label"
          yKey="count"
          type="bar"
          color="#3858e9"
          note={`${baseDateKey} KST 기준일에 올라온 SNS 플랫폼별 조회/언급 수, 합계 ${dailySocialTotal}건`}
          onExpand={() => setExpandedChart({
            title: `${selectedKeywordLabel} 기준일 SNS 조회 수`,
            data: dailySocialRows,
            xKey: "source_label",
            yKey: "count",
            type: "bar",
            color: "#3858e9",
            note: `${baseDateKey} KST 기준일에 올라온 SNS 플랫폼별 조회/언급 수, 합계 ${dailySocialTotal}건`,
          })}
        />
      </div>
      <ChartCard
        title={`${selectedKeywordLabel} 기준일 판단 신호`}
        data={dailySignalData}
        xKey="label"
        yKey="count"
        color="#646970"
        note={`${baseDateKey} 발행 기사 감성 분석 기준, 홍보성은 별도 비율로 계산`}
        onExpand={() => setExpandedChart({
          title: `${selectedKeywordLabel} 기준일 판단 신호`,
          data: dailySignalData,
          xKey: "label",
          yKey: "count",
          color: "#646970",
          note: `${baseDateKey} 발행 기사 감성 분석 기준, 홍보성은 별도 비율로 계산`,
        })}
      />
      <div className="daily-article-panel">
        <div className="panel-heading">
          <div>
            <strong>기준일 우선 확인 기사</strong>
            <span>{baseDateKey} 발행 기사 기준</span>
          </div>
        </div>
        <div className="priority-list compact">
          {dailyImportantArticles.length ? dailyImportantArticles.slice(0, 5).map((article, index) => {
            const expanded = expandedDailyArticleId === article.id;
            const detail = dailyArticleDetails[article.id];
            const fullSummary = detail?.summary || article.summary || "요약문이 아직 없습니다.";
            const fullContent = detail?.content || "";
            return (
              <article className={`daily-priority-item ${expanded ? "expanded" : ""}`} key={article.id || article.title}>
                <button className="daily-priority-toggle" onClick={() => toggleDailyArticle(article)} type="button">
                  <b>{index + 1}</b>
                  <div>
                    <strong>{article.title}</strong>
                    <span>{article.source || "출처 없음"} · {formatDate(article.published_at)}</span>
                    <p>{article.summary || "요약문이 아직 없습니다."}</p>
                  </div>
                  <em>{normalizeScore(article.importance ?? article.score)?.toFixed(1) || "-"}</em>
                </button>
                {expanded && (
                  <div className="daily-priority-detail">
                    <strong>{detail?.title || article.title}</strong>
                    <span>{article.source || detail?.source || "출처 없음"} · {formatDate(detail?.published_at || article.published_at)}</span>
                    <p>{fullSummary}</p>
                    {fullContent && <pre>{fullContent}</pre>}
                    {(detail?.url || article.url) && (
                      <a href={detail?.url || article.url} target="_blank" rel="noreferrer">원문 열기</a>
                    )}
                  </div>
                )}
              </article>
            );
          }) : <EmptyState title="어제 발행 기사 없음" body="어제 발행된 기사 기준으로 표시할 후보가 없습니다." />}
        </div>
      </div>
    </>
  );

  return (
    <section className="stats-grid">
      <div className="toolbar full">
        <div className="brief-tabs" role="tablist" aria-label="브리핑 화면">
          <button className={briefTab === "current" ? "active" : ""} onClick={() => setBriefTab("current")} type="button">현재 화면</button>
          <button className={briefTab === "daily" ? "active" : ""} onClick={() => setBriefTab("daily")} type="button">일일 화면</button>
        </div>
        <label className="range-label">조회 기간 {days}일</label>
        <input min="1" max="90" type="range" value={days} onChange={(event) => setDays(Number(event.target.value))} />
        <span className="auto-status">
          {busy ? <Loader2 className="spin" size={15} /> : <CheckCircle2 size={15} />}
          자동 업데이트 {pending > 0 ? `· 분석 대기 ${pending}건` : ""}
        </span>
      </div>

      {briefTab === "current" ? currentBrief : dailyBrief}

      <div className="report-panel">
        <div className="panel-heading">
          <strong>데일리 리포트</strong>
          <span>요약 본문과 그래프가 포함된 보고서</span>
        </div>
        <button className="secondary" onClick={downloadReport}>
          <Download size={16} /> Excel 다운로드
        </button>
        <textarea value={emails} onChange={(event) => setEmails(event.target.value)} placeholder="example@gmail.com&#10;team@example.com" />
        <button className="primary" disabled={busy} onClick={sendEmail}>
          <Mail size={16} /> 이메일 발송
        </button>
      </div>

      {expandedChart && <ChartModal chart={expandedChart} onClose={() => setExpandedChart(null)} />}
    </section>
  );
}

function ChartVisual({ data, xKey, yKey, type = "bar", color = "#2563eb", height = 220 }) {
  return (
    <ResponsiveContainer height={height} width="100%">
      {type === "line" ? (
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey={xKey} tick={{ fontSize: 11 }} />
          <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
          <Tooltip />
          <Line dataKey={yKey} stroke={color} strokeWidth={2.5} type="monotone" />
        </LineChart>
      ) : (
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey={xKey} tick={{ fontSize: 11 }} />
          <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
          <Tooltip />
          <Bar dataKey={yKey} fill={color} radius={[4, 4, 0, 0]} />
        </BarChart>
      )}
    </ResponsiveContainer>
  );
}

function ChartCard({ title, data, xKey, yKey, type = "bar", color = "#2563eb", note = "", onExpand }) {
  return (
    <div className="chart-card">
      <div className="panel-heading">
        <div>
          <strong>{title}</strong>
          <span>{note || `${data?.length || 0}개 항목`}</span>
        </div>
        <button className="icon-button" disabled={!data?.length} title="그래프 크게 보기" onClick={onExpand}>
          <Maximize2 size={15} />
        </button>
      </div>
      {!data?.length ? (
        <EmptyState title="데이터 없음" body="수집 또는 분석 후 확인할 수 있습니다." />
      ) : (
        <ChartVisual data={data} xKey={xKey} yKey={yKey} type={type} color={color} />
      )}
    </div>
  );
}

function ChartModal({ chart, onClose }) {
  return (
    <div className="modal-backdrop chart-modal-backdrop" role="presentation" onMouseDown={onClose}>
      <div className="chart-modal" role="dialog" aria-modal="true" aria-label={chart.title} onMouseDown={(event) => event.stopPropagation()}>
        <div className="modal-heading">
          <div>
            <strong>{chart.title}</strong>
            <span>{chart.note || `${chart.data?.length || 0}개 항목`}</span>
          </div>
          <button className="icon-button" title="닫기" onClick={onClose}>
            <X size={17} />
          </button>
        </div>
        {!chart.data?.length ? (
          <EmptyState title="데이터 없음" body="수집 또는 분석 후 확인할 수 있습니다." />
        ) : (
          <ChartVisual {...chart} height={520} />
        )}
      </div>
    </div>
  );
}

function App() {
  const [bootstrapped, setBootstrapped] = useState(false);
  const [loginRequired, setLoginRequired] = useState(false);
  const [keywords, setKeywords] = useState([]);
  const [selectedKeywordId, setSelectedKeywordId] = useState(null);
  const [chats, setChats] = useState([]);
  const [selectedChatId, setSelectedChatId] = useState(null);
  const [selectedChatKeywordId, setSelectedChatKeywordId] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatConversationId, setChatConversationId] = useState("");
  const [topItems, setTopItems] = useState([]);
  const [articlePage, setArticlePage] = useState(null);
  const [importancePage, setImportancePage] = useState(null);
  const [activeTab, setActiveTab] = useState("stats");
  const [toast, setToast] = useState(null);
  const [loadingSide, setLoadingSide] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const selectedKeyword = keywords.find((item) => item.id === selectedKeywordId);
  const showToast = (message, type = "info") => setToast({ message, type });

  async function loadShell() {
    setLoadingSide(true);
    try {
      const [keywordData, chatData] = await Promise.all([endpoints.keywords(), endpoints.chats()]);
      const nextKeywords = keywordData.items || [];
      const nextChats = chatData.items || [];

      setKeywords(nextKeywords);
      setChats(nextChats);
      setSelectedKeywordId((current) => current || nextKeywords[0]?.id || null);
      setLoginRequired(false);
    } catch (err) {
      if (String(err.message).includes("Authentication")) setLoginRequired(true);
      else showToast(err.message, "error");
    } finally {
      setBootstrapped(true);
      setLoadingSide(false);
    }
  }

  async function ensureChatSession(keywordId = selectedKeywordId) {
    if (!keywordId) {
      setSelectedChatId(null);
      setSelectedChatKeywordId(null);
      setChatMessages([]);
      setChatConversationId("");
      return null;
    }

    if (selectedChatId && selectedChatKeywordId === keywordId) return selectedChatId;

    try {
      const existing = chats.find((chat) => chat.keyword_id === keywordId) || (await endpoints.chats(keywordId)).items?.[0];
      if (existing) {
        setSelectedChatId(existing.id);
        setSelectedChatKeywordId(keywordId);
        setChats((prev) => [existing, ...prev.filter((chat) => chat.id !== existing.id)]);
        const detail = await endpoints.chatDetail(existing.id);
        setChatConversationId(detail.external_conversation_id || "");
        setChatMessages(normalizeChatMessages(detail.messages || []));
        return existing.id;
      }
      const keyword = keywords.find((item) => item.id === keywordId);
      const created = await endpoints.createChat(`${keyword ? keywordName(keyword) : "키워드"} AI 채팅`, keywordId);
      setSelectedChatId(created.id);
      setSelectedChatKeywordId(keywordId);
      setChats((prev) => [created, ...prev.filter((chat) => chat.id !== created.id)]);
      setChatMessages([]);
      setChatConversationId("");
      return created.id;
    } catch (err) {
      showToast(err.message, "error");
      return null;
    }
  }

  async function loadSummary(keywordId = selectedKeywordId) {
    if (!keywordId) return;
    try {
      const [articles, importance] = await Promise.all([
        endpoints.articles({ keyword_id: keywordId, page: 1, size: 1, sort: "published_at_desc" }),
        endpoints.importance({ keyword_id: keywordId, page: 1, size: 5, sort: "score_desc" }),
      ]);
      setArticlePage(articles.page_info);
      setTopItems(importance.items || []);
      setImportancePage(importance.page_info);
    } catch (err) {
      showToast(err.message, "error");
    }
  }

  useEffect(() => {
    loadShell();
  }, []);

  useEffect(() => {
    loadSummary(selectedKeywordId);
  }, [selectedKeywordId]);

  async function createKeyword(keywordConfig) {
    setLoadingSide(true);
    try {
      const data = await endpoints.createKeyword(keywordConfig);
      const competitorKeywords = keywordConfig.competitor_keywords || [];
      let competitorCreatedCount = 0;
      if (competitorKeywords.length) {
        const groupName = keywordConfig.group_name || `${keywordConfig.keyword} 경쟁사 그룹`;
        const batch = await endpoints.batchCreateKeywords({
          ...keywordConfig,
          keywords: competitorKeywords,
          group_name: groupName,
          monitoring_type: "competitor",
          email_auto_send: false,
          email_recipients: [],
        });
        const createdIds = (batch.items || [])
          .filter((item) => item.status === "CREATED" && item.id)
          .map((item) => item.id);
        competitorCreatedCount = createdIds.length;
        if (createdIds.length) {
          await endpoints.runCrawlForKeywordIds(createdIds);
        }
      }
      showToast(
        competitorCreatedCount
          ? `'${keywordName(data.keyword) || keywordConfig.keyword}' 키워드와 경쟁사 ${competitorCreatedCount}개를 추가했습니다.`
          : `'${keywordName(data.keyword) || keywordConfig.keyword}' 키워드를 추가했습니다.`,
        "success"
      );
      await loadShell();
      if (data.keyword?.id) setSelectedKeywordId(data.keyword.id);
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      setLoadingSide(false);
    }
  }

  async function toggleKeyword(id, isActive) {
    try {
      await endpoints.updateKeyword(id, { is_active: isActive });
      setKeywords((prev) => prev.map((item) => (item.id === id ? { ...item, is_active: isActive } : item)));
    } catch (err) {
      showToast(err.message, "error");
    }
  }

  async function resetCurrentChat() {
    if (!selectedChatId) return;
    try {
      const detail = await endpoints.resetChat(selectedChatId);
      setChatConversationId(detail.external_conversation_id || "");
      setChatMessages(normalizeChatMessages(detail.messages || []));
      setChats((prev) =>
        prev.map((chat) =>
          chat.id === selectedChatId
            ? { ...chat, last_message: null, last_message_at: null }
            : chat
        )
      );
      showToast("현재 키워드의 AI 채팅을 초기화했습니다.", "success");
    } catch (err) {
      showToast(err.message, "error");
    }
  }

  async function updateKeyword(id, keywordConfig) {
    setLoadingSide(true);
    try {
      const updated = await endpoints.updateKeyword(id, keywordConfig);
      showToast(`'${keywordName(updated)}' 키워드 설정을 수정했습니다.`, "success");
      await loadShell();
      setSelectedKeywordId(id);
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      setLoadingSide(false);
    }
  }

  async function deleteKeyword(keyword) {
    const id = keyword?.id ?? keyword;
    const label = keywordName(keyword);
    const remainingKeywords = keywords.filter((item) => item.id !== id);
    try {
      setLoadingSide(true);
      await endpoints.deleteKeyword(id);
      showToast(`'${label}' 키워드 삭제 요청을 정리했습니다.`, "success");
      if (selectedKeywordId === id) {
        setSelectedKeywordId(remainingKeywords[0]?.id || null);
      }
      await loadShell();
      return true;
    } catch (err) {
      showToast(err.message, "error");
      return false;
    } finally {
      setLoadingSide(false);
    }
  }

  if (!bootstrapped) {
    return (
      <main className="splash">
        <Loader2 className="spin" size={28} />
        <span>콘솔을 준비하는 중</span>
      </main>
    );
  }

  if (loginRequired) {
    return <LoginGate onLogin={loadShell} />;
  }

  return (
    <div className={`app-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
      <Sidebar
        keywords={keywords}
        selectedKeywordId={selectedKeywordId}
        setSelectedKeywordId={setSelectedKeywordId}
        onCreateKeyword={createKeyword}
        onUpdateKeyword={updateKeyword}
        onDeleteKeyword={deleteKeyword}
        loading={loadingSide}
        collapsed={sidebarCollapsed}
        setCollapsed={setSidebarCollapsed}
      />
      <main className="main">
        <header className="topbar">
          <div>
            <span className="eyebrow">뉴스 인텔리전스 콘솔</span>
            <h1>{selectedKeyword ? keywordName(selectedKeyword) : "키워드를 선택하세요"}</h1>
          </div>
        </header>

        <Summary selectedKeyword={selectedKeyword} articlePage={articlePage} importancePage={importancePage} />

        <nav className="tabs">
          <button className={activeTab === "stats" ? "active" : ""} onClick={() => setActiveTab("stats")}>
            <BarChart3 size={16} /> 통계
          </button>
          <button className={activeTab === "articles" ? "active" : ""} onClick={() => setActiveTab("articles")}>
            <Search size={16} /> 기사
          </button>
          <button className={activeTab === "chat" ? "active" : ""} onClick={() => setActiveTab("chat")}>
            <MessageSquare size={16} /> AI 채팅
          </button>
        </nav>

        {activeTab === "articles" && (
          <Articles selectedKeywordId={selectedKeywordId} topItems={topItems} showToast={showToast} refreshSummary={() => loadSummary()} />
        )}
        {activeTab === "chat" && (
          <Chat
            chatId={selectedChatId}
            conversationId={chatConversationId}
            setConversationId={setChatConversationId}
            messages={chatMessages}
            setMessages={setChatMessages}
            ensureChat={ensureChatSession}
            onReset={resetCurrentChat}
            selectedKeywordId={selectedKeywordId}
            selectedKeywordName={selectedKeyword ? keywordName(selectedKeyword) : ""}
            showToast={showToast}
          />
        )}
        {activeTab === "stats" && (
          <Stats
            selectedKeywordId={selectedKeywordId}
            selectedKeywordName={selectedKeyword ? keywordName(selectedKeyword) : ""}
            showToast={showToast}
          />
        )}
      </main>
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
