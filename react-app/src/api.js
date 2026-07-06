const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v1";

const tokenKey = "news_console_access_token";
const refreshKey = "news_console_refresh_token";

export const authStore = {
  get token() {
    return localStorage.getItem(tokenKey);
  },
  setTokens(accessToken, refreshToken) {
    if (accessToken) localStorage.setItem(tokenKey, accessToken);
    if (refreshToken) localStorage.setItem(refreshKey, refreshToken);
  },
  clear() {
    localStorage.removeItem(tokenKey);
    localStorage.removeItem(refreshKey);
  },
};

function unwrap(body) {
  if (body && typeof body === "object" && "data" in body) return body.data;
  return body;
}

export async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (!(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  headers.set("ngrok-skip-browser-warning", "true");
  if (authStore.token) headers.set("Authorization", `Bearer ${authStore.token}`);

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
    body: options.body && !(options.body instanceof FormData) ? JSON.stringify(options.body) : options.body,
  });

  if (!response.ok) {
    let detail = await response.text();
    try {
      const parsed = JSON.parse(detail);
      detail = parsed?.error?.message || parsed?.message || detail;
    } catch {
      // keep plain text
    }
    throw new Error(detail || `HTTP ${response.status}`);
  }

  if (options.raw) return response;
  const text = await response.text();
  return text ? unwrap(JSON.parse(text)) : null;
}

export const endpoints = {
  login: (email, password) => api("/auth/login", { method: "POST", body: { email, password } }),
  me: () => api("/users/me"),
  keywords: () => api("/keywords?page=1&size=100"),
  createKeyword: (keywordConfig) => api("/keywords", {
    method: "POST",
    body: {
      keyword: keywordConfig.keyword,
      language: "ko",
      client_name: keywordConfig.client_name || null,
      group_name: keywordConfig.group_name || null,
      monitoring_type: keywordConfig.monitoring_type || "brand",
      priority_level: keywordConfig.priority_level || "normal",
      crawl_interval_minutes: keywordConfig.crawl_interval_minutes,
      crawl_limit: keywordConfig.crawl_limit,
      email_auto_send: keywordConfig.email_auto_send,
      email_recipients: keywordConfig.email_recipients,
      email_send_time: keywordConfig.email_send_time,
      email_condition_type: keywordConfig.email_condition_type,
      alert_negative_rate_threshold: keywordConfig.alert_negative_rate_threshold,
      alert_importance_threshold: keywordConfig.alert_importance_threshold,
      alert_article_count_threshold: keywordConfig.alert_article_count_threshold,
      importance_criteria: keywordConfig.importance_criteria || null,
    },
  }),
  batchCreateKeywords: (keywordConfig) => api("/keywords/batch", {
    method: "POST",
    body: {
      keywords: keywordConfig.keywords,
      language: "ko",
      client_name: keywordConfig.client_name || null,
      group_name: keywordConfig.group_name || null,
      monitoring_type: keywordConfig.monitoring_type || "competitor",
      priority_level: keywordConfig.priority_level || "normal",
      crawl_interval_minutes: keywordConfig.crawl_interval_minutes,
      crawl_limit: keywordConfig.crawl_limit,
      email_auto_send: keywordConfig.email_auto_send || false,
      email_recipients: keywordConfig.email_recipients || [],
      email_send_time: keywordConfig.email_send_time || "08:30",
      email_condition_type: keywordConfig.email_condition_type || "daily_summary",
      alert_negative_rate_threshold: keywordConfig.alert_negative_rate_threshold || 25,
      alert_importance_threshold: keywordConfig.alert_importance_threshold || 80,
      alert_article_count_threshold: keywordConfig.alert_article_count_threshold || 10,
      importance_criteria: keywordConfig.importance_criteria || null,
    },
  }),
  updateKeyword: (id, body) => api(`/keywords/${id}`, { method: "PATCH", body }),
  deleteKeyword: (id) => api(`/keywords/${id}`, { method: "DELETE" }),
  articles: (params) => api(`/articles?${new URLSearchParams(params)}`),
  articleDetail: (id) => api(`/articles/${id}`),
  deleteArticle: (id) => api(`/articles/${id}`, { method: "DELETE" }),
  articleImportance: (id) => api(`/articles/${id}/importance`),
  summarize: (articleId, jobId) => api("/ai/summary", { method: "POST", body: { article_id: articleId, job_id: jobId } }),
  runCrawl: (keywordId) => api("/crawl-runs", {
    method: "POST",
    body: {
      force: true,
      today_only: true,
      keyword_ids: keywordId ? [keywordId] : null,
    },
  }),
  runCrawlForKeywordIds: (keywordIds) => api("/crawl-runs", {
    method: "POST",
    body: {
      force: true,
      today_only: true,
      keyword_ids: keywordIds?.length ? keywordIds : null,
    },
  }),
  runImportance: (keywordId, jobId) => api("/importance/run", { method: "POST", body: { keyword_id: keywordId, job_id: jobId } }),
  importance: (params) => api(`/importance?${new URLSearchParams(params)}`),
  scoringFeedback: (body) => api("/importance/feedback", { method: "POST", body }),
  chats: (keywordId) => api(`/chats?page=1&size=50${keywordId ? `&keyword_id=${keywordId}` : ""}`),
  chatDetail: (id) => api(`/chats/${id}`),
  createChat: (title, keywordId = null) => api("/chats", { method: "POST", body: { title, keyword_id: keywordId } }),
  deleteChat: (id) => api(`/chats/${id}`, { method: "DELETE" }),
  resetChat: (id) => api(`/chats/${id}/reset`, { method: "POST" }),
  sendMessage: (chatId, body) => api(`/chats/${chatId}/messages`, { method: "POST", body }),
  articleStats: (days) => api(`/stats/articles?days=${days}`),
  articleHourlyStats: (date, keywordId) => {
    const params = new URLSearchParams({ date });
    if (keywordId) params.set("keyword_id", keywordId);
    return api(`/stats/articles/hourly?${params}`);
  },
  dailySocialStats: (date, keywordId) => {
    const params = new URLSearchParams({ date });
    if (keywordId) params.set("keyword_id", keywordId);
    return api(`/stats/social/daily?${params}`);
  },
  analysisStats: (days) => api(`/stats/analysis?days=${days}`),
  searchVolume: () => api("/stats/search-volume"),
  searchVolumeTrend: (hours = 48) => api(`/stats/search-volume/trend?hours=${hours}`),
  pendingAnalysis: () => api("/crawl-runs/analysis/pending"),
  runAnalysis: (jobId) => api("/crawl-runs/analysis", { method: "POST", body: { job_id: jobId } }),
  job: (jobId) => api(`/jobs/${jobId}`),
  report: (keywordId) => api(`/reports/daily${keywordId ? `?keyword_id=${keywordId}` : ""}`, { raw: true }),
  emailReport: (body) => api("/reports/email", { method: "POST", body }),
};
