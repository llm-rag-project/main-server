import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  BarChart3,
  Bell,
  Bot,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Calendar,
  Clock,
  Circle,
  CopyMinus,
  Download,
  ExternalLink,
  Eye,
  FileText,
  Hash,
  HelpCircle,
  Home,
  Loader2,
  Mail,
  MessageSquare,
  Maximize2,
  Pencil,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  Send,
  Settings,
  Sparkles,
  Star,
  Trash2,
  UserRound,
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
import CollectionStatusPanel from "./CollectionStatusPanel";
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
const donggukDashboardUrl = "https://2c25-210-94-172-73.ngrok-free.app/";
const donggukSections = {
  foundation: "동국대 [법인/건학위]",
  education: "대학 [교육]",
  buddhism: "불교 [종단]",
};
function normalizeDonggukSectionKey(section) {
  const value = String(section || "").trim();
  if (!value) return "";
  if (value === "dongguk_core" || value === "foundation" || /동국대|법인|건학/.test(value)) return "foundation";
  if (value === "education" || /대학\s*\[교육\]|고등교육|교육/.test(value)) return "education";
  if (value === "buddhism" || /불교|종단|조계종/.test(value)) return "buddhism";
  return "";
}

function normalizeDonggukSectionLabel(section, fallback = donggukSections.foundation) {
  const key = normalizeDonggukSectionKey(section);
  return key ? donggukSections[key] : fallback;
}
const donggukPriorityBands = [
  { label: "P1", name: "최우선", min: 80, tone: "p1" },
  { label: "P2", name: "주요", min: 64, tone: "p2" },
  { label: "P3", name: "보통", min: 52, tone: "p3" },
  { label: "P4", name: "참고", min: 25, tone: "p4" },
  { label: "P5", name: "낮음", min: 0, tone: "p5" },
];
const donggukCategoryRules = [
  { key: "leader", label: "총장/이사장 메시지", score: 95, priority: "P1", keywords: ["총장", "이사장", "부총장", "밝혀", "말해", "기조연설", "서원"] },
  { key: "donation", label: "기부/장학/발전기금", score: 86, priority: "P1", keywords: ["기부", "쾌척", "기탁", "장학기금", "발전기금", "성금"] },
  { key: "buddhist_identity", label: "불교 정체성 상징 행사", score: 78, priority: "P2", keywords: ["봉축", "연등회", "수계", "불교사전", "봉정", "법회"] },
  { key: "research", label: "연구 성과/AI", score: 75, priority: "P2", keywords: ["연구", "AI", "개발", "특허", "수주", "전지", "배터리", "이온", "소재", "논문"] },
  { key: "campaign", label: "건학 기념 캠페인", score: 72, priority: "P2", keywords: ["120주년", "건학"] },
  { key: "partnership", label: "협약/사업 선정", score: 68, priority: "P2", keywords: ["업무협약", "MOU", "컨소시엄", "협약 체결", "맞손", "선정"] },
  { key: "award", label: "수상/인증", score: 66, priority: "P2", keywords: ["수상", "재인증", "인증 획득", "문학상", "미술상", "대상"] },
  { key: "event", label: "학교 공식 행사", score: 66, priority: "P2", keywords: ["개최", "봉행", "기념식", "개원", "추모제", "간담회"] },
  { key: "academic", label: "학술활동", score: 62, priority: "P3", keywords: ["학술원", "연구소", "학술대회", "춘계", "추계", "토론"] },
  { key: "admission", label: "입시/교육 프로그램", score: 60, priority: "P3", keywords: ["입결", "입시", "수시", "정시", "모집인원"] },
  { key: "appointment", label: "인사(임용/위촉)", score: 56, priority: "P3", keywords: ["임용", "선임", "취임", "위촉", "영입"] },
  { key: "education_policy", label: "대학 정책/고등교육 이슈", score: 55, priority: "P3", keywords: ["교육부", "의대", "유학생", "등록금", "대입"] },
  { key: "alumni", label: "동문/교수 인터뷰·칼럼", score: 49, priority: "P4", keywords: ["동문소식", "교수", "칼럼", "인터뷰", "출연"] },
  { key: "buddhist_general", label: "불교계/종단 일반", score: 28, priority: "P4", keywords: ["조계종", "사찰", "종정"] },
  { key: "other", label: "기타 개별 홍보 피처", score: 24, priority: "P5", keywords: [] },
];
const donggukCategoryLabels = new Set(donggukCategoryRules.map((rule) => rule.label));
const donggukCategoryAliases = {
  chairperson_message: "총장/이사장 메시지",
  donation: "기부/장학/발전기금",
  buddhist_identity: "불교 정체성 상징 행사",
  research_ai: "연구 성과/AI",
  campaign: "건학 기념 캠페인",
  partnership: "협약/사업 선정",
  award: "수상/인증",
  official_event: "학교 공식 행사",
  academic: "학술활동",
  admission: "입시/교육 프로그램",
  personnel: "인사(임용/위촉)",
  education_policy: "대학 정책/고등교육 이슈",
  alumni_media: "동문/교수 인터뷰·칼럼",
  buddhist_general: "불교계/종단 일반",
};
const defaultDonggukPriorityCriteria = `홍보처 AI 기사 선정 기준

우선순위 기준:
- 총장 또는 이사장의 공식 메시지가 포함된 기사를 가장 먼저 선정합니다.
- 기부, 장학금, 발전기금처럼 학교 이미지와 직접 연결되는 기사를 우선 선정합니다.
- 건학 120주년 등 현재 진행 중인 학교 캠페인 관련 기사를 우선 선정합니다.
- 연구 성과, 기술 개발, 특허, AI 관련 성과 기사를 우선 선정합니다.
- 공식 기관과의 협약, 사업 선정, 컨소시엄 참여 기사를 우선 선정합니다.
- 학교, 교직원, 학생의 수상 및 공식 인증 획득 기사를 우선 선정합니다.
- 학교가 주최하거나 공식적으로 참여한 주요 행사 기사를 우선 선정합니다.
- [동문소식], 교수 인터뷰·칼럼, 불교학술원, 종학연구소 등 동국대 소속이 제목에 드러나는 기사는 동국대 직접 관련 기사로 판단합니다.
- 대학 [교육] 섹션은 동국대 직접 언급 여부와 관계없이 파급력 있는 고등교육 정책 기사를 선정합니다.
- 불교 [종단] 섹션은 동국대 직접 언급 여부와 관계없이 파급력 있는 불교계·종단 기사를 선정합니다.

대표 기사 선정 기준:
- 동일 주제/동일 보도자료/같은 사건의 반복 보도는 하나의 그룹으로 묶고, 대표 기사 1건만 선정한다.
- 대표 기사는 원문 URL이 정상이고 본문 확인이 가능한 기사를 우선한다.
- 제목이 가장 명확하고 기관명, 행사명, 인물명, 금액, 성과 등 핵심 정보가 잘 드러난 기사를 우선한다.
- 기사 내용이 길고 요약에 필요한 사실 정보가 충분한 기사를 우선한다.
- 출처 신뢰도와 홍보처 배포 활용성을 고려한다.

제외 기준:
- 동국대 [법인/건학위] 섹션에서 동국대학교 또는 소속 기관·동문·교수와의 직접 관련성이 확인되지 않는 기사는 제외한다.
- 원문 확인이 어렵거나 본문 정보가 부족한 기사는 제외한다.`;
const defaultRepresentativeCriteria = `대표 기사 선정 기준:
- 동일 주제/동일 보도자료/같은 사건의 반복 보도는 하나의 그룹으로 묶고, 대표 기사 1건만 선정한다.
- 대표 기사는 원문 URL이 정상이고 본문 확인이 가능한 기사를 우선한다.
- 제목이 가장 명확하고 기관명, 행사명, 인물명, 금액, 성과 등 핵심 정보가 잘 드러난 기사를 우선한다.
- 기사 내용이 길고 요약에 필요한 사실 정보가 충분한 기사를 우선한다.
- 출처 신뢰도와 홍보처 배포 활용성을 고려한다.
- 단순 재전송, 제목만 바꾼 기사, 내용이 짧거나 원문 확인이 어려운 기사는 제외한다.`;

function normalizeDonggukCriteria(criteria) {
  let text = (criteria || "").trim();
  if (!text) return defaultDonggukPriorityCriteria;
  const legacyReplacements = [
    [
      "- 대학 정책과 고등교육 일반 이슈는 동국대학교와의 직접 관련성을 확인해 선정합니다.",
      "- 대학 [교육] 섹션은 동국대 직접 언급 여부와 관계없이 교육부, 대교협, 사총협, 고등교육법, 교육교부금, 등록금, 입시 등 파급력 있는 고등교육 정책 기사를 선정합니다.",
    ],
    [
      "- 불교계와 종단 일반 소식은 동국대학교와 직접 연결될 때만 참고 기사로 선정합니다.",
      "- 불교 [종단] 섹션은 동국대 직접 언급 여부와 관계없이 조계종, 종단, 포교, 출가, 성보, 불교문화유산 등 불교계 파급력이 있는 기사를 선정합니다.",
    ],
    [
      "- 동국대학교와 직접 관련성이 확인되지 않는 기사는 제외합니다.",
      "- 동국대 [법인/건학위] 섹션에서 동국대학교 또는 소속 기관·동문·교수와의 직접 관련성이 확인되지 않는 기사는 제외합니다.",
    ],
  ];
  legacyReplacements.forEach(([legacy, replacement]) => {
    text = text.replace(legacy, replacement);
  });
  return text;
}

const priorityRuleSentenceMap = {
  "총장/이사장 메시지": "총장 또는 이사장의 공식 메시지가 포함된 기사를 가장 먼저 선정합니다.",
  "기부/장학/발전기금": "기부, 장학금, 발전기금처럼 학교 이미지와 직접 연결되는 기사를 우선 선정합니다.",
  "건학 120주년 등 진행 중 캠페인": "건학 120주년 등 현재 진행 중인 학교 캠페인 관련 기사를 우선 선정합니다.",
  "연구 성과/AI": "연구 성과, 기술 개발, 특허, AI 관련 성과 기사를 우선 선정합니다.",
  "협약/사업 선정": "공식 기관과의 협약, 사업 선정, 컨소시엄 참여 기사를 우선 선정합니다.",
  "수상/인증": "학교, 교직원, 학생의 수상 및 공식 인증 획득 기사를 우선 선정합니다.",
  "학교 공식 행사": "학교가 주최하거나 공식적으로 참여한 주요 행사 기사를 우선 선정합니다.",
  "학술활동": "학술대회, 세미나, 토론회 관련 기사는 주요 성과 기사보다 낮게 선정합니다.",
  "입시/교육 프로그램": "입시와 교육 프로그램 기사는 홍보 활용도를 확인해 일반 순위로 선정합니다.",
  "인사/위촉": "임용, 위촉, 취임 등 인사 관련 기사는 일반 순위로 선정합니다.",
  "대학 정책/고등교육 이슈": "대학 [교육] 섹션은 동국대 직접 언급 여부와 관계없이 교육부, 대교협, 사총협, 고등교육법, 교육교부금, 등록금, 입시 등 파급력 있는 고등교육 정책 기사를 선정합니다.",
  "동문/교수 인터뷰·칼럼": "동문과 교수의 인터뷰, 칼럼, 방송 출연 기사는 참고 순위로 선정합니다.",
  "불교계/종단 일반 소식": "불교 [종단] 섹션은 동국대 직접 언급 여부와 관계없이 조계종, 종단, 포교, 출가, 성보, 불교문화유산 등 불교계 파급력이 있는 기사를 선정합니다.",
};
const defaultPriorityRuleItems = Object.values(priorityRuleSentenceMap);
const defaultRepresentativeRuleItems = [
  "동일 주제, 동일 보도자료, 같은 사건의 반복 보도는 하나의 그룹으로 묶고 대표 기사 1건만 선정합니다.",
  "원문 URL이 정상이고 본문 전체를 확인할 수 있는 기사를 우선합니다.",
  "기관명, 행사명, 인물명, 금액, 성과 등 핵심 정보가 제목에 명확히 드러난 기사를 우선합니다.",
  "요약에 필요한 사실 정보가 충분하고 기사 내용이 충실한 기사를 우선합니다.",
  "언론사 신뢰도와 홍보처 배포 활용도가 높은 기사를 우선합니다.",
];
const defaultExclusionRuleItems = [
  "동국대 [법인/건학위] 섹션에서 동국대학교 또는 소속 기관·동문·교수와의 직접 관련성이 확인되지 않는 기사는 제외합니다.",
  "원문 확인이 어렵거나 본문 정보가 부족한 기사는 제외합니다.",
];

function criteriaSectionRules(criteria, sectionName) {
  const lines = normalizeDonggukCriteria(criteria).split("\n");
  const sectionAliases = {
    priority: ["우선순위 기준", "위에 있을수록 우선적으로 올릴 기사", "최우선으로 올릴 기사", "일반 또는 참고로 낮출 기사"],
    representative: ["대표 기사 선정 기준"],
    exclusion: ["제외 기준"],
  };
  let active = sectionName === "priority";
  const rows = [];
  lines.forEach((rawLine) => {
    const line = rawLine.trim();
    const matchedSection = Object.entries(sectionAliases).find(([, aliases]) => aliases.some((alias) => line.startsWith(alias)));
    if (matchedSection) {
      active = matchedSection[0] === sectionName;
      return;
    }
    if (active && line.startsWith("- ")) rows.push(line.replace(/^- /, "").trim());
  });
  return rows.filter(Boolean);
}

function priorityRulesFromCriteria(criteria) {
  const rules = criteriaSectionRules(criteria, "priority");
  const sentenceRules = rules.map((rule) => priorityRuleSentenceMap[rule] || rule);
  return sentenceRules.length ? [...new Set(sentenceRules)] : defaultPriorityRuleItems;
}

function representativeRulesFromCriteria(criteria) {
  const rules = criteriaSectionRules(criteria, "representative");
  return rules.length ? rules : defaultRepresentativeRuleItems;
}

function exclusionRulesFromCriteria(criteria) {
  const rules = criteriaSectionRules(criteria, "exclusion");
  return rules.length ? rules : defaultExclusionRuleItems;
}

function criteriaFromRuleGroups(priorityRules, representativeRules, exclusionRules) {
  const clean = (rules) => rules.map((item) => item.trim()).filter(Boolean);
  return `홍보처 AI 기사 선정 기준

우선순위 기준:
${clean(priorityRules).map((item) => `- ${item}`).join("\n")}

대표 기사 선정 기준:
${clean(representativeRules).map((item) => `- ${item}`).join("\n")}

제외 기준:
${clean(exclusionRules).map((item) => `- ${item}`).join("\n")}`;
}

function defaultDonggukSectionLimits() {
  return {
    [donggukSections.foundation]: 4,
    [donggukSections.education]: 2,
    [donggukSections.buddhism]: 2,
  };
}

function donggukSectionLimitPayload(limits) {
  return {
    foundation: Number(limits[donggukSections.foundation] ?? 0),
    education: Number(limits[donggukSections.education] ?? 0),
    buddhism: Number(limits[donggukSections.buddhism] ?? 0),
  };
}

function donggukSectionLimitsFromPayload(payload, fallback = defaultDonggukSectionLimits()) {
  if (!payload) return fallback;
  return {
    [donggukSections.foundation]: Number(payload.foundation ?? fallback[donggukSections.foundation] ?? 0),
    [donggukSections.education]: Number(payload.education ?? fallback[donggukSections.education] ?? 0),
    [donggukSections.buddhism]: Number(payload.buddhism ?? fallback[donggukSections.buddhism] ?? 0),
  };
}

function applyDonggukSectionLimits(articles, limits) {
  const used = {};
  return articles.filter((article) => {
    const section = article.sectionLabel || donggukSections.foundation;
    const limit = Number(limits[section] ?? 0);
    used[section] = used[section] || 0;
    if (used[section] >= limit) return false;
    used[section] += 1;
    return true;
  });
}
const donggukDemoArticles = [
  {
    title: "동국대 이사장 돈관스님, 건학 120주년 기념 법회서 미래 인재 양성 서원",
    section: "foundation",
    source: "불교신문",
    links: [],
    summary: "이사장 메시지와 건학 120주년 캠페인이 함께 드러난 기사입니다. 기존 메일 패턴상 최상단 고정 후보로 분류됩니다.",
    matchedType: "leader",
  },
  {
    title: "법보선원, 동국대 장학기금 10억 원 기탁",
    section: "foundation",
    source: "법보신문 외",
    links: [],
    summary: "기부·기탁 유형은 기존 표본에서 가장 높은 신디케이션 비율을 보였습니다. 학교 이미지와 직접 연결되어 최우선으로 정렬됩니다.",
    matchedType: "donation",
  },
  {
    title: "동국대 AI융합연구팀, 의료영상 분석 기술 개발",
    section: "foundation",
    source: "전자신문 외",
    links: [],
    summary: "연구 성과와 AI 키워드가 결합된 기사입니다. 복수매체 보도 가산점으로 주요 기사 묶음 상단에 배치됩니다.",
    matchedType: "research",
  },
  {
    title: "동국대, 지역 상생 교육 컨소시엄 업무협약 체결",
    section: "foundation",
    source: "대학저널",
    links: [],
    summary: "공식 기관 협력 기사로 협약·사업 선정 기준에 해당합니다. 데일리 메일에서 주요 배지와 세부 카테고리가 표시됩니다.",
    matchedType: "partnership",
  },
  {
    title: "[동문소식-박주형] 신세계그룹 전략 발표",
    section: "foundation",
    source: "매일경제 외",
    links: [],
    summary: "기본 유형은 참고 기사지만 복수매체 동시보도 신호가 있어 주요 기사로 승급되는 예외 케이스입니다.",
    matchedType: "alumni",
  },
  {
    title: "동국대 학술원, 불교문화유산 디지털 아카이브 학술대회 개최",
    section: "foundation",
    source: "한국대학신문",
    links: [],
    summary: "학술활동과 불교 정체성 키워드가 함께 있으나 학술활동 기준으로 보통 우선순위 목록에 배치됩니다.",
    matchedType: "academic",
  },
  {
    title: "교육부, 2027학년도 대입 제도 개편안 발표",
    section: "education",
    source: "연합뉴스",
    links: [],
    summary: "고등교육 정책 참고 기사입니다. 기존 메일의 대학 [교육] 섹션 성격을 유지해 보통 우선순위로 분류합니다.",
    matchedType: "education_policy",
  },
  {
    title: "주요 대학, 수시 모집인원 확대와 입결 변화 분석",
    section: "education",
    source: "대학저널",
    links: [],
    summary: "입시·입결 키워드가 포함된 교육 섹션 기사입니다. 홍보처 참고 가치가 있어 일반 목록에 노출됩니다.",
    matchedType: "admission",
  },
  {
    title: "조계종, 종정 신년 법어 발표",
    section: "buddhism",
    source: "불교닷컴",
    links: [],
    summary: "불교 [종단] 섹션의 일반 참고 기사입니다. 동국대 직접 관련성이 낮아 참고 기사로 내려 정렬합니다.",
    matchedType: "buddhist_general",
  },
  {
    title: "봉축 연등회 문화행사 도심서 봉행",
    section: "buddhism",
    source: "BTN불교TV",
    links: [],
    summary: "불교 정체성 상징 행사의 참고 기사입니다. 동국대 직접 기사보다 낮지만 종단 일반 기사보다 우선합니다.",
    matchedType: "buddhist_identity",
  },
];

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

function shiftDateKey(dateKey, amount) {
  const date = new Date(`${dateKey}T12:00:00`);
  if (Number.isNaN(date.getTime())) return dateKey;
  date.setDate(date.getDate() + amount);
  return localDateKey(date);
}

function calendarGridRange(monthKey) {
  const firstDay = new Date(`${monthKey}-01T12:00:00`);
  if (Number.isNaN(firstDay.getTime())) return null;
  const lastDay = new Date(firstDay);
  lastDay.setMonth(lastDay.getMonth() + 1, 0);
  return {
    start: shiftDateKey(localDateKey(firstDay), -firstDay.getDay()),
    end: shiftDateKey(localDateKey(lastDay), 6 - lastDay.getDay()),
  };
}

function articlePublishedDateKey(article) {
  const value = article?.published_at || article?.publishedAt || "";
  if (!value) return "";
  const text = String(value).trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
  return localDateKey(text);
}

function previousDateKey(dateKey) {
  const date = new Date(`${dateKey}T12:00:00`);
  if (Number.isNaN(date.getTime())) return dateKey;
  date.setDate(date.getDate() - 1);
  return localDateKey(date);
}

function reportWindowForDate(dateKey, sendTime = "08:30") {
  const cleanDate = dateKey || localDateKey();
  const cleanTime = /^\d{2}:\d{2}$/.test(sendTime || "") ? sendTime : "08:30";
  const startKey = previousDateKey(cleanDate);
  return {
    startKey,
    endKey: cleanDate,
    from_at: `${startKey}T${cleanTime}:00+09:00`,
    to_at: `${cleanDate}T${cleanTime}:00+09:00`,
    label: `${startKey} ${cleanTime} ~ ${cleanDate} ${cleanTime}`,
  };
}

function reportWindowForRange(startDateKey, endDateKey, sendTime = "08:30") {
  const startWindow = reportWindowForDate(startDateKey, sendTime);
  const endWindow = reportWindowForDate(endDateKey, sendTime);
  return {
    startKey: startWindow.startKey,
    endKey: endWindow.endKey,
    from_at: startWindow.from_at,
    to_at: endWindow.to_at,
    label: `${startWindow.startKey} ${sendTime || "08:30"} ~ ${endWindow.endKey} ${sendTime || "08:30"}`,
  };
}

function getArticleUrl(article) {
  return article?.original_url || article?.url || article?.link || "";
}

function getArticleThumbnail(article) {
  return article?.thumbnail_url || article?.thumbnailUrl || article?.image_url || article?.image || "";
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

function donggukMailSubject(date = new Date()) {
  const weekdays = ["일", "월", "화", "수", "목", "금", "토"];
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `오늘의 주요 뉴스 ${year}.${month}.${day}.[${weekdays[date.getDay()]}]`;
}

function getDonggukRule(key) {
  return donggukCategoryRules.find((rule) => rule.key === key) || donggukCategoryRules[donggukCategoryRules.length - 1];
}

function donggukPriorityFromScore(score) {
  return donggukPriorityBands.find((band) => score >= band.min) || donggukPriorityBands[donggukPriorityBands.length - 1];
}

function donggukPriorityBandFromValue(value, score = 0) {
  const text = String(value || "").trim();
  return donggukPriorityBands.find((band) => band.label === text || band.name === text) || donggukPriorityFromScore(score);
}

function priorityDisplayName(articleOrBand) {
  return articleOrBand?.priorityName || articleOrBand?.name || "";
}

function formatInsightActionState(state = {}) {
  const labels = {
    position: "순서",
    priority: "우선순위",
    score: "점수",
    category: "하위 분류",
    section: "상위 분류",
    sectionLabel: "상위 분류",
    included: "메일 포함",
    trashed: "휴지통",
    title: "제목",
    summary: "요약",
  };
  return Object.entries(state)
    .map(([key, value]) => {
      if (key === "priority_criteria") return "AI 선정 기준 문안";
      const displayValue = typeof value === "boolean" ? (value ? "예" : "아니오") : String(value ?? "-");
      return `${labels[key] || key} ${displayValue}`;
    })
    .join(" · ");
}

function articlePriorityReason(article = {}) {
  const directReason = article.selectionReason || article.selection_reason || article.priorityReason || article.priority_reason;
  if (directReason) return directReason;
  const category = article.category || "기사 후보";
  const priorityName = priorityDisplayName(article) || "검토";
  const score = Number(article.score ?? 0);
  const details = [];
  if (/총장|이사장|기관장/.test(category)) details.push("기관장 메시지와 공식 발언 성격이 있어 홍보 가치가 높습니다");
  else if (/기부|장학|발전기금/.test(category)) details.push("기부·장학·발전기금 성격이라 학교 이미지와 직접 연결됩니다");
  else if (/연구|AI/.test(category)) details.push("연구 성과와 기술 키워드가 있어 성과 홍보에 적합합니다");
  else if (/협약|사업/.test(category)) details.push("기관 협력 또는 사업 선정 성격의 공식 기사입니다");
  else if (/수상|인증/.test(category)) details.push("수상·인증 성과 기사로 대외 신뢰도에 기여합니다");
  else if (/행사/.test(category)) details.push("학교 공식 행사 기사로 기본 홍보 가치가 있습니다");
  else if (/학술|입시|교육|인사|동문|교수|종단|기타/.test(category)) details.push("참고성 기사라 직접 홍보 기사보다 우선순위가 낮게 평가됩니다");
  if (article.isSyndicated) details.push("복수매체 보도 신호가 있습니다");
  if (article.isCampaign) details.push("진행 중 캠페인 키워드가 포함되어 있습니다");
  if (!details.length) details.push(score >= 64 ? "홍보처 기준에 맞는 주요 신호가 확인되었습니다" : "직접 홍보성과의 관련성이 상대적으로 낮습니다");
  return `${priorityName} 평가: ${details.join(", ")}.`;
}

function articleSimilarityTokens(article = {}) {
  const text = `${article.title || ""} ${article.summary || ""}`.toLowerCase();
  const stopwords = new Set(["동국대", "동국대학교", "기사", "보도", "개최", "진행", "관련", "위해", "이번", "통해", "있는", "대한", "한다", "했다", "에서", "으로", "하고"]);
  return new Set((text.match(/[가-힣A-Za-z0-9]{2,}/g) || []).filter((token) => !stopwords.has(token)));
}

function isSimilarDonggukArticle(left = {}, right = {}) {
  const leftLinks = realArticleLinks(left);
  const rightLinks = realArticleLinks(right);
  if (leftLinks.some((link) => rightLinks.includes(link))) return true;
  const leftTopic = representativeTopicKey(left);
  const rightTopic = representativeTopicKey(right);
  if (leftTopic && leftTopic === rightTopic) return true;
  const leftTokens = articleSimilarityTokens(left);
  const rightTokens = articleSimilarityTokens(right);
  if (!leftTokens.size || !rightTokens.size) return false;
  const shared = [...leftTokens].filter((token) => rightTokens.has(token)).length;
  const overlap = shared / Math.max(1, Math.min(leftTokens.size, rightTokens.size));
  const sameSource = left.source && right.source && left.source === right.source;
  const sameMinute = String(left.published_at || "").slice(0, 16) && String(left.published_at || "").slice(0, 16) === String(right.published_at || "").slice(0, 16);
  return overlap >= 0.42 || (sameSource && sameMinute && overlap >= 0.22);
}

function isAiDuplicateTopicExclusion(article = {}) {
  const reason = `${article.selectionReason || article.selection_reason || ""} ${article.reason || ""} ${article.summary || ""}`;
  return /같은\s*주제|동일\s*주제|중복\s*(?:기사|보도|주제)|동일\s*보도자료|반복\s*보도/.test(reason);
}

function aiDuplicateExcludedKeys(excludedArticles = [], candidates = []) {
  const duplicateRows = excludedArticles.filter(isAiDuplicateTopicExclusion);
  const keys = new Set();
  duplicateRows.forEach((excluded) => {
    const excludedLinks = realArticleLinks(excluded);
    const index = candidates.findIndex((candidate) => {
      const sameId = excluded.id && candidate.id && String(excluded.id) === String(candidate.id);
      const sameTitle = excluded.title && candidate.title && excluded.title === candidate.title;
      const sameLink = excludedLinks.some((link) => realArticleLinks(candidate).includes(link));
      return sameId || sameTitle || sameLink;
    });
    if (index >= 0) keys.add(articleKey(candidates[index], index));
  });
  return keys;
}

function candidateKeysForAiArticles(aiArticles = [], candidates = []) {
  return new Set(
    candidateIndexesForAiArticles(aiArticles, candidates)
      .map((index) => articleKey(candidates[index], index))
  );
}

function candidateIndexesForAiArticles(aiArticles = [], candidates = []) {
  const usedIndexes = new Set();
  const indexes = [];

  aiArticles.forEach((selected) => {
    const selectedLinks = realArticleLinks(selected).map(canonicalArticleUrl);
    const selectedPrimaryLink = selectedLinks[0] || "";
    const selectedTitle = normalizedArticleTitle(selected);
    const selectedSource = String(selected.source || "").replace(/\s+/g, " ").trim().toLowerCase();
    let bestIndex = -1;
    let bestScore = 0;

    candidates.forEach((candidate, index) => {
      if (usedIndexes.has(index)) return;
      const candidateLinks = realArticleLinks(candidate).map(canonicalArticleUrl);
      const candidatePrimaryLink = candidateLinks[0] || "";
      const candidateTitle = normalizedArticleTitle(candidate);
      const candidateSource = String(candidate.source || "").replace(/\s+/g, " ").trim().toLowerCase();
      const sameId = selected.id != null && candidate.id != null && String(selected.id) === String(candidate.id);
      const samePrimaryLink = Boolean(selectedPrimaryLink && selectedPrimaryLink === candidatePrimaryLink);
      const sameLink = selectedLinks.some((link) => candidateLinks.includes(link));
      const sameTitle = Boolean(selectedTitle && selectedTitle === candidateTitle);
      const sameSource = Boolean(selectedSource && selectedSource === candidateSource);
      const similarity = titleSimilarity(selected.title, candidate.title);

      let score = 0;
      if (sameId) score = 1000;
      else if (samePrimaryLink) score = 900;
      else if (sameLink) score = 800;
      else if (sameTitle && sameSource) score = 700;
      else if (sameTitle) score = 650;
      else if (sameSource && similarity >= 0.72) score = 500 + Math.round(similarity * 100);
      else if (similarity >= 0.82) score = 400 + Math.round(similarity * 100);

      if (score > bestScore) {
        bestIndex = index;
        bestScore = score;
      }
    });

    if (bestIndex >= 0) {
      usedIndexes.add(bestIndex);
      indexes.push(bestIndex);
    }
  });

  return indexes;
}

async function loadAllArticlePages(params = {}) {
  const size = 100;
  const first = await endpoints.articles({ ...params, page: 1, size });
  const items = [...(first?.items || [])];
  const total = Number(first?.page_info?.total ?? first?.total ?? items.length);
  const pageCount = Math.ceil(total / size);

  // Keep concurrent requests bounded so large archives do not overload the API.
  for (let start = 2; start <= pageCount; start += 5) {
    const pages = Array.from(
      { length: Math.min(5, pageCount - start + 1) },
      (_, offset) => start + offset
    );
    const results = await Promise.all(
      pages.map((page) => endpoints.articles({
        ...params,
        page,
        size,
        include_total: false,
      }))
    );
    results.forEach((result) => items.push(...(result?.items || [])));
  }

  return items;
}

function scoreDonggukArticle(article) {
  const rule = getDonggukRule(article.matchedType);
  const linkCount = article.links?.length || 0;
  const isSyndicated = linkCount >= 2 || String(article.source || "").includes("외");
  const isCampaign = /120주년|건학/.test(article.title);
  const rawScore = rule.score + (isSyndicated ? 10 : 0) + (isCampaign ? 8 : 0);
  const score = Math.max(0, Math.min(100, rawScore));
  const band = donggukPriorityFromScore(score);
  return {
    ...article,
    category: rule.label,
    baseScore: rule.score,
    score,
    priority: band.label,
    priorityName: band.name,
    priorityTone: band.tone,
    isSyndicated,
    isCampaign,
    sectionLabel: normalizeDonggukSectionLabel(article.section),
  };
}

function articleCollectedDateKey(article) {
  const value = article?.matched_at || article?.matchedAt || article?.collected_at || article?.collectedAt || "";
  if (!value) return "";
  const text = String(value).trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
  return localDateKey(text);
}

function articleReviewDateKey(article) {
  return articleCollectedDateKey(article) || articlePublishedDateKey(article);
}

function isDateWithinRange(value, startDate, endDate) {
  return Boolean(value && startDate && endDate && value >= startDate && value <= endDate);
}

function inferDonggukArticle(article) {
  const text = `${article.title || ""} ${article.summary || ""}`.toLowerCase();
  const researchContext = /전지|배터리|이온|소재|전극|수계아연|아연이온|논문|연구|개발|특허|ai/i.test(text);
  const rule = researchContext
    ? getDonggukRule("research")
    : donggukCategoryRules.find((item) =>
        item.key !== "other" && item.keywords.some((keyword) => text.includes(keyword.toLowerCase()))
      ) || getDonggukRule("other");
  const section =
    normalizeDonggukSectionKey(article.section)
    || (rule.key === "education_policy" || rule.key === "admission"
      ? "education"
      : rule.key === "buddhist_general"
        ? "buddhism"
        : "foundation");
  return scoreDonggukArticle({
    id: article.id,
    title: article.title || "제목 없음",
    section,
    source: article.source || article.publisher || "언론사 없음",
    url: getArticleUrl(article),
    thumbnail_url: getArticleThumbnail(article),
    links: [getArticleUrl(article)].filter(Boolean),
    summary: article.summary || "요약문이 아직 없습니다.",
    published_at: article.published_at,
    collected_at: article.collected_at || article.created_at || null,
    matched_at: article.matched_at || null,
    matchedType: rule.key,
  });
}

function normalizeDonggukTitle(title) {
  return String(title || "")
    .toLowerCase()
    .replace(/\[[^\]]+\]/g, "")
    .replace(/\([^)]*\)/g, "")
    .replace(/["'“”‘’]/g, "")
    .replace(/\b단독\b|\b종합\b|\b속보\b|\b인터뷰\b/g, "")
    .replace(/동국대|동국대학교/g, "동국대")
    .replace(/[^가-힣a-z0-9]/g, "");
}

function titleSimilarity(left, right) {
  const a = normalizeDonggukTitle(left);
  const b = normalizeDonggukTitle(right);
  if (!a || !b) return 0;
  if (a.includes(b) || b.includes(a)) return 1;
  const makeBigrams = (value) => Array.from({ length: Math.max(0, value.length - 1) }, (_, index) => value.slice(index, index + 2));
  const aSet = new Set(makeBigrams(a));
  const bSet = new Set(makeBigrams(b));
  const intersection = [...aSet].filter((item) => bSet.has(item)).length;
  const union = new Set([...aSet, ...bSet]).size || 1;
  return intersection / union;
}

function topicTokens(article) {
  const text = `${article.title || ""} ${article.summary || ""}`.toLowerCase();
  const stopWords = new Set(["동국대", "동국대학교", "연구", "개발", "교수", "연구팀", "기자", "관련", "통해", "위해", "대한", "지난"]);
  const words = text.match(/[가-힣a-z0-9]{2,}/g) || [];
  const compoundTokens = ["수계", "아연", "아연이온", "이온전지", "수계아연", "수계아연이온전지", "전지", "배터리", "전극", "소재", "의료영상", "인공지능", "ai"];
  const tokens = words
    .filter((word) => !stopWords.has(word))
    .filter((word) => word.length >= 2);
  compoundTokens.forEach((token) => {
    if (text.includes(token)) tokens.push(token);
  });
  return new Set(tokens);
}

function topicSimilarity(left, right) {
  const leftTokens = topicTokens(left);
  const rightTokens = topicTokens(right);
  const union = new Set([...leftTokens, ...rightTokens]);
  if (!union.size) return titleSimilarity(left.title, right.title);
  const intersection = [...leftTokens].filter((token) => rightTokens.has(token)).length;
  return Math.max(titleSimilarity(left.title, right.title), intersection / union.size);
}

function compactDonggukArticles(articles, maxCount = 8) {
  const groups = [];
  articles.forEach((article) => {
    const group = groups.find((item) => {
      if (item.representative.category !== article.category) return false;
      return topicSimilarity(item.representative, article) >= 0.34;
    });
    if (group) {
      group.items.push(article);
      if (article.score > group.representative.score) group.representative = article;
    } else {
      groups.push({ representative: article, items: [article] });
    }
  });

  return groups
    .map((group) => {
      const representative = group.representative;
      const sources = [...new Set(group.items.map((item) => item.source).filter(Boolean))];
      const links = [...new Set(group.items.flatMap((item) => item.links || []).filter(Boolean))];
      return {
        ...representative,
        source: sources.length > 1 ? `${sources[0]} 외` : representative.source,
        links,
        isSyndicated: sources.length > 1 || links.length > 1 || representative.isSyndicated,
        relatedCount: group.items.length,
      };
    })
    .sort((a, b) => b.score - a.score)
    .slice(0, maxCount);
}

function articleKey(article, index = 0) {
  return String(article?.id ?? article?.url ?? article?.title ?? index);
}

function realArticleLinks(article) {
  const links = article?.links?.length ? article.links : [article?.url].filter(Boolean);
  return [...new Set(links)]
    .map((link) => String(link || "").trim())
    .filter((link) => /^https?:\/\//i.test(link))
    .filter((link) => !/\/\/(?:www\.)?example\.com(?:\/|$)/i.test(link));
}

function canonicalArticleUrl(value = "") {
  try {
    const url = new URL(String(value).trim());
    url.hash = "";
    url.protocol = "https:";
    url.hostname = url.hostname.toLowerCase().replace(/^(?:www\.|m\.)/, "");
    url.pathname = url.pathname
      .replace(/\/+/g, "/")
      .replace(/\/(?:amp|mobile)\//gi, "/")
      .replace(/view_amp(?=\.)/gi, "view")
      .replace(/\/$/, "") || "/";
    const stableKeys = ["arcid", "idxno", "no", "article_id", "articleid", "aid", "id"];
    const stableKey = stableKeys.find((key) => url.searchParams.get(key));
    if (stableKey) {
      const stableValue = url.searchParams.get(stableKey);
      url.search = "";
      url.searchParams.set(stableKey, stableValue);
    } else {
      [...url.searchParams.keys()].forEach((key) => {
        if (/^utm_/i.test(key) || ["cp", "from", "gclid", "fbclid", "influxdiv", "medium", "ncid", "ocid", "ref", "source"].includes(key.toLowerCase())) {
          url.searchParams.delete(key);
        }
      });
      url.searchParams.sort();
    }
    return url.toString().replace(/\/$/, "");
  } catch {
    return String(value || "").split("#", 1)[0].replace(/\/$/, "").toLowerCase();
  }
}

function normalizedArticleTitle(article = {}) {
  const source = String(article.source || "").trim();
  let title = String(article.title || "").replace(/<[^>]+>/g, " ");
  if (source) title = title.replace(new RegExp(`\\s*[-|]\\s*${source.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*$`, "i"), "");
  title = title.replace(/\s*[-|]\s*(?:네이버\s*뉴스|구글\s*뉴스|뉴스)\s*$/i, "");
  return title.toLowerCase().replace(/[^0-9a-z가-힣]+/g, "");
}

function exactArticleIdentity(article = {}) {
  const firstLink = realArticleLinks(article)[0];
  if (firstLink) return `url:${canonicalArticleUrl(firstLink)}`;
  const title = normalizedArticleTitle(article);
  const source = String(article.source || "").replace(/\s+/g, " ").trim().toLowerCase();
  if (title && source) return `title-source:${title}|${source}`;
  if (article.id != null) return `id:${article.id}`;
  return `title:${String(article.title || "").trim().toLowerCase()}|${String(article.source || "").trim().toLowerCase()}`;
}

function dedupeExactArticles(articles = []) {
  const seenUrls = new Set();
  const seenTitles = new Set();
  return articles.filter((article) => {
    const firstLink = realArticleLinks(article)[0];
    const urlKey = firstLink ? canonicalArticleUrl(firstLink) : "";
    const titleKey = `${normalizedArticleTitle(article)}|${String(article.source || "").replace(/\s+/g, " ").trim().toLowerCase()}`;
    if ((urlKey && seenUrls.has(urlKey)) || (normalizedArticleTitle(article) && seenTitles.has(titleKey))) return false;
    if (urlKey) seenUrls.add(urlKey);
    if (normalizedArticleTitle(article)) seenTitles.add(titleKey);
    return true;
  });
}

function buildDonggukMailText(subject, articles) {
  const rows = articles.length ? articles : scoredFallbackDonggukArticles();
  return [
    subject,
    `대시보드: ${donggukDashboardUrl}`,
    "",
    ...Object.values(donggukSections).flatMap((section) => {
      const sectionRows = rows.filter((article) => article.sectionLabel === section);
      if (!sectionRows.length) return [];
      return [
        `[${section}]`,
        "",
        ...sectionRows.flatMap((article, index) => {
          const links = realArticleLinks(article);
          return [
            `${index + 1}. ${article.title} [${article.source || "언론사 없음"}]${article.isSyndicated ? " 외" : ""}`,
            article.summary || "요약문이 아직 없습니다.",
            ...links,
            "",
          ];
        }),
      ];
    }),
  ].join("\n").trim();
}

function scoredFallbackDonggukArticles() {
  return donggukDemoArticles.map(scoreDonggukArticle).sort((a, b) => b.score - a.score);
}

function donggukArticlePayload(article) {
  return {
    id: article.id,
    title: article.title,
    source: article.source,
    section: article.sectionLabel || article.section,
    category: article.category,
    summary: article.summary,
    url: article.url,
    thumbnail_url: getArticleThumbnail(article),
    published_at: article.published_at,
    collected_at: article.collected_at || null,
    matched_at: article.matched_at || null,
    links: realArticleLinks(article),
    priority: article.priority,
    priority_name: article.priorityName || article.priority_name,
    score: article.score,
    is_syndicated: article.isSyndicated ?? article.is_syndicated ?? false,
    selection_reason: article.selectionReason || article.selection_reason || article.priorityReason || article.priority_reason || null,
  };
}

function normalizeDonggukPreviewArticle(article) {
  const score = Math.max(0, Math.min(100, Number(article.score ?? 0)));
  const band = donggukPriorityBandFromValue(article.priority || article.priority_name || article.priorityName, score);
  const sectionLabel = normalizeDonggukSectionLabel(article.section || article.sectionLabel);
  const rawCategory = String(article.category || "").trim();
  const inferredCategory = inferDonggukArticle({ ...article, section: sectionLabel }).category;
  const category = donggukCategoryLabels.has(rawCategory)
    ? rawCategory
    : donggukCategoryAliases[rawCategory] || inferredCategory;
  return {
    ...article,
    section: sectionLabel,
    sectionLabel,
    category,
    priority: band.label,
    priorityName: article.priority_name || article.priorityName || band.name,
    priorityTone: band.tone,
    score,
    isSyndicated: article.is_syndicated ?? article.isSyndicated ?? realArticleLinks(article).length > 1,
    thumbnail_url: getArticleThumbnail(article),
    links: realArticleLinks(article),
    selectionReason: article.selection_reason || article.selectionReason || article.priority_reason || article.priorityReason || "",
  };
}

function countBy(items, keyFn) {
  return items.reduce((acc, item) => {
    const key = keyFn(item);
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
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
  activeTab,
  setActiveTab,
  dashboardMode,
  setDashboardMode,
  donggukViewMode,
  setDonggukViewMode,
  chatSidebarOpen,
  onOpenChat,
  onCreateKeyword,
  onUpdateKeyword,
  onDeleteKeyword,
  loading,
  collapsed,
  keywordArticleCountOverrides = {},
  donggukArticleSummary = {},
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
  const [guideOpen, setGuideOpen] = useState(false);
  const [keywordInput, setKeywordInput] = useState(defaultForm);
  const activeCount = keywords.filter((item) => item.is_active).length;
  const [keywordPage, setKeywordPage] = useState(1);
  const keywordPageSize = 4;
  const keywordPageCount = Math.max(1, Math.ceil(keywords.length / keywordPageSize));
  const shownKeywords = keywords.slice((keywordPage - 1) * keywordPageSize, keywordPage * keywordPageSize);

  useEffect(() => {
    setKeywordPage(1);
  }, [dashboardMode, keywords.length]);

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
      dashboard_mode: dashboardMode,
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

        <div className="mode-switch" role="tablist" aria-label="대시보드 모드">
          <button
            className={dashboardMode === "general" ? "active" : ""}
            onClick={() => {
              setDashboardMode("general");
              setActiveTab("stats");
            }}
            type="button"
          >
            일반
          </button>
          <button
            className={dashboardMode === "dongguk" ? "active" : ""}
            onClick={() => {
              setDashboardMode("dongguk");
              setActiveTab("dongguk");
              setDonggukViewMode("priority");
            }}
            type="button"
          >
            홍보처
          </button>
        </div>

        <nav className="dashboard-nav" aria-label="대시보드">
          <button
            className={
              (dashboardMode === "general" && activeTab === "stats")
              || (dashboardMode === "dongguk" && activeTab === "dongguk" && donggukViewMode === "home")
                ? "active"
                : ""
            }
            onClick={() => {
              if (dashboardMode === "dongguk") {
                setActiveTab("dongguk");
                setDonggukViewMode("home");
              } else {
                setActiveTab("stats");
              }
            }}
            type="button"
          >
            <Home size={18} />
            {!collapsed && <span>{dashboardMode === "dongguk" ? "설정" : "홈"}</span>}
          </button>
          <button
            className={
              (dashboardMode === "dongguk" && activeTab === "dongguk" && ["priority", "edit", "mail"].includes(donggukViewMode))
              || (dashboardMode === "general" && activeTab === "articles")
                ? "active"
                : ""
            }
            onClick={() => {
              if (dashboardMode === "dongguk") {
                setActiveTab("dongguk");
                setDonggukViewMode("priority");
              } else {
                setActiveTab("articles");
              }
            }}
            type="button"
          >
            <FileText size={18} />
            {!collapsed && <span>{dashboardMode === "dongguk" ? "오늘 수집된 기사" : "기사 모니터링"}</span>}
          </button>
          {dashboardMode === "dongguk" && (
            <button
              className={activeTab === "dongguk" && donggukViewMode === "collection" ? "active" : ""}
              onClick={() => {
                setActiveTab("dongguk");
                setDonggukViewMode("collection");
              }}
              type="button"
            >
              <RefreshCw size={18} />
              {!collapsed && <span>수집 상태</span>}
            </button>
          )}
          {dashboardMode === "dongguk" && (
            <button
              className={activeTab === "dongguk" && donggukViewMode === "calendar" ? "active" : ""}
              onClick={() => {
                setActiveTab("dongguk");
                setDonggukViewMode("calendar");
              }}
              type="button"
            >
              <Calendar size={18} />
              {!collapsed && <span>캘린더</span>}
            </button>
          )}
          {dashboardMode === "general" && (
            <button onClick={() => setActiveTab("stats")} type="button">
              <Hash size={18} />
              {!collapsed && <span>키워드 관리</span>}
            </button>
          )}
          {dashboardMode === "general" && (
            <button onClick={() => setActiveTab("stats")} type="button">
              <Mail size={18} />
              {!collapsed && <span>발송 관리</span>}
            </button>
          )}
          {dashboardMode === "dongguk" && (
            <button
              className={activeTab === "dongguk" && donggukViewMode === "history" ? "active" : ""}
              onClick={() => {
                setActiveTab("dongguk");
                setDonggukViewMode("history");
              }}
              type="button"
            >
              <Send size={18} />
              {!collapsed && <span>발송 기록</span>}
            </button>
          )}
          {dashboardMode === "dongguk" && (
            <button
              className={activeTab === "dongguk" && donggukViewMode === "trash" ? "active" : ""}
              onClick={() => {
                setActiveTab("dongguk");
                setDonggukViewMode("trash");
              }}
              type="button"
            >
              <Trash2 size={18} />
              {!collapsed && <span>휴지통</span>}
            </button>
          )}
          <button
            className={
              (dashboardMode === "dongguk" && activeTab === "dongguk" && donggukViewMode === "stats")
              || (dashboardMode === "general" && activeTab === "stats")
                ? "active"
                : ""
            }
            onClick={() => {
              if (dashboardMode === "dongguk") {
                setActiveTab("dongguk");
                setDonggukViewMode("stats");
              } else {
                setActiveTab("stats");
              }
            }}
            type="button"
          >
            <BarChart3 size={18} />
            {!collapsed && <span>{dashboardMode === "dongguk" ? "통계" : "통계/분석"}</span>}
          </button>
          <button className={chatSidebarOpen ? "active" : ""} onClick={onOpenChat} type="button">
            <MessageSquare size={18} />
            {!collapsed && <span>AI 채팅</span>}
          </button>
        </nav>

        {dashboardMode === "dongguk" && !collapsed && (
          <section className="side-section dongguk-today-summary">
            <div className="dongguk-today-summary-head">
              <div>
                <FileText size={16} />
                <strong>오늘 수집 기사 현황</strong>
              </div>
              <span>{String(donggukArticleSummary.date || "").replaceAll("-", ".")}</span>
            </div>
            <div className="dongguk-today-summary-total">
              <span>전체 수집</span>
              <strong>{Number(donggukArticleSummary.total || 0).toLocaleString()}건</strong>
            </div>
            <div className="dongguk-today-summary-rows">
              <div>
                <span>동국대·건학위</span>
                <b>{Number(donggukArticleSummary.sections?.[donggukSections.foundation] || 0).toLocaleString()}건</b>
              </div>
              <div>
                <span>대학·교육</span>
                <b>{Number(donggukArticleSummary.sections?.[donggukSections.education] || 0).toLocaleString()}건</b>
              </div>
              <div>
                <span>불교·종단</span>
                <b>{Number(donggukArticleSummary.sections?.[donggukSections.buddhism] || 0).toLocaleString()}건</b>
              </div>
            </div>
            <div className="dongguk-today-summary-mail">
              <CheckCircle2 size={15} />
              <span>메일 포함</span>
              <strong>{Number(donggukArticleSummary.mailIncluded || 0).toLocaleString()}건</strong>
            </div>
          </section>
        )}

        {dashboardMode === "general" && (
          <section className="side-section keyword-admin">
            {!collapsed && (
              <>
                <div className="keyword-group-head">
                  <span>키워드 목록</span>
                  <button className="secondary compact" onClick={openCreateModal} type="button">
                    <Plus size={14} /> 추가
                  </button>
                </div>

                <div className="keyword-checklist">
                  {shownKeywords.length === 0 && (
                    <div className="toc-empty">
                      <strong>저장된 키워드가 없습니다</strong>
                      <span>키워드를 추가하면 기사 목록과 함께 이곳에 표시됩니다.</span>
                    </div>
                  )}
                  {shownKeywords.map((keyword) => {
                    const selected = keyword.id === selectedKeywordId;
                    const todayArticleCount = Number(keywordArticleCountOverrides[keyword.id] ?? keyword.article_count ?? 0);
                    return (
                      <div className={`toc-row ${selected ? "selected" : ""}`} key={keyword.id}>
                        <button className="toc-select" onClick={() => setSelectedKeywordId(keyword.id)} type="button">
                          <Circle className="toc-dot" size={12} />
                          <span className="toc-title">{keywordName(keyword)}</span>
                          <span className="toc-summary">오늘 {todayArticleCount.toLocaleString()}건 · {keyword.is_active ? "활성" : "비활성"}</span>
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
                {keywordPageCount > 1 && (
                  <div className="keyword-pager">
                    <button className="secondary compact" disabled={keywordPage <= 1} onClick={() => setKeywordPage((page) => Math.max(1, page - 1))} type="button">
                      이전
                    </button>
                    <span>{keywordPage} / {keywordPageCount}</span>
                    <button className="secondary compact" disabled={keywordPage >= keywordPageCount} onClick={() => setKeywordPage((page) => Math.min(keywordPageCount, page + 1))} type="button">
                      다음
                    </button>
                  </div>
                )}
              </>
            )}
          </section>
        )}
        {!collapsed && (
          <div className="sidebar-guide">
            <button className="secondary" onClick={() => setGuideOpen(true)} type="button">
              <HelpCircle size={16} /> 사용자 가이드
            </button>
          </div>
        )}
      </aside>

      {guideOpen && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setGuideOpen(false)}>
          <div
            className="keyword-modal guide-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="user-guide-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="modal-heading">
              <div>
                <strong id="user-guide-title">사용자 가이드</strong>
                <span>{dashboardMode === "dongguk" ? "동국대학교 홍보처 전용 화면 기준 안내입니다." : "일반 기사 모니터링 화면 기준 안내입니다."}</span>
              </div>
              <button className="ghost" onClick={() => setGuideOpen(false)} title="닫기" type="button">
                <X size={18} />
              </button>
            </div>

            <div className="guide-content">
              <section className="guide-block highlight">
                <div>
                  <span className="guide-kicker">현재 모드</span>
                  <h3>{dashboardMode === "dongguk" ? "홍보처 모드" : "일반 모드"}</h3>
                </div>
                <p>
                  {dashboardMode === "dongguk"
                    ? "동국대학교 키워드를 기준으로 수집된 기사를 AI가 대표 기사로 정리하고, 관리자가 편집한 뒤 메일 미리보기와 발송 기록을 관리합니다."
                    : "등록한 키워드별 기사 수집, 통계 확인, 기사 모니터링, 일반 리포트 발송 관리를 한 화면에서 진행합니다."}
                </p>
              </section>

              <section className="guide-block">
                <h3>왼쪽 사이드바</h3>
                <ul>
                  <li><strong>일반 / 홍보처</strong>: 일반 모니터링과 홍보처 전용 대시보드를 전환합니다.</li>
                  {dashboardMode === "general" && (
                    <li><strong>키워드 목록</strong>: 등록된 키워드와 오늘 수집된 기사 수를 확인합니다. 4개 이상이면 페이지로 넘겨 볼 수 있습니다.</li>
                  )}
                  {dashboardMode === "dongguk" && (
                    <li><strong>홍보처 메뉴</strong>: 별도의 키워드를 선택하지 않고 설정, 수집 기사, 수집 상태, 캘린더, 발송 기록과 통계로 바로 이동합니다.</li>
                  )}
                  <li><strong>사이드바 열기·닫기</strong>: 상단 아이콘으로 사이드바를 숨겨 작업 공간을 넓히거나 다시 열 수 있습니다.</li>
                  <li><strong>AI 채팅</strong>: 오른쪽 채팅 패널을 열어 현재 서비스 사용 중 궁금한 점을 물어볼 수 있습니다.</li>
                  <li><strong>휴지통</strong>: 홍보처 모드에서 제외 후 휴지통으로 보낸 기사를 복구하거나 완전 삭제합니다.</li>
                </ul>
              </section>

              {dashboardMode === "dongguk" ? (
                <>
                  <section className="guide-block">
                    <h3>홍보처 작업 순서</h3>
                    <ol>
                      <li><strong>설정</strong>에서 기준일, 카테고리별 최대 기사 수, 수신인, 자동 발송 여부, 우선순위 기준을 정합니다.</li>
                      <li><strong>캘린더</strong>에서 학교 휴일과 개인 휴가를 등록합니다. 휴일 중에도 기사는 수집되며 다음 업무일 아침 메일에 함께 들어갑니다.</li>
                      <li><strong>오늘 수집된 기사</strong>에서 후보를 검색하고 페이지별로 확인한 뒤 메일 포함 여부를 선택합니다.</li>
                      <li><strong>수집 상태</strong>에서 분야별 기사 수집 여부를 확인하고, 누락이 의심되는 기간을 다시 수집합니다.</li>
                      <li>같은 화면 아래의 <strong>메일 미리보기</strong>에서 선택된 기사와 실제 발송 문안을 확인합니다.</li>
                      <li>미리보기의 <strong>편집</strong> 버튼으로 제목, 요약, 순서, 카테고리, 우선순위를 조정하고 URL 기사도 추가합니다.</li>
                      <li><strong>발송 기록</strong>에서 보낸 메일과 제외된 기사 수를 확인합니다. 메일 발송 시 한글 파일도 함께 첨부됩니다.</li>
                    </ol>
                  </section>
                  <section className="guide-block">
                    <h3>AI 편집 기준</h3>
                    <ul>
                      <li>AI는 같은 주제나 같은 보도자료 기사를 묶고 대표 기사 1건만 메일 후보로 남깁니다.</li>
                      <li>관리자가 저장한 우선순위 기준과 대표 기사 선정 기준이 AI 요청에 함께 전달됩니다.</li>
                      <li>한 번 생성된 메일 편집 결과는 발송용 데이터로 저장되어, 이후 화면 이동이나 새로고침 후에도 유지됩니다.</li>
                      <li>제외된 뉴스는 제외 이유를 확인한 뒤 다시 추가하거나 휴지통으로 이동할 수 있습니다.</li>
                    </ul>
                  </section>
                </>
              ) : (
                <>
                  <section className="guide-block">
                    <h3>일반 모니터링 흐름</h3>
                    <ol>
                      <li><strong>키워드 관리</strong>에서 모니터링 키워드, 수집 주기, 기사 수, 발송 조건을 등록합니다.</li>
                      <li><strong>기사 모니터링</strong>에서 수집된 기사 목록을 최신순, 중요도순, 감성 기준으로 확인합니다.</li>
                      <li><strong>통계/분석</strong>에서 기사 수, 조회 기사, SNS 신호, 감성 분포를 봅니다.</li>
                      <li><strong>발송 관리</strong>에서 리포트 수신인과 자동 발송 조건을 관리합니다.</li>
                    </ol>
                  </section>
                  <section className="guide-block">
                    <h3>키워드 등록 팁</h3>
                    <ul>
                      <li>클라이언트명과 그룹명을 함께 넣으면 여러 키워드를 구분하기 쉽습니다.</li>
                      <li>중요도 기준과 경쟁사 키워드를 입력하면 통계와 리포트 판단에 함께 반영됩니다.</li>
                      <li>자동 리포트는 정기 발송 외에도 부정 비중, 중요도, 기사량 조건을 활용할 수 있습니다.</li>
                    </ul>
                  </section>
                </>
              )}
            </div>
          </div>
        </div>
      )}

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
              <p>이 키워드로 등록된 AI 지식 문서도 함께 삭제를 시도합니다.</p>
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

function Articles({ selectedKeywordId, selectedKeyword, topItems, showToast, refreshSummary }) {
  const [articles, setArticles] = useState([]);
  const [pageInfo, setPageInfo] = useState(null);
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [articleDate, setArticleDate] = useState("");
  const [sort, setSort] = useState(sortOptions[0][1]);
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(20);
  const [busy, setBusy] = useState(false);
  const [running, setRunning] = useState("");
  const [details, setDetails] = useState({});
  const [deleteArticleTarget, setDeleteArticleTarget] = useState(null);
  const [manualUrl, setManualUrl] = useState("");
  const selectedSendTime = selectedKeyword?.email_send_time || "08:30";
  const rankMap = useMemo(() => new Map(topItems.map((item, index) => [item.article_id, index + 1])), [topItems]);

  async function loadArticles(overrides = {}) {
    if (!selectedKeywordId) return;
    setBusy(true);
    try {
      const nextPage = overrides.page ?? page;
      const nextSize = overrides.size ?? size;
      const nextSort = overrides.sort ?? sort;
      const nextDate = Object.prototype.hasOwnProperty.call(overrides, "articleDate") ? overrides.articleDate : articleDate;
      const nextQuery = Object.prototype.hasOwnProperty.call(overrides, "query") ? overrides.query : debouncedQuery;
      const dateWindow = nextDate ? reportWindowForDate(nextDate, selectedSendTime) : null;
      const data = await endpoints.articles({
        keyword_id: selectedKeywordId,
        page: nextPage,
        size: nextSize,
        sort: nextSort,
        ...(dateWindow ? { from_at: dateWindow.from_at, to_at: dateWindow.to_at } : {}),
        ...(nextQuery.trim() ? { q: nextQuery.trim() } : {}),
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
  }, [selectedKeywordId, page, size, sort, articleDate, selectedSendTime, debouncedQuery]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setPage(1);
      setDebouncedQuery(query.trim());
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

  async function addArticleFromUrl(event) {
    event.preventDefault();
    const url = manualUrl.trim();
    if (!selectedKeywordId) {
      showToast("키워드를 먼저 선택해 주세요.", "error");
      return;
    }
    if (!url) {
      showToast("추가할 기사 URL을 입력해 주세요.", "error");
      return;
    }
    setRunning("manual-url");
    try {
      const result = await endpoints.createArticleFromUrl({
        keyword_id: selectedKeywordId,
        url,
      });
      setManualUrl("");
      setArticleDate("");
      setQuery("");
      setSort("published_at_desc");
      setPage(1);
      await loadArticles({ page: 1, sort: "published_at_desc", articleDate: "", query: "" });
      refreshSummary?.();
      const article = result?.article;
      showToast(
        `${result?.created ? "새 기사로 저장했습니다." : "기존 기사에 키워드를 연결했습니다."} 요약/우선순위 분석을 완료했습니다.${article?.title ? ` (${article.title})` : ""}`,
        "success"
      );
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
      await endpoints.moveDonggukTrash({
        keyword_id: selectedKeywordId,
        mail_date: articleDate || localDateKey(),
        article: donggukArticlePayload(deleteArticleTarget),
      });
      showToast("기사를 휴지통으로 이동했습니다.", "success");
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
          <label className="inline-date-filter">
            <span>날짜 선택</span>
            <input type="date" value={articleDate} onChange={(event) => { setArticleDate(event.target.value); setPage(1); }} />
          </label>
          {articleDate && (
            <button className="secondary compact" onClick={() => setArticleDate("")} type="button">
              전체 날짜
            </button>
          )}
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

      <form className="manual-url-panel" onSubmit={addArticleFromUrl}>
        <div>
          <strong>URL로 기사 추가</strong>
          <span>크롤링되지 않은 기사 URL을 넣으면 원문을 수집하고 요약과 우선순위를 바로 생성합니다.</span>
        </div>
        <div className="manual-url-controls">
          <input
            value={manualUrl}
            onChange={(event) => setManualUrl(event.target.value)}
            placeholder="https://news.example.com/article"
          />
          <button className="primary" disabled={running === "manual-url"} type="submit">
            {running === "manual-url" ? <Loader2 className="spin" size={16} /> : <Plus size={16} />}
            기사 추가
          </button>
        </div>
      </form>

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
            const thumbnailUrl = getArticleThumbnail(article);
            return (
              <article className="article-card" key={articleId}>
                <div className={`article-main ${rank ? "has-rank" : "no-rank"}`}>
                  {rank && <div className="rank-badge">{rank}</div>}
                  {thumbnailUrl && (
                    <img
                      className="article-thumbnail"
                      src={thumbnailUrl}
                      alt=""
                      loading="lazy"
                      onError={(event) => {
                        event.currentTarget.style.display = "none";
                      }}
                    />
                  )}
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
                  <button className="danger ghost-action" title="휴지통으로 이동" onClick={() => setDeleteArticleTarget(article)} type="button">
                    <Trash2 size={15} />
                    휴지통
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
                <strong id="delete-article-title">휴지통으로 이동</strong>
                <span>기사는 일반 목록에서 숨겨지고 휴지통에서 복구할 수 있습니다.</span>
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
              <strong>이동 후 처리</strong>
              <p>기사와 관련 분석 데이터는 삭제되지 않고 그대로 보관됩니다.</p>
              <p>데이터베이스에서 완전히 지우려면 휴지통 화면에서 영구 삭제를 선택해야 합니다.</p>
            </div>
            <div className="modal-actions">
              <button className="secondary" disabled={running === "delete"} onClick={() => setDeleteArticleTarget(null)} type="button">취소</button>
              <button className="danger solid" disabled={running === "delete"} onClick={confirmDeleteArticle} type="button">
                {running === "delete" ? <Loader2 className="spin" size={16} /> : <Trash2 size={16} />}
                휴지통으로 이동
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

function Stats({ selectedKeywordId, selectedKeyword, selectedKeywordName, showToast }) {
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
  const statsLoadRequestRef = useRef(0);
  const selectedSendTime = selectedKeyword?.email_send_time || "08:30";

  async function load() {
    const requestId = ++statsLoadRequestRef.current;
    setBusy(true);
    try {
      const reportDateKey = localDateKey();
      const reportWindow = reportWindowForDate(reportDateKey, selectedSendTime);
      const dailyArticleParams = {
        page: 1,
        size: 100,
        sort: "importance_desc",
        from_at: reportWindow.from_at,
        to_at: reportWindow.to_at,
      };
      if (selectedKeywordId) dailyArticleParams.keyword_id = selectedKeywordId;
      const [priorityData, dailyData, dailyHourlyData] = await Promise.all([
        selectedKeywordId
          ? endpoints.articles({ keyword_id: selectedKeywordId, page: 1, size: 8, sort: "importance_desc", include_total: false })
          : Promise.resolve({ items: [] }),
        endpoints.articles(dailyArticleParams),
        endpoints.articleHourlyStats(reportDateKey, selectedKeywordId, reportWindow),
      ]);
      if (requestId !== statsLoadRequestRef.current) return;
      setPriorityArticles(priorityData.items || []);
      setDailyArticles(dailyData.items || []);
      setDailyPage(dailyData.page_info || null);
      setDailyHourlyArticles(dailyHourlyData || []);
      setExpandedDailyArticleId(null);

      const [articles, analysis, searchVolume] = await Promise.all([
        endpoints.articleStats(days),
        endpoints.analysisStats(days),
        endpoints.searchVolume(),
      ]);
      if (requestId !== statsLoadRequestRef.current) return;
      setArticleStats(articles || {});
      setAnalysisStats(analysis || {});
      setVolume(searchVolume || []);

      const [searchTrend, pendingData, dailySocialData] = await Promise.all([
        endpoints.searchVolumeTrend(days * 24),
        endpoints.pendingAnalysis(),
        endpoints.dailySocialStats(reportDateKey, selectedKeywordId, reportWindow),
      ]);
      if (requestId !== statsLoadRequestRef.current) return;
      setVolumeTrend(searchTrend || []);
      setDailySocialMetrics(dailySocialData || []);
      setPending(pendingData?.pending_count || 0);
    } catch (err) {
      if (requestId === statsLoadRequestRef.current) showToast(err.message, "error");
    } finally {
      if (requestId === statsLoadRequestRef.current) setBusy(false);
    }
  }

  useEffect(() => {
    load();
  }, [days, selectedKeywordId, selectedSendTime]);

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
  const baseDateKey = localDateKey();
  const baseReportWindow = reportWindowForDate(baseDateKey, selectedSendTime);
  const previousBaseDateKey = previousDateKey(baseDateKey);
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
    `${selectedKeywordLabel} 기준 ${baseDateKey} 수집 기준 기사(${baseReportWindow.label})는 ${baseDateArticleTotal}건입니다.`,
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
          note={`${baseReportWindow.label} KST 발행 기사 수, 합계 ${baseDateArticleHourlyTotal}건`}
          onExpand={() => setExpandedChart({
            title: `${selectedKeywordLabel} 기준일 발행 기사 추이`,
            data: baseDateArticleHourlyRows,
            xKey: "hour",
            yKey: "total_count",
            type: "bar",
            color: "#2271b1",
            note: `${baseReportWindow.label} KST 발행 기사 수, 합계 ${baseDateArticleHourlyTotal}건`,
          })}
        />
        <ChartCard
          title={`${selectedKeywordLabel} 기준일 SNS 조회 수`}
          data={dailySocialRows}
          xKey="source_label"
          yKey="count"
          type="bar"
          color="#3858e9"
          note={`${baseReportWindow.label} KST SNS 플랫폼별 조회/언급 수, 합계 ${dailySocialTotal}건`}
          onExpand={() => setExpandedChart({
            title: `${selectedKeywordLabel} 기준일 SNS 조회 수`,
            data: dailySocialRows,
            xKey: "source_label",
            yKey: "count",
            type: "bar",
            color: "#3858e9",
            note: `${baseReportWindow.label} KST SNS 플랫폼별 조회/언급 수, 합계 ${dailySocialTotal}건`,
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

function ChartVisual({
  data,
  xKey,
  yKey,
  type = "bar",
  color = "#2563eb",
  height = 220,
  seriesName = "",
  valueSuffix = "",
}) {
  const tooltipFormatter = seriesName
    ? (value) => [`${value}${valueSuffix}`, seriesName]
    : undefined;
  return (
    <ResponsiveContainer height={height} width="100%">
      {type === "line" ? (
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey={xKey} tick={{ fontSize: 11 }} />
          <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
          <Tooltip formatter={tooltipFormatter} />
          <Line dataKey={yKey} name={seriesName || yKey} stroke={color} strokeWidth={2.5} type="monotone" />
        </LineChart>
      ) : (
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey={xKey} tick={{ fontSize: 11 }} />
          <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
          <Tooltip formatter={tooltipFormatter} />
          <Bar dataKey={yKey} name={seriesName || yKey} fill={color} radius={[4, 4, 0, 0]} />
        </BarChart>
      )}
    </ResponsiveContainer>
  );
}

function representativeTopicKey(article = {}) {
  const title = String(article.title || "").replace(/\s+/g, " ").trim();
  const patterns = [
    ["meditation-retreat", /하안거|30일\s*수행|선.?교\s*겸수/i],
    ["lotus-donation", /로터스관.*(?:기부|희사|발전기금)|(?:기부|희사).*로터스관/i],
    ["mongolia-heritage-camp", /청년\s*문화유산\s*캠프|몽골.*(?:한[·\-\s]*몽\s*청년|문화유산\s*캠프)|한[·\-\s]*몽\s*청년.*(?:몽골|건학\s*120주년)/i],
    ["iot-degree", /지능\s*IoT|공동학위/i],
    ["meditation-expo", /서울국제명상엑스포|명상,?\s*함께\s*깨어나다|명상엑스포/i],
    ["anchor-goyang", /경기앵커|앵커사업단|고양산업진흥원|지역성장\s*인재양성체계/i],
  ];
  return patterns.find(([, pattern]) => pattern.test(title))?.[0] || "";
}

function areRepresentativeDuplicates(left = {}, right = {}) {
  const leftLinks = realArticleLinks(left).map(canonicalArticleUrl);
  const rightLinks = new Set(realArticleLinks(right).map(canonicalArticleUrl));
  if (leftLinks.some((link) => rightLinks.has(link))) return true;
  const leftTopic = representativeTopicKey(left);
  const rightTopic = representativeTopicKey(right);
  if (leftTopic && leftTopic === rightTopic) return true;
  const leftTokens = new Set((String(left.title || "").toLowerCase().match(/[가-힣A-Za-z0-9]{2,}/g) || []).filter((token) => !["동국대", "동국대학교"].includes(token)));
  const rightTokens = new Set((String(right.title || "").toLowerCase().match(/[가-힣A-Za-z0-9]{2,}/g) || []).filter((token) => !["동국대", "동국대학교"].includes(token)));
  const shared = [...leftTokens].filter((token) => rightTokens.has(token)).length;
  return shared >= 3 && shared / Math.max(1, Math.min(leftTokens.size, rightTokens.size)) >= 0.7;
}

function dedupeRepresentativeArticles(articles = []) {
  const kept = [];
  dedupeExactArticles(articles).forEach((article) => {
    const matchIndex = kept.findIndex((candidate) => areRepresentativeDuplicates(candidate, article));
    if (matchIndex < 0) {
      kept.push(article);
      return;
    }
    const current = kept[matchIndex];
    const representative = Number(article.score || 0) > Number(current.score || 0) ? article : current;
    const links = [...new Set([...realArticleLinks(representative), ...realArticleLinks(representative === article ? current : article)])];
    kept[matchIndex] = {
      ...representative,
      links,
      isSyndicated: links.length > 1 || representative.isSyndicated,
    };
  });
  return kept;
}

function sanitizeDonggukMailArticles(articles, limits) {
  return applyDonggukSectionLimits(dedupeRepresentativeArticles(articles), limits);
}

function hasChartValues(data, yKey) {
  return Boolean(data?.length && data.some((item) => {
    const value = Number(item?.[yKey]);
    return Number.isFinite(value) && value !== 0;
  }));
}

function ChartCard({
  title,
  data,
  xKey,
  yKey,
  type = "bar",
  color = "#2563eb",
  note = "",
  onExpand,
  seriesName = "",
  valueSuffix = "",
}) {
  const hasData = hasChartValues(data, yKey);
  return (
    <div className={`chart-card ${hasData ? "" : "chart-card-empty"}`}>
      <div className="panel-heading">
        <div>
          <strong>{title}</strong>
          <span>{note || `${data?.length || 0}개 항목`}</span>
        </div>
        <button className="icon-button" disabled={!hasData || !onExpand} title="그래프 크게 보기" onClick={onExpand}>
          <Maximize2 size={15} />
        </button>
      </div>
      {!hasData ? (
        <EmptyState title="집계된 기사가 없습니다" body="기사가 수집되면 이곳에 통계가 표시됩니다." />
      ) : (
        <ChartVisual
          data={data}
          xKey={xKey}
          yKey={yKey}
          type={type}
          color={color}
          seriesName={seriesName}
          valueSuffix={valueSuffix}
        />
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

function DonggukPrConsole({ selectedKeyword, selectedKeywordId, selectedKeywordName, showToast, onUpdateKeyword, viewMode, setViewMode, onCandidateCountChange }) {
  const [emails, setEmails] = useState("");
  const [testEmails, setTestEmails] = useState("");
  const [autoSendEnabled, setAutoSendEnabled] = useState(false);
  const [autoSendTime, setAutoSendTime] = useState("08:30");
  const [mailDate, setMailDate] = useState(localDateKey());
  const [workWindow, setWorkWindow] = useState(null);
  const [loadingWorkWindow, setLoadingWorkWindow] = useState(false);
  const [schoolHolidays, setSchoolHolidays] = useState([]);
  const [schoolHolidayForm, setSchoolHolidayForm] = useState({
    name: "",
    holiday_type: "personal",
    start_date: localDateKey(),
    end_date: localDateKey(),
  });
  const [savingSchoolHoliday, setSavingSchoolHoliday] = useState(false);
  const [calendarMonth, setCalendarMonth] = useState(localDateKey().slice(0, 7));
  const [calendarDays, setCalendarDays] = useState([]);
  const [loadingCalendar, setLoadingCalendar] = useState(false);
  const [sending, setSending] = useState(false);
  const [savingAuto, setSavingAuto] = useState(false);
  const [savingPriorityCriteria, setSavingPriorityCriteria] = useState(false);
  const [loadingCandidates, setLoadingCandidates] = useState(false);
  const [runningCandidateCrawl, setRunningCandidateCrawl] = useState(false);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [workspaceMailPreviewOpen, setWorkspaceMailPreviewOpen] = useState(false);
  const [previewArticles, setPreviewArticles] = useState([]);
  const [previewExcludedArticles, setPreviewExcludedArticles] = useState([]);
  const [previewExcludedCount, setPreviewExcludedCount] = useState(0);
  const [previewEditorUsed, setPreviewEditorUsed] = useState(false);
  const [previewCached, setPreviewCached] = useState(false);
  const [aiProcessedArticleCount, setAiProcessedArticleCount] = useState(0);
  const [draftLoaded, setDraftLoaded] = useState(false);
  const [candidateArticles, setCandidateArticles] = useState([]);
  const [candidateSortIncludedKeys, setCandidateSortIncludedKeys] = useState(new Set());
  const [candidateSortSnapshotReady, setCandidateSortSnapshotReady] = useState(false);
  const [exactLinkDuplicateCount, setExactLinkDuplicateCount] = useState(0);
  const [trashArticles, setTrashArticles] = useState([]);
  const [selectedArticleKeys, setSelectedArticleKeys] = useState(new Set());
  const [history, setHistory] = useState([]);
  const [recentRecipients, setRecentRecipients] = useState([]);
  const [activeDonggukCategory, setActiveDonggukCategory] = useState("전체");
  const [activeDonggukSubcategory, setActiveDonggukSubcategory] = useState("전체");
  const [categoryArticleLimits, setCategoryArticleLimits] = useState(defaultDonggukSectionLimits);
  const [maxVisibleCandidates, setMaxVisibleCandidates] = useState(10);
  const [candidateSearchQuery, setCandidateSearchQuery] = useState("");
  const [candidatePage, setCandidatePage] = useState(1);
  const [duplicateExcludedKeys, setDuplicateExcludedKeys] = useState(new Set());
  const [duplicateFilterNeedsRefresh, setDuplicateFilterNeedsRefresh] = useState(false);
  const [manualArticleUrl, setManualArticleUrl] = useState("");
  const [addingManualArticle, setAddingManualArticle] = useState(false);
  const [inlineEditingArticleKey, setInlineEditingArticleKey] = useState("");
  const [inlineArticleDraft, setInlineArticleDraft] = useState(null);
  const [savingInlineArticle, setSavingInlineArticle] = useState(false);
  const [editDirty, setEditDirty] = useState(false);
  const editBaselineArticles = useRef([]);
  const [priorityCriteria, setPriorityCriteria] = useState("");
  const criteriaBaselineRef = useRef("");
  const [priorityRuleItems, setPriorityRuleItems] = useState(defaultPriorityRuleItems);
  const [representativeRuleItems, setRepresentativeRuleItems] = useState(defaultRepresentativeRuleItems);
  const [exclusionRuleItems, setExclusionRuleItems] = useState(defaultExclusionRuleItems);
  const [newPriorityRule, setNewPriorityRule] = useState("");
  const [newRepresentativeRule, setNewRepresentativeRule] = useState("");
  const [newExclusionRule, setNewExclusionRule] = useState("");
  const [draggedPriorityIndex, setDraggedPriorityIndex] = useState(null);
  const [recipientContextMenu, setRecipientContextMenu] = useState(null);
  const [priorityContextMenu, setPriorityContextMenu] = useState(null);
  const [priorityInsights, setPriorityInsights] = useState([]);
  const [activeInsightRules, setActiveInsightRules] = useState([]);
  const [priorityInsightCadence, setPriorityInsightCadence] = useState({});
  const [selectedPriorityInsightId, setSelectedPriorityInsightId] = useState(null);
  const [priorityInsightDetail, setPriorityInsightDetail] = useState(null);
  const [loadingPriorityInsights, setLoadingPriorityInsights] = useState(false);
  const [generatingPriorityInsight, setGeneratingPriorityInsight] = useState(false);
  const autoPreviewRequestKey = useRef("");
  const candidateLoadRequestId = useRef(0);
  const thumbnailRefreshAttemptedIds = useRef(new Set());
  const historySummaryLoadedRef = useRef(false);
  const scoredArticles = useMemo(
    () => scoredFallbackDonggukArticles(),
    []
  );
  const selectedCandidates = useMemo(
    () => candidateArticles.filter((article, index) => !article.isTrashed && selectedArticleKeys.has(articleKey(article, index))),
    [candidateArticles, selectedArticleKeys]
  );
  const workingArticles = useMemo(
    () => (candidateArticles.length ? selectedCandidates : scoredArticles),
    [candidateArticles.length, selectedCandidates, scoredArticles]
  );
  const mailArticles = useMemo(
    () => (candidateArticles.length ? applyDonggukSectionLimits(selectedCandidates, categoryArticleLimits) : []),
    [candidateArticles.length, selectedCandidates, categoryArticleLimits]
  );
  const effectiveMailArticles = useMemo(
    () => sanitizeDonggukMailArticles(previewArticles.length ? previewArticles : mailArticles, categoryArticleLimits),
    [previewArticles, mailArticles, categoryArticleLimits]
  );
  const maxMailArticleTotal = useMemo(
    () => Object.values(categoryArticleLimits).reduce((total, value) => total + Number(value || 0), 0),
    [categoryArticleLimits]
  );
  const mailArticleKeySet = useMemo(() => {
    return new Set(
      candidateIndexesForAiArticles(effectiveMailArticles, candidateArticles)
        .map((index) => articleKey(candidateArticles[index], index))
    );
  }, [effectiveMailArticles, candidateArticles]);
  useEffect(() => {
    if (candidateSortSnapshotReady || loadingCandidates || loadingPreview || !draftLoaded) return;
    const eligibleCount = candidateArticles.filter(
      (article) => !article.isTrashed && realArticleLinks(article).length > 0
    ).length;
    const aiSelectionReady = !eligibleCount
      || aiProcessedArticleCount >= eligibleCount
      || Boolean(autoPreviewRequestKey.current);
    if (!aiSelectionReady) return;
    setCandidateSortIncludedKeys(new Set(mailArticleKeySet));
    setCandidateSortSnapshotReady(true);
  }, [
    candidateSortSnapshotReady,
    loadingCandidates,
    loadingPreview,
    draftLoaded,
    candidateArticles,
    aiProcessedArticleCount,
    mailArticleKeySet,
  ]);
  const candidateRows = useMemo(
    () => candidateArticles.map((article, index) => ({ article, index, key: articleKey(article, index) })),
    [candidateArticles]
  );
  const excludedHomeRows = useMemo(
    () => candidateRows.filter(({ article, key }) => !mailArticleKeySet.has(key)),
    [candidateRows, mailArticleKeySet]
  );
  const editedMailArticles = previewArticles.length ? previewArticles : [];
  const sectionCounts = countBy(workingArticles, (item) => item.sectionLabel);
  const priorityCounts = countBy(workingArticles, (item) => item.priority);
  const categoryCounts = countBy(workingArticles, (item) => item.category);
  const totalLinks = workingArticles.reduce((total, item) => total + (item.links?.length || 0), 0);
  const syndicatedCount = workingArticles.filter((item) => item.isSyndicated).length;
  const leadArticle = effectiveMailArticles[0] || workingArticles[0];
  const selectedMailDate = useMemo(() => new Date(`${mailDate}T12:00:00`), [mailDate]);
  const mailSubject = donggukMailSubject(selectedMailDate);
  const recipientList = useMemo(
    () => emails.replaceAll(",", "\n").split("\n").map((item) => item.trim()).filter(Boolean),
    [emails]
  );
  const testRecipientList = useMemo(
    () => testEmails.replaceAll(",", "\n").split("\n").map((item) => item.trim()).filter(Boolean),
    [testEmails]
  );
  const selectedArticleKeySignature = useMemo(
    () => [...selectedArticleKeys].map(String).sort().join("|"),
    [selectedArticleKeys]
  );
  const sectionChart = Object.values(donggukSections).map((label) => ({ label, count: sectionCounts[label] || 0 }));
  const priorityChart = donggukPriorityBands.map((band) => ({ label: band.label, count: priorityCounts[band.label] || 0 }));
  const aiSelectedCandidateRows = useMemo(
    () => candidateRows.filter(({ article, key }) => !article.isTrashed && selectedArticleKeys.has(key)),
    [candidateRows, selectedArticleKeys]
  );
  const aiSelectedCandidateArticles = useMemo(
    () => aiSelectedCandidateRows.map(({ article }) => article),
    [aiSelectedCandidateRows]
  );
  const candidateCategoryTabs = useMemo(() => {
    const counts = countBy(candidateArticles, (item) => item.sectionLabel || "미분류");
    const orderedLabels = Object.values(donggukSections);
    const extraLabels = Object.keys(counts).filter((label) => !orderedLabels.includes(label));
    return [
      { label: "전체", count: candidateArticles.length },
      ...orderedLabels.map((label) => ({ label, count: counts[label] || 0 })),
      ...extraLabels.map((label) => ({ label, count: counts[label] || 0 })),
    ];
  }, [candidateArticles]);
  const candidateSubcategoryTabs = useMemo(() => {
    if (activeDonggukCategory === "전체") return [];
    const scoped = candidateArticles.filter((article) => article.sectionLabel === activeDonggukCategory);
    const counts = countBy(scoped, (item) => item.category || "미분류");
    const orderedLabels = donggukCategoryRules.map((rule) => rule.label);
    const usedLabels = [
      ...orderedLabels.filter((label) => counts[label] || scoped.some((article) => article.category === label)),
      ...Object.keys(counts).filter((label) => !orderedLabels.includes(label)),
    ];
    return [
      { label: "전체", count: scoped.length },
      ...usedLabels.map((label) => ({ label, count: counts[label] || 0 })),
    ];
  }, [candidateArticles, activeDonggukCategory]);
  const filteredCandidateRows = useMemo(
    () => candidateRows.filter(({ article }) => {
      const sectionMatched = activeDonggukCategory === "전체" || article.sectionLabel === activeDonggukCategory;
      const subcategoryMatched = activeDonggukSubcategory === "전체" || article.category === activeDonggukSubcategory;
      const searchText = candidateSearchQuery.trim().toLocaleLowerCase("ko");
      const searchMatched = !searchText || [
        article.title,
        article.summary,
        article.source,
        article.category,
        article.sectionLabel,
      ].some((value) => String(value || "").toLocaleLowerCase("ko").includes(searchText));
      return sectionMatched && subcategoryMatched && searchMatched;
    }),
    [candidateRows, activeDonggukCategory, activeDonggukSubcategory, candidateSearchQuery]
  );
  const sortedCandidateRows = useMemo(
    () => [...filteredCandidateRows].sort((left, right) => {
      const sortIncludedKeys = candidateSortSnapshotReady ? candidateSortIncludedKeys : mailArticleKeySet;
      const leftIncluded = sortIncludedKeys.has(left.key) ? 1 : 0;
      const rightIncluded = sortIncludedKeys.has(right.key) ? 1 : 0;
      if (leftIncluded !== rightIncluded) return rightIncluded - leftIncluded;
      const scoreDifference = Number(right.article.score || 0) - Number(left.article.score || 0);
      if (scoreDifference) return scoreDifference;
      return String(articleReviewDateKey(right.article) || "").localeCompare(String(articleReviewDateKey(left.article) || ""));
    }),
    [filteredCandidateRows, candidateSortSnapshotReady, candidateSortIncludedKeys, mailArticleKeySet]
  );
  const candidatePageSize = Math.max(1, maxVisibleCandidates);
  const candidateTotalPages = Math.max(1, Math.ceil(sortedCandidateRows.length / candidatePageSize));
  const normalizedCandidatePage = Math.min(candidatePage, candidateTotalPages);
  const visibleCandidateRows = useMemo(
    () => {
      const start = (normalizedCandidatePage - 1) * candidatePageSize;
      return sortedCandidateRows.slice(start, start + candidatePageSize);
    },
    [sortedCandidateRows, normalizedCandidatePage, candidatePageSize]
  );
  const duplicateExcludedCount = useMemo(
    () => candidateRows.filter(({ key }) => duplicateExcludedKeys.has(key)).length,
    [candidateRows, duplicateExcludedKeys]
  );
  const aiSelectedCount = aiSelectedCandidateRows.length;
  const aiExcludedCount = Math.max(0, candidateArticles.length - aiSelectedCount);

  async function loadDonggukHistory(summaryOnly = viewMode !== "history", force = false) {
    if (summaryOnly && historySummaryLoadedRef.current && !force) return;
    try {
      const data = await endpoints.donggukHistory(summaryOnly);
      if (!summaryOnly) setHistory(data.items || []);
      setRecentRecipients(data.recent_recipients || []);
      historySummaryLoadedRef.current = true;
    } catch (err) {
      showToast?.(err.message, "error");
    }
  }

  useEffect(() => {
    loadDonggukHistory(viewMode !== "history");
  }, [viewMode]);

  useEffect(() => {
    if (!selectedKeywordId || !onCandidateCountChange) return undefined;
    if (!draftLoaded) return undefined;
    const sections = Object.values(donggukSections).reduce((counts, label) => {
      counts[label] = candidateArticles.filter((article) => article.sectionLabel === label && !article.isTrashed).length;
      return counts;
    }, {});
    onCandidateCountChange(selectedKeywordId, {
      date: mailDate,
      total: candidateArticles.filter((article) => !article.isTrashed).length,
      sections,
      mailIncluded: effectiveMailArticles.length,
    });
    return undefined;
  }, [selectedKeywordId, candidateArticles, draftLoaded, effectiveMailArticles.length, mailDate]);

  useEffect(() => {
    setActiveDonggukSubcategory("전체");
  }, [activeDonggukCategory]);

  useEffect(() => {
    if (candidatePage > candidateTotalPages) setCandidatePage(candidateTotalPages);
  }, [candidatePage, candidateTotalPages]);

  async function loadDonggukTrash(targetMailDate = mailDate, keywordId = selectedKeywordId, requestId = null) {
    if (!targetMailDate || !keywordId) {
      if (requestId == null || requestId === candidateLoadRequestId.current) setTrashArticles([]);
      return [];
    }
    try {
      const data = await endpoints.donggukTrash({
        keyword_id: keywordId,
        mail_date: targetMailDate,
      });
      const rows = (data.items || []).map((item) => ({
        ...item,
        article: normalizeDonggukPreviewArticle(item.article || {}),
      }));
      if (requestId == null || requestId === candidateLoadRequestId.current) setTrashArticles(rows);
      return rows;
    } catch (err) {
      if (requestId == null || requestId === candidateLoadRequestId.current) {
        showToast?.(err.message, "error");
        setTrashArticles([]);
      }
      return [];
    }
  }

  useEffect(() => {
    setAutoSendEnabled(Boolean(selectedKeyword?.email_auto_send));
    setAutoSendTime(selectedKeyword?.email_send_time || "08:30");
    setEmails((selectedKeyword?.email_recipients || []).join("\n"));
    const nextCriteria = normalizeDonggukCriteria(selectedKeyword?.importance_criteria);
    const nextPriorityRules = priorityRulesFromCriteria(nextCriteria);
    const nextRepresentativeRules = representativeRulesFromCriteria(nextCriteria);
    const nextExclusionRules = exclusionRulesFromCriteria(nextCriteria);
    setPriorityRuleItems(nextPriorityRules);
    setRepresentativeRuleItems(nextRepresentativeRules);
    setExclusionRuleItems(nextExclusionRules);
    const normalizedCriteria = criteriaFromRuleGroups(nextPriorityRules, nextRepresentativeRules, nextExclusionRules);
    setPriorityCriteria(normalizedCriteria);
    criteriaBaselineRef.current = normalizedCriteria;
  }, [selectedKeywordId, selectedKeyword]);

  async function loadPriorityInsights(selectId = selectedPriorityInsightId) {
    if (!selectedKeywordId) {
      setPriorityInsights([]);
      setActiveInsightRules([]);
      setPriorityInsightDetail(null);
      return;
    }
    setLoadingPriorityInsights(true);
    try {
      const data = await endpoints.priorityInsights({ keyword_id: selectedKeywordId, limit: 24 });
      const items = data.items || [];
      setPriorityInsights(items);
      setActiveInsightRules(data.active_rules || []);
      setPriorityInsightCadence(data.cadence || {});
      const nextId = selectId || items[0]?.id || null;
      setSelectedPriorityInsightId(nextId);
      if (nextId) {
        const detail = await endpoints.priorityInsight(nextId);
        setPriorityInsightDetail(detail);
      } else {
        setPriorityInsightDetail(null);
      }
    } catch (err) {
      showToast?.(err.message, "error");
    } finally {
      setLoadingPriorityInsights(false);
    }
  }

  async function openPriorityInsight(insightId) {
    setSelectedPriorityInsightId(insightId);
    setLoadingPriorityInsights(true);
    try {
      setPriorityInsightDetail(await endpoints.priorityInsight(insightId));
    } catch (err) {
      showToast?.(err.message, "error");
    } finally {
      setLoadingPriorityInsights(false);
    }
  }

  async function generatePriorityInsight() {
    if (!selectedKeywordId) return;
    setGeneratingPriorityInsight(true);
    try {
      const result = await endpoints.runPriorityInsight({
        keyword_id: selectedKeywordId,
        cadence: "monthly",
        force: true,
      });
      await loadPriorityInsights(result.id);
      showToast?.(
        result.changes?.length
          ? `지난달 행동을 분석해 우선순위 기준 ${result.changes.length}개를 소폭 반영했습니다.`
          : "지난달 행동을 분석했지만 반복 근거가 충분하지 않아 기준은 유지했습니다.",
        "success"
      );
    } catch (err) {
      showToast?.(err.message, "error");
    } finally {
      setGeneratingPriorityInsight(false);
    }
  }

  async function deletePriorityInsight(insight) {
    const confirmed = window.confirm(
      `${insight.period_key} 인사이트의 기준 반영을 삭제할까요?\n근거가 된 사용자 행동 로그는 감사 기록으로 남습니다.`
    );
    if (!confirmed) return;
    try {
      await endpoints.deletePriorityInsight(insight.id);
      await loadPriorityInsights(insight.id);
      showToast?.("AI 인사이트의 기준 반영을 취소했습니다. 근거 로그는 보존됩니다.", "success");
    } catch (err) {
      showToast?.(err.message, "error");
    }
  }

  useEffect(() => {
    if (viewMode === "stats") {
      loadPriorityInsights();
    }
  }, [viewMode, selectedKeywordId]);

  useEffect(() => {
    function closeMenus() {
      setRecipientContextMenu(null);
      setPriorityContextMenu(null);
    }
    window.addEventListener("click", closeMenus);
    window.addEventListener("scroll", closeMenus, true);
    return () => {
      window.removeEventListener("click", closeMenus);
      window.removeEventListener("scroll", closeMenus, true);
    };
  }, []);

  const workWindowMatchesMailDate = workWindow?.target_date === mailDate;
  const activeRangeStart = workWindowMatchesMailDate ? workWindow.start_date : mailDate;
  const activeRangeEnd = workWindowMatchesMailDate ? workWindow.end_date : mailDate;
  const activeArticleWindow = useMemo(
    () => reportWindowForRange(activeRangeStart, activeRangeEnd, autoSendTime),
    [activeRangeStart, activeRangeEnd, autoSendTime]
  );
  const monthCalendarRange = useMemo(() => calendarGridRange(calendarMonth), [calendarMonth]);
  const calendarDayMap = useMemo(
    () => new Map(calendarDays.map((item) => [item.date, item])),
    [calendarDays]
  );
  const calendarCells = useMemo(() => {
    if (!monthCalendarRange) return [];
    const cells = [];
    let cursor = monthCalendarRange.start;
    while (cursor <= monthCalendarRange.end && cells.length < 42) {
      const day = calendarDayMap.get(cursor) || {
        date: cursor,
        is_business_day: true,
        is_weekend: [0, 6].includes(new Date(`${cursor}T12:00:00`).getDay()),
        school_holiday_names: [],
        personal_holiday_names: [],
      };
      cells.push({
        ...day,
        isCurrentMonth: cursor.startsWith(calendarMonth),
        isToday: cursor === localDateKey(),
      });
      cursor = shiftDateKey(cursor, 1);
    }
    return cells;
  }, [monthCalendarRange, calendarDayMap, calendarMonth]);
  const calendarMonthLabel = useMemo(() => {
    const [year, month] = calendarMonth.split("-");
    return `${year}년 ${Number(month)}월`;
  }, [calendarMonth]);

  useEffect(() => {
    setCandidatePage(1);
  }, [
    activeDonggukCategory,
    activeDonggukSubcategory,
    candidateSearchQuery,
    maxVisibleCandidates,
    activeRangeStart,
    activeRangeEnd,
  ]);

  function isArticleInActiveRange(article) {
    const value = article?.published_at || article?.publishedAt || article?.collected_at || article?.collectedAt;
    if (!value) return false;
    const timestamp = new Date(value).getTime();
    const start = new Date(activeArticleWindow.from_at).getTime();
    const end = new Date(activeArticleWindow.to_at).getTime();
    return Number.isFinite(timestamp) && timestamp >= start && timestamp <= end;
  }

  async function loadWorkWindow(targetDate = mailDate) {
    if (!targetDate) return null;
    setLoadingWorkWindow(true);
    try {
      const data = await endpoints.workWindow(targetDate);
      setWorkWindow(data);
      return data;
    } catch (err) {
      setWorkWindow({
        target_date: targetDate,
        start_date: targetDate,
        end_date: targetDate,
        is_target_business_day: true,
        days: [],
      });
      showToast?.(`업무일 범위를 불러오지 못했습니다: ${err.message}`, "error");
      return null;
    } finally {
      setLoadingWorkWindow(false);
    }
  }

  async function loadSchoolHolidays(targetDate = mailDate) {
    const year = Number(String(targetDate || localDateKey()).slice(0, 4));
    if (!year) return;
    try {
      const data = await endpoints.schoolHolidays({
        from: `${year}-01-01`,
        to: `${year}-12-31`,
      });
      setSchoolHolidays(data.items || []);
    } catch (err) {
      showToast?.(err.message, "error");
    }
  }

  async function loadCalendarDays(targetMonth = calendarMonth) {
    const range = calendarGridRange(targetMonth);
    if (!range) return;
    setLoadingCalendar(true);
    try {
      const data = await endpoints.calendarDays({ from: range.start, to: range.end });
      setCalendarDays(data.items || []);
    } catch (err) {
      setCalendarDays([]);
      showToast?.(`캘린더를 불러오지 못했습니다: ${err.message}`, "error");
    } finally {
      setLoadingCalendar(false);
    }
  }

  useEffect(() => {
    setWorkWindow(null);
    setLoadingCandidates(true);
    loadWorkWindow(mailDate);
    loadSchoolHolidays(mailDate);
  }, [mailDate]);

  useEffect(() => {
    if (viewMode !== "calendar") return;
    loadCalendarDays(calendarMonth);
    loadSchoolHolidays(`${calendarMonth}-01`);
  }, [viewMode, calendarMonth]);

  async function createSchoolHoliday() {
    const { name, holiday_type, start_date, end_date } = schoolHolidayForm;
    if (!name.trim() || !start_date || !end_date) {
      showToast?.("휴일 이름과 기간을 입력해 주세요.", "error");
      return;
    }
    if (start_date > end_date) {
      showToast?.("휴일 시작일은 종료일보다 늦을 수 없습니다.", "error");
      return;
    }
    setSavingSchoolHoliday(true);
    try {
      await endpoints.createSchoolHoliday({
        name: name.trim(),
        holiday_type,
        start_date,
        end_date,
      });
      setSchoolHolidayForm({
        name: "",
        holiday_type: "personal",
        start_date: end_date,
        end_date,
      });
      await Promise.all([
        loadSchoolHolidays(`${calendarMonth}-01`),
        loadCalendarDays(calendarMonth),
        loadWorkWindow(mailDate),
      ]);
      showToast?.(
        holiday_type === "personal"
          ? "개인 휴가를 등록했습니다. 다음 업무일 아침 메일에 휴가 기간 기사가 포함됩니다."
          : "학교 휴일을 등록했습니다.",
        "success"
      );
    } catch (err) {
      showToast?.(err.message, "error");
    } finally {
      setSavingSchoolHoliday(false);
    }
  }

  async function removeSchoolHoliday(id) {
    if (!window.confirm("이 휴일을 삭제할까요?")) return;
    try {
      await endpoints.deleteSchoolHoliday(id);
      await Promise.all([
        loadSchoolHolidays(`${calendarMonth}-01`),
        loadCalendarDays(calendarMonth),
        loadWorkWindow(mailDate),
      ]);
      showToast?.("휴일을 삭제했습니다.", "success");
    } catch (err) {
      showToast?.(err.message, "error");
    }
  }

  async function editSchoolHoliday(item) {
    const name = window.prompt("휴일 이름", item.name);
    if (name === null) return;
    const startDate = window.prompt("시작일 (YYYY-MM-DD)", item.start_date);
    if (startDate === null) return;
    const endDate = window.prompt("종료일 (YYYY-MM-DD)", item.end_date);
    if (endDate === null) return;
    if (!name.trim() || !/^\d{4}-\d{2}-\d{2}$/.test(startDate) || !/^\d{4}-\d{2}-\d{2}$/.test(endDate) || startDate > endDate) {
      showToast?.("휴일 이름과 기간을 확인해 주세요.", "error");
      return;
    }
    try {
      await endpoints.updateSchoolHoliday(item.id, {
        name: name.trim(),
        holiday_type: item.holiday_type || "school",
        start_date: startDate,
        end_date: endDate,
      });
      await Promise.all([
        loadSchoolHolidays(`${calendarMonth}-01`),
        loadCalendarDays(calendarMonth),
        loadWorkWindow(mailDate),
      ]);
      showToast?.("휴일을 수정했습니다.", "success");
    } catch (err) {
      showToast?.(err.message, "error");
    }
  }

  function moveCalendarMonth(amount) {
    const date = new Date(`${calendarMonth}-01T12:00:00`);
    date.setMonth(date.getMonth() + amount);
    setCalendarMonth(localDateKey(date).slice(0, 7));
  }

  function selectCalendarDate(dateKey) {
    setSchoolHolidayForm((prev) => ({
      ...prev,
      start_date: dateKey,
      end_date: dateKey,
    }));
  }

  async function loadCandidateArticles() {
    const requestId = ++candidateLoadRequestId.current;
    setCandidateSortSnapshotReady(false);
    setCandidateSortIncludedKeys(new Set());
    autoPreviewRequestKey.current = "";
    if (!selectedKeywordId || !mailDate) {
      setLoadingCandidates(false);
      setCandidateArticles([]);
      setExactLinkDuplicateCount(0);
      setSelectedArticleKeys(new Set());
      setPreviewArticles([]);
      setPreviewExcludedArticles([]);
      setPreviewExcludedCount(0);
      setPreviewEditorUsed(false);
      setPreviewCached(false);
      setAiProcessedArticleCount(0);
      setDraftLoaded(false);
      setDuplicateExcludedKeys(new Set());
      setDuplicateFilterNeedsRefresh(false);
      return [];
    }
    setLoadingCandidates(true);
    try {
      const collectedItems = await loadAllArticlePages({
        keyword_id: selectedKeywordId,
        sort: "importance_desc",
        from_at: activeArticleWindow.from_at,
        to_at: activeArticleWindow.to_at,
      });
      if (requestId !== candidateLoadRequestId.current) return [];
      const byArticleKey = new Map();
      collectedItems.forEach((item) => {
        const article = inferDonggukArticle(item);
        byArticleKey.set(exactArticleIdentity(article), article);
      });
      setExactLinkDuplicateCount(Math.max(0, collectedItems.length - byArticleKey.size));
      const rawRows = [...byArticleKey.values()].sort((a, b) => b.score - a.score);
      const trashRows = await loadDonggukTrash(mailDate, selectedKeywordId, requestId);
      if (requestId !== candidateLoadRequestId.current) return [];
      const trashedIds = new Set(trashRows.map((item) => String(item.article_id || item.article?.id)));
      const rows = rawRows.map((article) => ({
        ...article,
        isTrashed: trashedIds.has(String(article.id)),
      }));
      const mailableKeySet = new Set(
        rows
          .map((article, index) => ({ article, key: articleKey(article, index) }))
          .filter(({ article }) => !article.isTrashed && isArticleInActiveRange(article))
          .map(({ key }) => key)
      );
      let restoredRows = rows;
      setActiveDonggukCategory("전체");
      setPreviewArticles([]);
      setPreviewExcludedCount(0);
      setPreviewEditorUsed(false);
      setPreviewCached(false);
      setDraftLoaded(false);
      try {
        const draft = await endpoints.donggukDraft({
          keyword_id: selectedKeywordId,
          mail_date: mailDate,
        });
        if (requestId !== candidateLoadRequestId.current) return [];
        if (draft?.found) {
          const currentArticleIds = new Set(rows.map((article) => String(article.id)).filter(Boolean));
          const savedArticles = [
            ...(draft.selected_articles || []),
            ...(draft.removed_articles || []),
          ].map(normalizeDonggukPreviewArticle)
            .filter((article) => currentArticleIds.has(String(article.id)))
            .filter((article) => isArticleInActiveRange(article));
          const byKey = new Map();
          rows.forEach((article, index) => byKey.set(articleKey(article, index), article));
          savedArticles.forEach((article, index) => {
            const key = articleKey(article, index);
            if (!byKey.has(key)) byKey.set(key, article);
          });
          restoredRows = [...byKey.values()];
          setCandidateArticles(restoredRows);
          const availableKeys = new Set(restoredRows.map((article, index) => articleKey(article, index)));
          const draftSelectedKeys = (draft.selected_article_keys || []).map(String);
          const draftRemovedKeys = (draft.removed_article_keys || []).map(String);
          const restoredMailableKeySet = new Set(
              restoredRows
                .map((article, index) => ({ article, key: articleKey(article, index) }))
              .filter(({ article }) => !article.isTrashed && isArticleInActiveRange(article))
                .map(({ key }) => key)
          );
          const restoredKeys = draftSelectedKeys.filter((key) => availableKeys.has(key) && restoredMailableKeySet.has(key));
          const removedKeys = new Set(draftRemovedKeys.filter((key) => availableKeys.has(key)));
          const nextKeys = draftSelectedKeys.length
            ? restoredKeys
            : restoredRows
                .map((article, index) => articleKey(article, index))
                .filter((key) => restoredMailableKeySet.has(key) && !removedKeys.has(key));
          setSelectedArticleKeys(new Set(nextKeys));
          const preview = draft.preview_data;
          const restoredSectionLimits = donggukSectionLimitsFromPayload(preview?.section_limits, categoryArticleLimits);
          if (preview?.section_limits) setCategoryArticleLimits(restoredSectionLimits);
          const aiExcluded = (preview?.excluded_articles || draft.removed_articles || []).map(normalizeDonggukPreviewArticle);
          const aiSelected = (preview?.articles || draft.selected_articles || []).map(normalizeDonggukPreviewArticle);
          const aiSelectedKeys = candidateKeysForAiArticles(aiSelected, restoredRows);
          setPreviewExcludedArticles(aiExcluded);
          setDuplicateExcludedKeys(aiDuplicateExcludedKeys(aiExcluded, restoredRows));
          setAiProcessedArticleCount(aiSelected.length + aiExcluded.length);
          if (preview?.articles?.length && nextKeys.length && preview.editor_used !== false) {
            setPreviewArticles(sanitizeDonggukMailArticles(
              (preview.articles || []).map(normalizeDonggukPreviewArticle).filter((article) => isArticleInActiveRange(article)),
              restoredSectionLimits
            ));
            if (aiSelectedKeys.size) setSelectedArticleKeys(aiSelectedKeys);
            setPreviewExcludedCount(Number(preview.excluded_count || 0));
            setPreviewEditorUsed(Boolean(preview.editor_used));
            setPreviewCached(true);
          } else {
            setPreviewArticles([]);
            setPreviewExcludedCount(0);
            setPreviewEditorUsed(false);
            setPreviewCached(false);
          }
          setDraftLoaded(true);
        } else {
          setCandidateArticles(restoredRows);
          setSelectedArticleKeys(mailableKeySet);
          setPreviewExcludedArticles([]);
          setDuplicateExcludedKeys(new Set());
          setAiProcessedArticleCount(0);
          setDraftLoaded(true);
        }
      } catch (err) {
        if (requestId !== candidateLoadRequestId.current) return [];
        setCandidateArticles(restoredRows);
        setSelectedArticleKeys(mailableKeySet);
        setPreviewExcludedArticles([]);
        setDuplicateExcludedKeys(new Set());
        setAiProcessedArticleCount(0);
        setDraftLoaded(true);
        showToast?.(err.message, "error");
      }
      setDuplicateFilterNeedsRefresh(false);
      refreshMissingThumbnails(restoredRows);
      return restoredRows;
    } catch (err) {
      if (requestId === candidateLoadRequestId.current) {
        setExactLinkDuplicateCount(0);
        showToast?.(err.message, "error");
      }
      return [];
    } finally {
      if (requestId === candidateLoadRequestId.current) setLoadingCandidates(false);
    }
  }

  async function runDonggukCandidateCrawl() {
    if (!selectedKeywordId) {
      showToast?.("키워드를 먼저 선택해 주세요.", "error");
      return;
    }
    setRunningCandidateCrawl(true);
    try {
      const result = await endpoints.runCrawl(selectedKeywordId);
      showToast?.(`새 기사 확인을 요청했습니다. 수집 ${result.crawl_count ?? 0}건`, "success");
      await loadCandidateArticles();
    } catch (err) {
      showToast?.(err.message, "error");
    } finally {
      setRunningCandidateCrawl(false);
    }
  }

  async function refreshMissingThumbnails(rows) {
    const missingIds = rows
      .filter((article) => article.id && realArticleLinks(article).length && !getArticleThumbnail(article))
      .map((article) => Number(article.id))
      .filter((articleId) => !thumbnailRefreshAttemptedIds.current.has(articleId))
      .slice(0, 12);
    if (!missingIds.length) return;
    missingIds.forEach((articleId) => thumbnailRefreshAttemptedIds.current.add(articleId));
    try {
      const result = await endpoints.refreshArticleThumbnails(missingIds);
      const refreshed = result.items || {};
      if (!Object.keys(refreshed).length) return;
      setCandidateArticles((prev) => prev.map((article) => {
        const nextThumbnail = refreshed[String(article.id)];
        return nextThumbnail ? { ...article, thumbnail_url: nextThumbnail } : article;
      }));
      setPreviewArticles((prev) => prev.map((article) => {
        const nextThumbnail = refreshed[String(article.id)];
        return nextThumbnail ? { ...article, thumbnail_url: nextThumbnail } : article;
      }));
    } catch (err) {
      console.warn("thumbnail refresh failed", err);
    }
  }

  useEffect(() => {
    if (!workWindowMatchesMailDate) return;
    loadCandidateArticles();
  }, [selectedKeywordId, mailDate, activeRangeStart, activeRangeEnd, workWindowMatchesMailDate]);

  useEffect(() => {
    if (!previewArticles.length) return;
    const next = sanitizeDonggukMailArticles(previewArticles, categoryArticleLimits);
    const currentSignature = previewArticles.map((article) => exactArticleIdentity(article)).join("|");
    const nextSignature = next.map((article) => exactArticleIdentity(article)).join("|");
    if (currentSignature === nextSignature) return;
    setPreviewArticles(next);
    saveEditedPreview(next, "settings-limit");
  }, [categoryArticleLimits, previewArticles]);

  function addRecipient(email) {
    const current = emails.replaceAll(",", "\n").split("\n").map((item) => item.trim()).filter(Boolean);
    if (!current.includes(email)) current.push(email);
    setEmails(current.join("\n"));
  }

  function updateRecipient(index, value) {
    const nextValue = value.trim();
    if (!nextValue) return;
    const current = emails.replaceAll(",", "\n").split("\n").map((item) => item.trim()).filter(Boolean);
    current[index] = nextValue;
    setEmails([...new Set(current)].join("\n"));
  }

  function deleteRecipient(index) {
    const current = emails.replaceAll(",", "\n").split("\n").map((item) => item.trim()).filter(Boolean);
    setEmails(current.filter((_, itemIndex) => itemIndex !== index).join("\n"));
  }

  function updateCategoryLimit(section, value) {
    const nextValue = Math.max(0, Math.min(30, Number(value) || 0));
    setCategoryArticleLimits((prev) => ({ ...prev, [section]: nextValue }));
  }

  function syncCriteria(nextPriority = priorityRuleItems, nextRepresentative = representativeRuleItems, nextExclusion = exclusionRuleItems) {
    setPriorityCriteria(criteriaFromRuleGroups(nextPriority, nextRepresentative, nextExclusion));
  }

  function movePriorityRule(fromIndex, toIndex) {
    if (fromIndex === null || fromIndex === toIndex) return;
    setPriorityRuleItems((prev) => {
      const next = [...prev];
      const [moved] = next.splice(fromIndex, 1);
      next.splice(toIndex, 0, moved);
      syncCriteria(next, representativeRuleItems, exclusionRuleItems);
      return next;
    });
  }

  function addPriorityRule() {
    const value = newPriorityRule.trim();
    if (!value) return;
    setPriorityRuleItems((prev) => {
      if (prev.includes(value)) return prev;
      const next = [...prev, value];
      syncCriteria(next, representativeRuleItems, exclusionRuleItems);
      return next;
    });
    setNewPriorityRule("");
  }

  function deletePriorityRule(index) {
    setPriorityRuleItems((prev) => {
      const next = prev.filter((_, itemIndex) => itemIndex !== index);
      syncCriteria(next, representativeRuleItems, exclusionRuleItems);
      return next;
    });
  }

  function updatePriorityRule(index, value) {
    setPriorityRuleItems((prev) => {
      const next = [...prev];
      next[index] = value;
      syncCriteria(next, representativeRuleItems, exclusionRuleItems);
      return next;
    });
  }

  function addRepresentativeRule() {
    const value = newRepresentativeRule.trim();
    if (!value) return;
    setRepresentativeRuleItems((prev) => {
      if (prev.includes(value)) return prev;
      const next = [...prev, value];
      syncCriteria(priorityRuleItems, next, exclusionRuleItems);
      return next;
    });
    setNewRepresentativeRule("");
  }

  function updateRepresentativeRule(index, value) {
    setRepresentativeRuleItems((prev) => {
      const next = prev.map((rule, itemIndex) => itemIndex === index ? value : rule);
      syncCriteria(priorityRuleItems, next, exclusionRuleItems);
      return next;
    });
  }

  function deleteRepresentativeRule(index) {
    setRepresentativeRuleItems((prev) => {
      const next = prev.filter((_, itemIndex) => itemIndex !== index);
      syncCriteria(priorityRuleItems, next, exclusionRuleItems);
      return next;
    });
  }

  function addExclusionRule(valueOverride = "") {
    const value = (valueOverride || newExclusionRule).trim();
    if (!value) return;
    setExclusionRuleItems((prev) => {
      if (prev.includes(value)) return prev;
      const next = [...prev, value];
      syncCriteria(priorityRuleItems, representativeRuleItems, next);
      return next;
    });
    setNewExclusionRule("");
  }

  function updateExclusionRule(index, value) {
    setExclusionRuleItems((prev) => {
      const next = prev.map((rule, itemIndex) => itemIndex === index ? value : rule);
      syncCriteria(priorityRuleItems, representativeRuleItems, next);
      return next;
    });
  }

  function deleteExclusionRule(index) {
    setExclusionRuleItems((prev) => {
      const next = prev.filter((_, itemIndex) => itemIndex !== index);
      syncCriteria(priorityRuleItems, representativeRuleItems, next);
      return next;
    });
  }

  function openRecipientContext(event, index) {
    event.preventDefault();
    event.stopPropagation();
    setPriorityContextMenu(null);
    setRecipientContextMenu({ index, x: event.clientX, y: event.clientY });
  }

  function openPriorityContext(event, index) {
    event.preventDefault();
    event.stopPropagation();
    setRecipientContextMenu(null);
    setPriorityContextMenu({ index, x: event.clientX, y: event.clientY });
  }

  function editRecipientFromMenu(index) {
    const current = recipientList[index] || "";
    const next = window.prompt("수신인 이메일 수정", current);
    if (next !== null) updateRecipient(index, next);
    setRecipientContextMenu(null);
  }

  function focusPriorityRule(index) {
    window.setTimeout(() => {
      document.querySelector(`[data-priority-rule-index="${index}"]`)?.focus();
    }, 0);
    setPriorityContextMenu(null);
  }

  function copyMailPreview() {
    const articles = effectiveMailArticles;
    if (!articles.length) {
      showToast?.("복사할 메일 기사가 없습니다.", "error");
      return;
    }
    const body = buildDonggukMailText(mailSubject, articles);
    navigator.clipboard?.writeText(body);
    showToast?.("제목, 요약, URL이 포함된 홍보처 메일 문안을 복사했습니다.", "success");
  }

  function updateCandidateArticle(index, patch) {
    setCandidateArticles((prev) => prev.map((article, idx) => {
      if (idx !== index) return article;
      const next = { ...article, ...patch };
      if (patch.sectionLabel) next.section = patch.sectionLabel;
      return next;
    }));
    setPreviewArticles([]);
    setPreviewExcludedCount(0);
    setPreviewEditorUsed(false);
    setPreviewCached(false);
  }

  function beginInlineArticleEdit(article, index) {
    setInlineEditingArticleKey(articleKey(article, index));
    setInlineArticleDraft(cloneArticles([article])[0]);
  }

  function cancelInlineArticleEdit() {
    setInlineEditingArticleKey("");
    setInlineArticleDraft(null);
  }

  async function saveInlineArticleEdit(article, index) {
    if (!inlineArticleDraft) return;
    setSavingInlineArticle(true);
    try {
      const previousKey = articleKey(article, index);
      const updatedArticle = normalizeDonggukPreviewArticle({
        ...article,
        ...inlineArticleDraft,
        section: inlineArticleDraft.sectionLabel || inlineArticleDraft.section,
      });
      const nextCandidates = candidateArticles.map((item, itemIndex) => (
        itemIndex === index ? updatedArticle : item
      ));
      const nextKey = articleKey(updatedArticle, index);
      const nextSelectedKeys = new Set(selectedArticleKeys);
      if (nextSelectedKeys.delete(previousKey)) nextSelectedKeys.add(nextKey);

      const matchesEditedArticle = (item) => {
        if (article.id && item.id) return String(article.id) === String(item.id);
        const itemLinks = realArticleLinks(item);
        return realArticleLinks(article).some((link) => itemLinks.includes(link))
          || (article.title && item.title && article.title === item.title);
      };
      const nextPreviewArticles = previewArticles.map((item) => (
        matchesEditedArticle(item) ? updatedArticle : item
      ));
      const previewData = nextPreviewArticles.length
        ? {
            articles: nextPreviewArticles.map(donggukArticlePayload),
            excluded_articles: previewExcludedArticles,
            article_count: nextPreviewArticles.length,
            excluded_count: previewExcludedCount,
            editor_used: previewEditorUsed,
            cached: true,
            manually_edited: true,
          }
        : null;

      setCandidateArticles(nextCandidates);
      setSelectedArticleKeys(nextSelectedKeys);
      if (nextPreviewArticles.length) setPreviewArticles(nextPreviewArticles);
      await saveDraftSelection(nextSelectedKeys, previewData, nextCandidates, "single-article-edit");
      cancelInlineArticleEdit();
      showToast?.("기사 수정사항을 저장했습니다.", "success");
    } catch (err) {
      showToast?.(err.message, "error");
    } finally {
      setSavingInlineArticle(false);
    }
  }

  async function setCandidateMailIncluded(article, index, included) {
    try {
      if (!candidateSortSnapshotReady) {
        setCandidateSortIncludedKeys(new Set(mailArticleKeySet));
        setCandidateSortSnapshotReady(true);
      }
      const key = articleKey(article, index);
      if (included) {
        await restoreExcludedArticle(article, index);
        return;
      }
      const nextKeys = new Set([...selectedArticleKeys].filter((item) => item !== key));
      setSelectedArticleKeys(nextKeys);
      setPreviewArticles([]);
      setPreviewExcludedCount(0);
      setPreviewEditorUsed(false);
      setPreviewCached(false);
      await saveDraftSelection(nextKeys, null, candidateArticles, "today");
      showToast?.("이번 메일에서 기사를 제외했습니다.", "success");
    } catch (err) {
      showToast?.(err.message, "error");
    }
  }

  async function deleteCandidateArticle(article, index) {
    if (!article?.id || String(article.id).startsWith("manual-")) {
      showToast?.("데이터베이스에 저장되지 않은 임시 기사는 휴지통으로 이동할 수 없습니다.", "error");
      return;
    }
    const confirmed = window.confirm("이 기사를 휴지통으로 이동할까요? 휴지통에서 다시 복구할 수 있습니다.");
    if (!confirmed) return;
    await moveExcludedArticleToTrash(article, index);
  }

  function excludedArticleReason(article, key) {
    if (!isArticleInActiveRange(article)) {
      const articleDate = articleReviewDateKey(article);
      return articleDate
        ? `기사 확인일이 ${articleDate}라 현재 조회 기간(${activeRangeStart} ~ ${activeRangeEnd})에서 제외되었습니다.`
        : `기사 날짜를 확인할 수 없어 현재 조회 기간(${activeRangeStart} ~ ${activeRangeEnd})에서 제외되었습니다.`;
    }
    if (!selectedArticleKeys.has(key)) {
      const representative = effectiveMailArticles.find((item) => isSimilarDonggukArticle(item, article));
      if (representative) {
        return `같은 주제의 대표 기사 '${representative.title || "제목 없음"}'로 묶여 메일 대표 목록에는 포함되지 않았습니다.`;
      }
      return `메일 대표 기사로 선택되지 않았습니다. ${articlePriorityReason(article)}`;
    }
    const representative = effectiveMailArticles.find((item) => isSimilarDonggukArticle(item, article) && String(item.id || item.title) !== String(article.id || article.title));
    if (representative) {
      return `같은 주제의 대표 기사 '${representative.title || "제목 없음"}'로 묶여 메일 대표 목록에는 포함되지 않았습니다.`;
    }
    return `이번 메일 대표 목록에는 포함되지 않았습니다. ${articlePriorityReason(article)}`;
  }

  async function restoreExcludedArticle(article, index) {
    if (!isArticleInActiveRange(article)) {
      showToast?.("현재 조회 기간 밖의 기사입니다. 기사 날짜를 포함하도록 조회 기간을 바꿔 주세요.", "error");
      return;
    }
    const key = articleKey(article, index);
    const nextKeys = new Set([...selectedArticleKeys, key]);
    const section = article.sectionLabel || article.section || donggukSections.foundation;
    const sectionMailCount = mailArticles.filter((item) => (item.sectionLabel || item.section) === section).length;
    const sectionLimit = Number(categoryArticleLimits[section] ?? 0);
    if (sectionMailCount >= sectionLimit) {
      showToast?.(`${section}은 최대 ${sectionLimit}건으로 설정되어 있습니다. 먼저 포함 기사를 제외하거나 최대 기사 수를 변경해 주세요.`, "error");
      return;
    }

    setSelectedArticleKeys(nextKeys);
    setPreviewArticles([]);
    setPreviewExcludedCount(0);
    setPreviewEditorUsed(false);
    setPreviewCached(false);
    await saveDraftSelection(nextKeys, null, candidateArticles, "today");
    showToast?.("제외된 기사를 메일 포함 목록에 다시 추가했습니다.", "success");
  }

  async function moveExcludedArticleToTrash(article, index) {
    if (!article?.id || String(article.id).startsWith("manual-")) {
      showToast?.("데이터베이스에 저장되지 않은 임시 기사는 휴지통으로 이동할 수 없습니다.", "error");
      return;
    }
    const key = articleKey(article, index);
    const nextKeys = new Set([...selectedArticleKeys].filter((item) => item !== key));
    const nextArticles = candidateArticles.filter((_, itemIndex) => itemIndex !== index);
    try {
      const result = await endpoints.moveDonggukTrash({
        keyword_id: selectedKeywordId,
        mail_date: mailDate,
        article: donggukArticlePayload(article),
      });
      setSelectedArticleKeys(nextKeys);
      setCandidateArticles(nextArticles);
      setTrashArticles((prev) => {
        const item = result.item ? { ...result.item, article: normalizeDonggukPreviewArticle(result.item.article || article) } : { article_id: article.id, article };
        return [item, ...prev.filter((row) => String(row.article_id || row.article?.id) !== String(article.id))];
      });
      setPreviewArticles([]);
      setPreviewExcludedCount(0);
      setPreviewEditorUsed(false);
      setPreviewCached(false);
      await saveDraftSelection(nextKeys, null, nextArticles);
      showToast?.("기사를 휴지통으로 이동했습니다.", "success");
    } catch (err) {
      showToast?.(err.message, "error");
    }
  }

  async function restoreTrashArticle(item) {
    const article = normalizeDonggukPreviewArticle(item.article || {});
    if (!article.id) return;
    try {
      await endpoints.restoreDonggukTrash({
        keyword_id: selectedKeywordId,
        mail_date: mailDate,
        article_id: article.id,
      });
      const nextArticles = candidateArticles.some((candidate) => String(candidate.id) === String(article.id))
        ? candidateArticles
        : [article, ...candidateArticles];
      setTrashArticles((prev) => prev.filter((row) => String(row.article_id || row.article?.id) !== String(article.id)));
      setCandidateArticles(nextArticles);
      await saveDraftSelection(selectedArticleKeys, null, nextArticles);
      showToast?.("휴지통에서 복구했습니다.", "success");
    } catch (err) {
      showToast?.(err.message, "error");
    }
  }

  async function permanentlyDeleteTrashArticle(item) {
    const article = item.article || {};
    if (!article.id) return;
    const confirmed = window.confirm("이 기사를 데이터베이스에서 완전히 삭제할까요? 이 작업은 되돌릴 수 없습니다.");
    if (!confirmed) return;
    try {
      await endpoints.deleteDonggukTrash({
        keyword_id: selectedKeywordId,
        mail_date: mailDate,
        article_id: article.id,
      });
      setTrashArticles((prev) => prev.filter((row) => String(row.article_id || row.article?.id) !== String(article.id)));
      showToast?.("기사를 데이터베이스에서 삭제했습니다.", "success");
    } catch (err) {
      showToast?.(err.message, "error");
    }
  }

  async function saveDraftSelection(
    nextKeys = selectedArticleKeys,
    previewData = null,
    articleSource = candidateArticles,
    feedbackSource = null
  ) {
    if (!selectedKeywordId || !mailDate || !articleSource.length) return;
    const keySet = new Set([...nextKeys].map(String));
    const selectedForDraft = articleSource.filter((article, index) => keySet.has(articleKey(article, index)));
    const removedForDraft = articleSource.filter((article, index) => !keySet.has(articleKey(article, index)));
    try {
      const removedKeys = articleSource
        .map((article, index) => articleKey(article, index))
        .filter((key) => !keySet.has(key));
      await endpoints.saveDonggukDraft({
        subject: mailSubject,
        keyword_id: selectedKeywordId,
        mail_date: mailDate,
        selected_article_keys: [...keySet],
        selected_articles: selectedForDraft.map(donggukArticlePayload),
        removed_article_keys: removedKeys,
        removed_articles: removedForDraft.map(donggukArticlePayload),
        preview_data: previewData,
        section_limits: donggukSectionLimitPayload(categoryArticleLimits),
        feedback_source: feedbackSource,
      });
      setDraftLoaded(true);
    } catch (err) {
      showToast?.(err.message, "error");
    }
  }

  async function saveEditedPreview(nextArticles = previewArticles, feedbackSource = "edit") {
    if (!selectedKeywordId || !mailDate) return;
    const previewData = {
      articles: nextArticles.map(donggukArticlePayload),
      excluded_articles: [],
      article_count: nextArticles.length,
      excluded_count: previewExcludedCount,
      editor_used: previewEditorUsed,
      cached: true,
      manually_edited: true,
      section_limits: donggukSectionLimitPayload(categoryArticleLimits),
    };
    await saveDraftSelection(selectedArticleKeys, previewData, candidateArticles, feedbackSource);
  }

  function updatePreviewArticle(index, patch) {
    setPreviewArticles((prev) => {
      const next = prev.map((article, idx) => {
        if (idx !== index) return article;
        const updated = { ...article, ...patch };
        if (patch.priority) {
          const band = donggukPriorityBands.find((item) => item.label === patch.priority) || donggukPriorityFromScore(updated.score);
          updated.priority = band.label;
          updated.priorityName = band.name;
          updated.priorityTone = band.tone;
          if (patch.score == null) updated.score = Math.max(Number(updated.score || 0), band.min);
        }
        if (patch.sectionLabel) updated.section = patch.sectionLabel;
        return normalizeDonggukPreviewArticle(updated);
      });
      return next;
    });
    setEditDirty(true);
  }

  function movePreviewArticle(index, direction) {
    setPreviewArticles((prev) => {
      const target = index + direction;
      if (target < 0 || target >= prev.length) return prev;
      const next = [...prev];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
    setEditDirty(true);
  }

  function removePreviewArticle(index) {
    setPreviewArticles((prev) => {
      const next = prev.filter((_, idx) => idx !== index);
      return next;
    });
    setEditDirty(true);
  }

  async function addArticlesFromUrls(urls) {
    if (!selectedKeywordId) {
      showToast?.("키워드를 먼저 선택해 주세요.", "error");
      return { added: 0, failed: 0 };
    }
    const existingUrls = new Set(
      candidateArticles.flatMap(realArticleLinks).map(canonicalArticleUrl)
    );
    const uniqueUrls = [...new Set(
      urls
        .map((url) => String(url || "").trim())
        .filter((url) => /^https?:\/\//i.test(url))
        .filter((url) => !existingUrls.has(canonicalArticleUrl(url)))
    )];
    const skipped = urls.length - uniqueUrls.length;
    if (!uniqueUrls.length) {
      showToast?.(skipped ? "이미 등록된 기사 URL입니다." : "유효한 기사 URL을 선택해 주세요.", "error");
      return { added: 0, failed: 0 };
    }

    const results = await Promise.allSettled(
      uniqueUrls.map((url) => endpoints.createArticleFromUrl({
        keyword_id: selectedKeywordId,
        url,
      }))
    );
    const addedArticles = results
      .filter((result) => result.status === "fulfilled" && result.value?.article)
      .map((result) => normalizeDonggukPreviewArticle(inferDonggukArticle(result.value.article)));
    const failed = results.length - addedArticles.length;

    if (addedArticles.length) {
      setCandidateArticles((prev) => dedupeExactArticles([...prev, ...addedArticles]));
      setPreviewArticles((prev) => dedupeExactArticles([...prev, ...addedArticles]));
      setSelectedArticleKeys((prev) => {
        const next = new Set(prev);
        addedArticles.forEach((article, index) => next.add(articleKey(article, candidateArticles.length + index)));
        return next;
      });
      setDuplicateFilterNeedsRefresh(true);
      setEditDirty(true);
    }
    if (addedArticles.length) {
      showToast?.(
        `${addedArticles.length}건을 편집 목록에 추가했습니다.${skipped ? ` 중복 URL ${skipped}건은 건너뛰었습니다.` : ""}${failed ? ` ${failed}건은 불러오지 못했습니다.` : ""}`,
        failed ? "info" : "success"
      );
    } else {
      showToast?.("선택한 기사를 불러오지 못했습니다. 원문 URL과 검색 서버 상태를 확인해 주세요.", "error");
    }
    return { added: addedArticles.length, failed };
  }

  async function addManualArticleFromLink() {
    const url = manualArticleUrl.trim();
    if (!/^https?:\/\//i.test(url)) {
      showToast?.("http 또는 https로 시작하는 기사 URL을 입력해 주세요.", "error");
      return;
    }
    setAddingManualArticle(true);
    try {
      const result = await addArticlesFromUrls([url]);
      if (result.added) setManualArticleUrl("");
    } finally {
      setAddingManualArticle(false);
    }
  }

  async function refreshDuplicateTopicFilter() {
    const completed = await loadDifyPreview(true, candidateArticles);
    if (completed) {
      setDuplicateFilterNeedsRefresh(false);
      showToast?.("AI가 추가 기사를 포함해 중복 주제를 다시 확인했습니다.", "success");
    }
  }

  async function downloadDonggukHwp() {
    const articles = effectiveMailArticles;
    if (!articles.length) {
      showToast?.("다운로드할 기사가 없습니다.", "error");
      return;
    }
    try {
      const response = await endpoints.donggukHwp({
        subject: mailSubject,
        mail_date: mailDate,
        articles: sanitizeDonggukMailArticles(articles, categoryArticleLimits).map(donggukArticlePayload),
        section_limits: donggukSectionLimitPayload(categoryArticleLimits),
      });
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `오늘의 주요 뉴스(${mailDate.replaceAll("-", "").slice(2)}).hwpx`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      showToast?.("한글 파일 다운로드를 시작했습니다.", "success");
    } catch (err) {
      showToast?.(err.message, "error");
    }
  }

  async function loadDifyPreview(forceRebuild = false, articlePool = null) {
    const sourceArticles = articlePool || mailArticles;
    const candidates = sourceArticles.filter((article) => !article.isTrashed && realArticleLinks(article).length > 0);
    if (!candidates.length) {
      setPreviewArticles([]);
      setPreviewExcludedArticles([]);
      setAiProcessedArticleCount(0);
      setPreviewExcludedCount(0);
      setPreviewEditorUsed(false);
      setPreviewCached(false);
      return false;
    }
    setLoadingPreview(true);
    try {
      const selectedKeySet = new Set([...selectedArticleKeys].map(String));
      const removedRows = candidateArticles
        .map((article, index) => ({ article, key: articleKey(article, index) }))
        .filter(({ key }) => !selectedKeySet.has(key));
      const result = await endpoints.donggukPreview({
        subject: mailSubject,
        keyword_id: selectedKeywordId,
        mail_date: mailDate,
        exclude_similar_sent: true,
        selected_article_keys: [...selectedArticleKeys],
        removed_article_keys: removedRows.map(({ key }) => key),
        removed_articles: removedRows.map(({ article }) => donggukArticlePayload(article)),
        priority_criteria: normalizeDonggukCriteria(priorityCriteria),
        section_limits: donggukSectionLimitPayload(categoryArticleLimits),
        force_rebuild: forceRebuild,
        articles: candidates.map(donggukArticlePayload),
      });
      const nextArticles = sanitizeDonggukMailArticles(
        (result.articles || []).map(normalizeDonggukPreviewArticle),
        categoryArticleLimits
      );
      const nextExcludedArticles = (result.excluded_articles || []).map(normalizeDonggukPreviewArticle);
      const nextSelectedKeys = candidateKeysForAiArticles(nextArticles, candidateArticles);
      setPreviewArticles(nextArticles);
      setPreviewExcludedArticles(nextExcludedArticles);
      setSelectedArticleKeys(nextSelectedKeys);
      setDuplicateExcludedKeys(aiDuplicateExcludedKeys(nextExcludedArticles, candidateArticles));
      setAiProcessedArticleCount(candidates.length);
      setPreviewExcludedCount(Number(result.excluded_count || 0));
      setPreviewEditorUsed(Boolean(result.editor_used));
      setPreviewCached(Boolean(result.cached));
      return true;
    } catch (err) {
      showToast?.(err.message, "error");
      return false;
    } finally {
      setLoadingPreview(false);
    }
  }

  useEffect(() => {
    if (loadingCandidates || loadingPreview) return;
    if (!draftLoaded) return;
    if (editDirty) return;
    if (duplicateFilterNeedsRefresh) return;
    const eligibleCount = candidateArticles.filter((article) => !article.isTrashed && realArticleLinks(article).length > 0).length;
    if (!eligibleCount) return;
    if (previewArticles.length && aiProcessedArticleCount >= eligibleCount) return;
    const requestKey = [
      selectedKeywordId,
      mailDate,
      candidateArticles.length,
      aiProcessedArticleCount,
      selectedArticleKeySignature,
      normalizeDonggukCriteria(priorityCriteria),
    ].join("::");
    if (autoPreviewRequestKey.current === requestKey) return;
    autoPreviewRequestKey.current = requestKey;
    const timer = setTimeout(() => {
      loadDifyPreview(aiProcessedArticleCount > 0, candidateArticles);
    }, 500);
    return () => clearTimeout(timer);
  }, [
    mailDate,
    selectedKeywordId,
    selectedArticleKeySignature,
    priorityCriteria,
    draftLoaded,
    candidateArticles.length,
    aiProcessedArticleCount,
    previewArticles.length,
    duplicateFilterNeedsRefresh,
    loadingCandidates,
    loadingPreview,
    editDirty,
  ]);

  async function saveAutoSendSettings(nextEnabled = autoSendEnabled) {
    if (!selectedKeywordId || !onUpdateKeyword) {
      showToast?.("키워드를 먼저 선택해 주세요.", "error");
      return;
    }
    const recipients = emails.replaceAll(",", "\n").split("\n").map((item) => item.trim()).filter(Boolean);
    if (nextEnabled && !recipients.length) {
      showToast?.("수신인을 먼저 지정해 주세요.", "error");
      return;
    }
    setAutoSendEnabled(nextEnabled);
    setSavingAuto(true);
    try {
      await onUpdateKeyword(selectedKeywordId, {
        email_auto_send: nextEnabled,
        email_recipients: nextEnabled ? recipients : [],
        email_send_time: autoSendTime || "08:30",
        email_condition_type: "daily_summary",
      });
      showToast?.(`홍보처 자동 발송을 ${nextEnabled ? "켰습니다." : "껐습니다."}`, "success");
    } finally {
      setSavingAuto(false);
    }
  }

  async function savePriorityCriteria() {
    if (!selectedKeywordId || !onUpdateKeyword) {
      showToast?.("키워드를 먼저 선택해 주세요.", "error");
      return;
    }
    setSavingPriorityCriteria(true);
    try {
      const nextCriteria = normalizeDonggukCriteria(priorityCriteria);
      const previousCriteria = criteriaBaselineRef.current;
      await onUpdateKeyword(selectedKeywordId, {
        importance_criteria: nextCriteria,
      });
      if (previousCriteria !== nextCriteria) {
        try {
          await endpoints.recordPriorityAction({
            keyword_id: selectedKeywordId,
            action_type: "criteria_edit",
            source_screen: "settings",
            mail_date: mailDate,
            before: { priority_criteria: previousCriteria },
            after: { priority_criteria: nextCriteria },
            reason: "관리자가 AI 기사 선정 기준을 직접 수정했습니다.",
          });
        } catch (err) {
          console.warn("priority criteria action log failed", err);
        }
      }
      criteriaBaselineRef.current = nextCriteria;
      setPreviewArticles([]);
      setPreviewExcludedCount(0);
      setPreviewEditorUsed(false);
      setPreviewCached(false);
      showToast?.("우선순위 선정 기준을 저장했습니다. AI 미리보기를 갱신하면 새 기준이 적용됩니다.", "success");
    } finally {
      setSavingPriorityCriteria(false);
    }
  }

  async function sendDonggukEmail(isTest = false) {
    const sourceEmails = isTest ? testEmails : emails;
    const toEmails = sourceEmails.replaceAll(",", "\n").split("\n").map((item) => item.trim()).filter(Boolean);
    if (!toEmails.length) {
      showToast?.(isTest ? "테스트 수신 이메일을 입력해 주세요." : "수신 이메일을 입력해 주세요.", "error");
      return;
    }
    setSending(true);
    try {
      if (!selectedKeywordId) {
        showToast?.("키워드를 먼저 선택해 주세요.", "error");
        return;
      }
      const loadedCandidates = candidateArticles.length ? selectedCandidates : await loadCandidateArticles();
      const editedCandidates = sanitizeDonggukMailArticles(
        editedMailArticles.length ? editedMailArticles : loadedCandidates,
        categoryArticleLimits
      );
      const candidates = editedCandidates.filter((article) => realArticleLinks(article).length > 0);
      if (!candidates.length) {
        showToast?.(`${mailDate} 기준 수집된 원문 URL 포함 기사 후보가 없습니다.`, "error");
        return;
      }
      const result = await endpoints.donggukEmail({
        to_emails: toEmails,
        subject: mailSubject,
        keyword_id: selectedKeywordId,
        mail_date: mailDate,
        exclude_similar_sent: true,
        use_current_articles: editedMailArticles.length > 0,
        articles: candidates.map(donggukArticlePayload),
        priority_criteria: normalizeDonggukCriteria(priorityCriteria),
        section_limits: donggukSectionLimitPayload(categoryArticleLimits),
        is_test: isTest,
      });
      if (Number(result?.article_count || 0) === 0) {
        showToast?.(result?.message || "오늘 발송할 신규 기사가 없습니다.", "error");
      } else {
        showToast?.(
          isTest
            ? `테스트 메일을 발송했습니다. AI 편집 후 제외 기사 ${result?.excluded_count || 0}건은 발송 기록에 반영되지 않습니다.`
            : `홍보처 맞춤 메일을 발송했습니다. AI 편집 후 제외 기사 ${result?.excluded_count || 0}건이 기록됐습니다.`,
          "success"
        );
      }
      await loadDonggukHistory(viewMode !== "history", true);
    } catch (err) {
      showToast?.(err.message, "error");
    } finally {
      setSending(false);
    }
  }

  function cloneArticles(articles) {
    return JSON.parse(JSON.stringify(articles || []));
  }

  function navigateDonggukView(nextView) {
    const resolvedView = nextView;
    if (viewMode === "edit" && resolvedView !== "edit" && editDirty) {
      const discard = window.confirm("저장하지 않은 기사 편집 내용이 있습니다. 변경사항을 버리고 이동할까요?");
      if (!discard) return;
      setPreviewArticles(cloneArticles(editBaselineArticles.current));
      setEditDirty(false);
    }
    if (resolvedView === "edit" && viewMode !== "edit") {
      editBaselineArticles.current = cloneArticles(previewArticles);
      setEditDirty(false);
    }
    setViewMode(resolvedView);
  }

  useEffect(() => {
    function warnUnsaved(event) {
      if (!editDirty) return;
      event.preventDefault();
      event.returnValue = "";
    }
    window.addEventListener("beforeunload", warnUnsaved);
    return () => window.removeEventListener("beforeunload", warnUnsaved);
  }, [editDirty]);

  function renderManualArticleImportPanel() {
    return (
      <details className="workspace-accordion manual-import-accordion">
        <summary>
          <div>
            <ExternalLink size={18} />
            <span className="workspace-summary-copy">
              <strong>링크로 기사 가져오기</strong>
              <small>수집되지 않은 기사 URL을 분석해 같은 형식으로 추가합니다.</small>
            </span>
          </div>
          <ChevronDown size={16} />
        </summary>
        <div className="workspace-accordion-body">
          <div className="manual-article-add">
            <input
              aria-label="추가할 기사 URL"
              value={manualArticleUrl}
              onChange={(event) => setManualArticleUrl(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  addManualArticleFromLink();
                }
              }}
              placeholder="https://news.example.com/article"
            />
            <button className="secondary" disabled={addingManualArticle || !manualArticleUrl.trim()} onClick={addManualArticleFromLink} type="button">
              {addingManualArticle ? <Loader2 className="spin" size={15} /> : <Plus size={15} />}
              기사 가져오기
            </button>
          </div>
        </div>
      </details>
    );
  }

  function renderUnifiedTestSendPanel() {
    const previewRows = effectiveMailArticles;
    return (
      <details className="workspace-accordion unified-test-send">
        <summary>
          <div>
            <Send size={18} />
            <span className="workspace-summary-copy">
              <strong>테스트 전송</strong>
              <small>현재 선택된 기사 {previewRows.length}건을 지정한 주소로 확인용 전송합니다.</small>
            </span>
          </div>
          <span className="workspace-summary-meta">수신인 {testRecipientList.length}명 <ChevronDown size={16} /></span>
        </summary>
        <div className="workspace-accordion-body">
          <div className="test-send-panel compact-test-send">
            <div>
              <strong>{mailSubject}</strong>
              <span>지정한 주소로만 현재 문안을 보내며 정식 발송 기록에는 반영하지 않습니다.</span>
              <textarea
                className="test-send-input"
                value={testEmails}
                onChange={(event) => setTestEmails(event.target.value)}
                placeholder="테스트로 받을 이메일 주소"
              />
              {recentRecipients.length > 0 && (
                <div className="test-recipient-chips" aria-label="최근 수신인">
                  {recentRecipients.slice(0, 4).map((email) => (
                    <button
                      className="chip-button"
                      key={`workspace-test-${email}`}
                      onClick={() => {
                        const current = testEmails.replaceAll(",", "\n").split("\n").map((item) => item.trim()).filter(Boolean);
                        setTestEmails([...new Set([...current, email])].join("\n"));
                      }}
                      type="button"
                    >
                      {email}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div className="test-send-meta">
              <span>수신인 {testRecipientList.length}명</span>
              <button className="primary compact" disabled={sending || !testRecipientList.length || !previewRows.length} onClick={() => sendDonggukEmail(true)} type="button">
                {sending ? <Loader2 className="spin" size={15} /> : <Send size={15} />}
                테스트 전송
              </button>
            </div>
          </div>
          <button
            aria-expanded={workspaceMailPreviewOpen}
            className="secondary workspace-mail-preview-button"
            onClick={() => setWorkspaceMailPreviewOpen((open) => !open)}
            type="button"
          >
            {workspaceMailPreviewOpen ? <ChevronUp size={16} /> : <Eye size={16} />}
            {workspaceMailPreviewOpen ? "미리보기 접기" : "메일 미리보기"}
          </button>
          {workspaceMailPreviewOpen && (
            <section className="workspace-inline-mail-preview" aria-label="메일 미리보기">
              <div className="preview-workspace-heading">
                <div>
                  <span className="preview-section-label">선택 기사 메일 미리보기</span>
                  <strong>{mailSubject}</strong>
                  <span>현재 메일 포함 기사 {previewRows.length}건을 실제 발송 순서로 표시합니다.</span>
                </div>
                <button
                  className="secondary compact"
                  disabled={loadingPreview || !mailArticles.length}
                  onClick={() => loadDifyPreview(true)}
                  type="button"
                >
                  {loadingPreview ? <Loader2 className="spin" size={15} /> : <Sparkles size={15} />}
                  AI 미리보기 갱신
                </button>
              </div>
              {loadingPreview && (
                <div className="loading-line">
                  <Loader2 className="spin" size={17} /> AI가 대표 기사와 메일 문안을 정리하는 중
                </div>
              )}
              <div className="unified-preview-content">
                {Object.values(donggukSections).map((section) => {
                  const rows = previewRows.filter((article) => article.sectionLabel === section);
                  if (!rows.length) return null;
                  return (
                    <div className="mail-section" key={`workspace-preview-${section}`}>
                      <h3>{section}</h3>
                      {rows.map((article, index) => (
                        <article className="mail-editor-card" key={`workspace-preview-${article.id || article.title}-${index}`}>
                          <div className="mail-editor-main">
                            <div className="mail-editor-title-row">
                              <strong>{index + 1}. {article.title} [{article.source}]</strong>
                            </div>
                            <p>{article.summary || "요약문이 아직 없습니다."}</p>
                            {realArticleLinks(article).length > 0 && (
                              <div className="mail-preview-links">
                                {realArticleLinks(article).map((link) => (
                                  <a href={link} target="_blank" rel="noreferrer" key={link}>{link}</a>
                                ))}
                              </div>
                            )}
                          </div>
                        </article>
                      ))}
                    </div>
                  );
                })}
                {!loadingPreview && !previewRows.length && (
                  <EmptyState
                    title="메일에 포함된 기사가 없습니다"
                    body="아래 기사 목록에서 메일에 포함할 기사를 선택하면 이곳에 미리보기가 표시됩니다."
                  />
                )}
              </div>
              <button className="secondary workspace-preview-collapse-button" onClick={() => setWorkspaceMailPreviewOpen(false)} type="button">
                <ChevronUp size={16} /> 미리보기 접기
              </button>
            </section>
          )}
        </div>
      </details>
    );
  }

  const isMailEditView = viewMode === "edit";

  return (
    <section className="dongguk-console">
      {viewMode !== "trash" && (
        <>
          <div className="dongguk-brief">
            <div className="brief-head">
              <div>
                <span className="eyebrow">Dongguk PR Desk</span>
                <h2>
                  {viewMode === "mail"
                    ? "메일 미리보기"
                    : viewMode === "edit"
                      ? "기사 편집"
                      : viewMode === "priority"
                        ? "오늘 수집된 기사"
                      : viewMode === "collection"
                        ? "수집 상태"
                      : viewMode === "stats"
                        ? "통계"
                        : viewMode === "calendar"
                          ? "휴일 캘린더"
                        : viewMode === "history"
                          ? "발송 기록"
                          : "설정"}
                </h2>
              </div>
              <div className="daily-date">
                <span>기준일 선택</span>
                <input type="date" value={mailDate} onChange={(event) => setMailDate(event.target.value)} />
                <strong>{mailSubject}</strong>
              </div>
            </div>
          </div>

          <div className="toolbar full dongguk-toolbar">
            <div className="brief-tabs" role="tablist" aria-label="홍보처 맞춤 화면">
              <button className={viewMode === "home" ? "active" : ""} onClick={() => navigateDonggukView("home")} type="button">
                <Settings size={18} /> 설정
              </button>
              <button className={["priority", "edit", "mail"].includes(viewMode) ? "active" : ""} onClick={() => navigateDonggukView("priority")} type="button">
                <FileText size={18} /> 오늘 수집된 기사
              </button>
              <button className={viewMode === "collection" ? "active" : ""} onClick={() => navigateDonggukView("collection")} type="button">
                <RefreshCw size={18} /> 수집 상태
              </button>
              <button className={viewMode === "calendar" ? "active" : ""} onClick={() => navigateDonggukView("calendar")} type="button">
                <Calendar size={18} /> 캘린더
              </button>
              <button className={viewMode === "stats" ? "active" : ""} onClick={() => navigateDonggukView("stats")} type="button">
                <BarChart3 size={18} /> 통계
              </button>
              <button className={viewMode === "history" ? "active" : ""} onClick={() => navigateDonggukView("history")} type="button">
                <Send size={18} /> 발송 기록
              </button>
            </div>
          </div>

        </>
      )}

      {viewMode === "home" && (
        <div className="dongguk-home-grid">
          <section className="dongguk-home-card">
            <div className="panel-heading clean">
              <FileText className="panel-heading-icon" size={24} />
              <strong>설정</strong>
              <span>{selectedKeywordName || "동국대학교"}</span>
            </div>
            <div className="home-article-list">
              <div className="home-news-section">
                <div className="home-news-section-head">
                  <strong>메일 포함 기사</strong>
                  <span>{effectiveMailArticles.length}건</span>
                </div>
                {effectiveMailArticles.length ? (
                  effectiveMailArticles.map((article, index) => {
                    const thumbnailUrl = getArticleThumbnail(article);
                    return (
                      <article className="home-article-card included" key={`${article.id || article.title}-selected-${index}`}>
                        <span className="lead-rank">{index + 1}</span>
                        {thumbnailUrl ? (
                          <img
                            className="home-article-thumb"
                            src={thumbnailUrl}
                            alt=""
                            loading="lazy"
                            onError={(event) => {
                              event.currentTarget.style.display = "none";
                            }}
                          />
                        ) : (
                          <div className="lead-thumb compact">
                            <div className="lead-thumb-mark">D</div>
                          </div>
                        )}
                        <div>
                          <div className="meta">
                            <span className="pill include">메일 포함</span>
                            <span className={`priority-pill ${article.priorityTone || "p3"}`}>{priorityDisplayName(article)}</span>
                            <span>{article.category || "기사 후보"}</span>
                            {article.isSyndicated && <span className="pill warning">중복</span>}
                          </div>
                          <h3>{article.title || "제목 없음"}</h3>
                          <p>{article.summary || "요약문이 아직 없습니다."}</p>
                          <div className="priority-reason">
                            <span>{articlePriorityReason(article)}</span>
                          </div>
                        </div>
                        <span className="lead-time">{formatDate(article.published_at) || autoSendTime || "08:30"}</span>
                      </article>
                    );
                  })
                ) : (
                  <EmptyState title="선정된 메일 포함 기사가 없습니다" body="기준일을 바꾸거나 오늘 수집된 기사 화면에서 메일 포함 기사를 선택해 주세요." />
                )}
              </div>

              <div className="home-news-section">
                <div className="home-news-section-head">
                  <strong>제외된 뉴스</strong>
                  <span>{excludedHomeRows.length}건</span>
                </div>
                {excludedHomeRows.length ? (
                  excludedHomeRows.map(({ article, index, key }) => {
                  const thumbnailUrl = getArticleThumbnail(article);
                  return (
                    <article className="home-article-card excluded" key={`${article.id || article.title}-${index}`}>
                      <span className="lead-rank">{index + 1}</span>
                      {thumbnailUrl ? (
                        <img
                          className="home-article-thumb"
                          src={thumbnailUrl}
                          alt=""
                          loading="lazy"
                          onError={(event) => {
                            event.currentTarget.style.display = "none";
                          }}
                        />
                      ) : (
                        <div className="lead-thumb compact">
                          <div className="lead-thumb-mark">D</div>
                        </div>
                      )}
                      <div>
                        <div className="meta">
                          <span className="pill muted">메일 제외</span>
                          <span className={`priority-pill ${article.priorityTone || "p3"}`}>{priorityDisplayName(article)}</span>
                          <span>{article.category || "기사 후보"}</span>
                          {article.isSyndicated && <span className="pill warning">중복</span>}
                        </div>
                        <h3>{article.title || "제목 없음"}</h3>
                        <p>{article.summary || "요약문이 아직 없습니다."}</p>
                        <div className="excluded-reason">
                          <span>{excludedArticleReason(article, key)}</span>
                          <button className="secondary compact" onClick={() => restoreExcludedArticle(article, index)} type="button">
                            <Plus size={14} /> 다시 추가
                          </button>
                          <button className="secondary compact danger-text" onClick={() => moveExcludedArticleToTrash(article, index)} type="button">
                            <Trash2 size={14} /> 휴지통 이동
                          </button>
                        </div>
                      </div>
                      <span className="lead-time">{formatDate(article.published_at) || autoSendTime || "08:30"}</span>
                    </article>
                  );
                  })
                ) : (
                  <EmptyState title="제외된 뉴스가 없습니다" body="현재 수집 기사 전체가 메일 포함 목록에 들어가 있습니다." />
                )}
              </div>

            </div>
          </section>

          <section className="dongguk-send-panel settings-card">
            <div className="panel-heading clean">
              <Settings className="panel-heading-icon" size={24} />
              <strong>설정</strong>
              <span>{mailSubject}</span>
            </div>
            <label className="settings-row">
              <Calendar size={18} />
              <span>기준일</span>
              <input type="date" value={mailDate} onChange={(event) => setMailDate(event.target.value)} />
            </label>
            <details className="settings-details">
              <summary>
                <span><Hash size={18} /> 최대 기사 수 지정하기</span>
                <b>총 {maxMailArticleTotal}건</b>
              </summary>
              <div className="category-limit-list">
                {Object.values(donggukSections).map((section) => (
                  <label className="category-limit-row" key={section}>
                    <span>{section}</span>
                    <select value={categoryArticleLimits[section] ?? 0} onChange={(event) => updateCategoryLimit(section, event.target.value)}>
                      {[0, 1, 2, 3, 4, 5, 6, 8, 10].map((value) => <option key={value} value={value}>{value}건</option>)}
                    </select>
                  </label>
                ))}
              </div>
            </details>
            <label className="settings-row">
              <Clock size={18} />
              <span>발송 시간</span>
              <input type="time" value={autoSendTime} onChange={(event) => setAutoSendTime(event.target.value)} />
            </label>
            <details className="settings-details">
              <summary>
                <span><UserRound size={18} /> 수신인 지정</span>
                <b>{recipientList.length}명</b>
              </summary>
              {recipientList.length > 0 && (
                <div className="recipient-edit-list">
                  {recipientList.map((email, index) => (
                    <button
                      className="recipient-edit-chip"
                      key={`${email}-${index}`}
                      onContextMenu={(event) => openRecipientContext(event, index)}
                      type="button"
                    >
                      {email}
                    </button>
                  ))}
                </div>
              )}
              <textarea
                value={emails}
                onChange={(event) => setEmails(event.target.value)}
                placeholder="pr-team@dongguk.edu&#10;newsroom@example.com"
              />
              {recentRecipients.length > 0 && (
                <div className="recipient-chip-list compact-list inside-details">
                  {recentRecipients.slice(0, 4).map((email) => (
                    <button className="secondary compact" key={email} onClick={() => addRecipient(email)} type="button">
                      {email}
                    </button>
                  ))}
                </div>
              )}
            </details>
            <details className="settings-details priority-rule-details">
              <summary>
                <span><BarChart3 size={18} /> AI 기사 선정 기준</span>
                <b>{priorityRuleItems.length + representativeRuleItems.length + exclusionRuleItems.length}개</b>
              </summary>
              <p className="criteria-help">아래 문장을 그대로 AI에 전달합니다. 순서를 바꾸거나 문장을 직접 수정할 수 있습니다.</p>
              <details className="criteria-subdetails">
                <summary>
                  <span><strong>우선순위 기준</strong><small>위에 있는 문장부터 우선 적용</small></span>
                  <b>{priorityRuleItems.length}개</b>
                </summary>
                <div className="priority-rule-list">
                {priorityRuleItems.map((rule, index) => (
                  <div
                    className="priority-rule-item"
                    draggable
                    key={`${rule}-${index}`}
                    onDragStart={() => setDraggedPriorityIndex(index)}
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={() => {
                      movePriorityRule(draggedPriorityIndex, index);
                      setDraggedPriorityIndex(null);
                    }}
                    onContextMenu={(event) => openPriorityContext(event, index)}
                  >
                    <span className="drag-handle">⋮⋮</span>
                    <b>{index + 1}</b>
                    <textarea
                      data-priority-rule-index={index}
                      rows={2}
                      value={rule}
                      onChange={(event) => updatePriorityRule(index, event.target.value)}
                      onContextMenu={(event) => openPriorityContext(event, index)}
                    />
                    <button className="icon-button danger-text" title="기준 삭제" onClick={() => deletePriorityRule(index)} type="button">
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))}
                </div>
                <div className="priority-rule-add">
                <input
                  value={newPriorityRule}
                  onChange={(event) => setNewPriorityRule(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      addPriorityRule();
                    }
                  }}
                  placeholder="예: 학생 성과가 구체적으로 드러난 기사를 우선 선정합니다."
                />
                <button className="secondary compact" onClick={addPriorityRule} type="button">
                  <Plus size={14} /> 추가
                </button>
                </div>
              </details>
              <details className="criteria-subdetails">
                <summary>
                  <span><strong>중복 주제 대표 기사 선정 기준</strong><small>같은 주제에서 1건을 고르는 방법</small></span>
                  <b>{representativeRuleItems.length}개</b>
                </summary>
                <div className="criteria-sentence-list">
                {representativeRuleItems.map((rule, index) => (
                  <div className="criteria-sentence-item" key={`representative-${index}`}>
                    <textarea rows={2} value={rule} onChange={(event) => updateRepresentativeRule(index, event.target.value)} />
                    <button className="icon-button danger-text" title="기준 삭제" onClick={() => deleteRepresentativeRule(index)} type="button">
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))}
                </div>
                <div className="priority-rule-add">
                <input
                  value={newRepresentativeRule}
                  onChange={(event) => setNewRepresentativeRule(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      addRepresentativeRule();
                    }
                  }}
                  placeholder="예: 제목에 핵심 인물과 성과가 명확한 기사를 대표로 선정합니다."
                />
                <button className="secondary compact" onClick={addRepresentativeRule} type="button"><Plus size={14} /> 추가</button>
                </div>
              </details>
              <details className="criteria-subdetails exclusion-subdetails">
                <summary>
                  <span><strong>제외 기준</strong><small>해당하는 기사는 메일 후보에서 제외</small></span>
                  <b>{exclusionRuleItems.length}개</b>
                </summary>
                <div className="criteria-sentence-list">
                {exclusionRuleItems.map((rule, index) => (
                  <div className="criteria-sentence-item exclusion-item" key={`exclusion-${index}`}>
                    <textarea rows={2} value={rule} onChange={(event) => updateExclusionRule(index, event.target.value)} />
                    <button className="icon-button danger-text" title="제외 기준 삭제" onClick={() => deleteExclusionRule(index)} type="button">
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))}
                </div>
                <div className="criteria-example-list">
                <span>예시로 추가</span>
                <button className="secondary compact" onClick={() => addExclusionRule("동국대의 인사발령 관련 기사는 모두 제외합니다.")} type="button">인사발령 제외</button>
                <button className="secondary compact" onClick={() => addExclusionRule("동국대학교 경주캠퍼스 관련 주제는 모두 제외합니다.")} type="button">경주캠퍼스 제외</button>
                </div>
                <div className="priority-rule-add">
                <input
                  value={newExclusionRule}
                  onChange={(event) => setNewExclusionRule(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      addExclusionRule();
                    }
                  }}
                  placeholder="예: 특정 인물의 단순 인사발령 기사는 모두 제외합니다."
                />
                <button className="secondary compact" onClick={() => addExclusionRule()} type="button"><Plus size={14} /> 추가</button>
                </div>
              </details>
              <button className="secondary save-criteria-button" disabled={savingPriorityCriteria} onClick={savePriorityCriteria} type="button">
                {savingPriorityCriteria ? <Loader2 className="spin" size={16} /> : <CheckCircle2 size={16} />}
                AI 기사 선정 기준 저장
              </button>
            </details>
            <details className="auto-send-box slim">
              <summary>
                <span>자동 발송 설정</span>
                <button
                  aria-checked={autoSendEnabled}
                  className={`inline-switch ${autoSendEnabled ? "on" : ""}`}
                  disabled={savingAuto}
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    saveAutoSendSettings(!autoSendEnabled);
                  }}
                  role="switch"
                  type="button"
                >
                  {savingAuto ? "저장 중" : autoSendEnabled ? "켜짐" : "꺼짐"}
                </button>
              </summary>
              <div className="auto-send-description">
                <p>켜짐 상태에서는 기준일과 발송 시간 설정에 맞춰 수신인 지정 목록의 메일 주소로 홍보처 맞춤 뉴스가 자동 발송됩니다.</p>
                <p>수신인 변경은 위의 <b>수신인 지정</b>에서 관리하고, 테스트 전송은 <b>메일 미리보기</b> 탭에서 별도로 실행합니다.</p>
              </div>
            </details>
          </section>
        </div>
      )}

      {viewMode === "collection" && (
        <CollectionStatusPanel
          keywordId={selectedKeywordId}
          keywordName={selectedKeywordName}
          showToast={showToast}
        />
      )}

      {viewMode === "calendar" && (
        <div className="holiday-calendar-layout">
          <section className="holiday-calendar-card">
            <div className="holiday-calendar-header">
              <div>
                <strong>휴일 캘린더</strong>
                <span>휴일에도 기사 수집은 계속되며, 다음 업무일 메일에 누적 기사가 포함됩니다.</span>
              </div>
              <div className="calendar-month-controls">
                <button className="icon-button" aria-label="이전 달" onClick={() => moveCalendarMonth(-1)} type="button">
                  <ChevronLeft size={18} />
                </button>
                <b>{calendarMonthLabel}</b>
                <button className="icon-button" aria-label="다음 달" onClick={() => moveCalendarMonth(1)} type="button">
                  <ChevronRight size={18} />
                </button>
                <button className="secondary compact" onClick={() => setCalendarMonth(localDateKey().slice(0, 7))} type="button">
                  오늘
                </button>
              </div>
            </div>

            <div className="calendar-legend" aria-label="캘린더 표시 안내">
              <span><i className="public" /> 공휴일</span>
              <span><i className="school" /> 학교 휴일</span>
              <span><i className="personal" /> 개인 휴가</span>
              <span><i className="weekend" /> 주말</span>
            </div>

            <div className="holiday-calendar-grid">
              {["일", "월", "화", "수", "목", "금", "토"].map((weekday) => (
                <strong className="calendar-weekday" key={weekday}>{weekday}</strong>
              ))}
              {loadingCalendar ? (
                <div className="calendar-loading"><Loader2 className="spin" size={22} /> 캘린더를 불러오는 중입니다.</div>
              ) : calendarCells.map((day) => {
                const hasPublicHoliday = Boolean(day.public_holiday_name);
                const hasSchoolHoliday = Boolean(day.school_holiday_names?.length);
                const hasPersonalHoliday = Boolean(day.personal_holiday_names?.length);
                const selected = schoolHolidayForm.start_date <= day.date && day.date <= schoolHolidayForm.end_date;
                return (
                  <button
                    aria-label={`${day.date}${day.public_holiday_name ? ` ${day.public_holiday_name}` : ""}${day.school_holiday_names?.length ? ` 학교 휴일 ${day.school_holiday_names.join(", ")}` : ""}${day.personal_holiday_names?.length ? ` 개인 휴가 ${day.personal_holiday_names.join(", ")}` : ""}`}
                    className={[
                      "holiday-calendar-day",
                      day.isCurrentMonth ? "" : "outside-month",
                      day.isToday ? "today" : "",
                      !day.is_business_day ? "holiday" : "",
                      selected ? "selected" : "",
                    ].filter(Boolean).join(" ")}
                    key={day.date}
                    onClick={() => selectCalendarDate(day.date)}
                    type="button"
                  >
                    <span className="calendar-day-number">{Number(day.date.slice(-2))}</span>
                    <div className="calendar-day-events">
                      {hasPublicHoliday && <em className="public">{day.public_holiday_name}</em>}
                      {day.school_holiday_names?.map((name) => <em className="school" key={`school-${day.date}-${name}`}>{name}</em>)}
                      {day.personal_holiday_names?.map((name) => <em className="personal" key={`personal-${day.date}-${name}`}>{name}</em>)}
                      {day.is_weekend && !hasPublicHoliday && !hasSchoolHoliday && !hasPersonalHoliday && <small>주말</small>}
                    </div>
                  </button>
                );
              })}
            </div>
          </section>

          <aside className="holiday-calendar-side">
            <section className="holiday-register-card">
              <div className="panel-heading clean">
                <Calendar className="panel-heading-icon" size={22} />
                <strong>휴일 등록</strong>
                <span>날짜를 누르면 자동 입력됩니다.</span>
              </div>
              <label className="holiday-form-field">
                <span>구분</span>
                <select
                  value={schoolHolidayForm.holiday_type}
                  onChange={(event) => setSchoolHolidayForm((prev) => ({ ...prev, holiday_type: event.target.value }))}
                >
                  <option value="personal">개인 휴가</option>
                  <option value="school">학교 휴일</option>
                </select>
              </label>
              <label className="holiday-form-field">
                <span>이름</span>
                <input
                  value={schoolHolidayForm.name}
                  onChange={(event) => setSchoolHolidayForm((prev) => ({ ...prev, name: event.target.value }))}
                  placeholder={schoolHolidayForm.holiday_type === "personal" ? "예: 여름 휴가" : "예: 개교기념일"}
                />
              </label>
              <div className="holiday-date-fields">
                <label className="holiday-form-field">
                  <span>시작일</span>
                  <input
                    type="date"
                    value={schoolHolidayForm.start_date}
                    onChange={(event) => setSchoolHolidayForm((prev) => ({ ...prev, start_date: event.target.value }))}
                  />
                </label>
                <label className="holiday-form-field">
                  <span>마지막 휴일</span>
                  <input
                    type="date"
                    min={schoolHolidayForm.start_date}
                    value={schoolHolidayForm.end_date}
                    onChange={(event) => setSchoolHolidayForm((prev) => ({ ...prev, end_date: event.target.value }))}
                  />
                </label>
              </div>
              <div className="holiday-mail-notice">
                <Clock size={17} />
                <span>
                  등록 기간에는 자동 메일을 보내지 않습니다. 수집된 기사는 휴일이 끝난 다음 업무일
                  <strong> {autoSendTime}</strong> 메일에 함께 포함됩니다.
                </span>
              </div>
              <button className="primary holiday-register-button" disabled={savingSchoolHoliday} onClick={createSchoolHoliday} type="button">
                {savingSchoolHoliday ? <Loader2 className="spin" size={16} /> : <Plus size={16} />}
                휴일 등록
              </button>
            </section>

            <section className="registered-holiday-card">
              <div className="panel-heading">
                <div>
                  <strong>등록된 휴일</strong>
                  <span>{calendarMonth.slice(0, 4)}년 기준</span>
                </div>
                <b>{schoolHolidays.length}개</b>
              </div>
              <div className="school-holiday-list">
                {schoolHolidays.map((item) => (
                  <div className="school-holiday-item" key={item.id}>
                    <span>
                      <strong>
                        <i className={`holiday-type-dot ${item.holiday_type || "school"}`} />
                        {item.name}
                      </strong>
                      <small>{item.start_date} ~ {item.end_date} · {item.holiday_type === "personal" ? "개인 휴가" : "학교 휴일"}</small>
                    </span>
                    <button className="icon-button" title="수정" onClick={() => editSchoolHoliday(item)} type="button"><Pencil size={14} /></button>
                    <button className="icon-button danger-text" title="삭제" onClick={() => removeSchoolHoliday(item.id)} type="button"><Trash2 size={14} /></button>
                  </div>
                ))}
                {!schoolHolidays.length && <span className="muted-copy">등록된 학교 휴일이나 개인 휴가가 없습니다.</span>}
              </div>
            </section>
          </aside>
        </div>
      )}

      {viewMode === "trash" && (
        <section className="dongguk-panel">
          <div className="panel-heading">
            <div>
              <strong>휴지통</strong>
              <span>휴지통으로 이동한 기사는 메일 후보와 제외 뉴스에서 숨겨집니다.</span>
            </div>
            <span className="count-pill">{trashArticles.length}건</span>
          </div>
          <div className="home-article-list">
            {trashArticles.length ? (
              trashArticles.map((item, index) => {
                const article = item.article || {};
                const thumbnailUrl = getArticleThumbnail(article);
                return (
                  <article className="home-article-card trash" key={`${article.id || article.title}-trash-${index}`}>
                    <span className="lead-rank">{index + 1}</span>
                    {thumbnailUrl ? (
                      <img
                        className="home-article-thumb"
                        src={thumbnailUrl}
                        alt=""
                        loading="lazy"
                        onError={(event) => {
                          event.currentTarget.style.display = "none";
                        }}
                      />
                    ) : (
                      <div className="lead-thumb compact">
                        <div className="lead-thumb-mark">D</div>
                      </div>
                    )}
                    <div>
                      <div className="meta">
                        <span className="pill muted">휴지통</span>
                        <span>{article.source || "언론사 없음"}</span>
                        {item.trashed_at && <span>{item.trashed_at}</span>}
                        {item.mail_date && <span>이동 기준일 {item.mail_date}</span>}
                      </div>
                      <h3>{article.title || "제목 없음"}</h3>
                      <p>{article.summary || "요약문이 아직 없습니다."}</p>
                      <div className="excluded-reason">
                        <span>복구하면 다시 기사 목록과 메일 후보에서 확인할 수 있습니다.</span>
                        <button className="secondary compact" onClick={() => restoreTrashArticle(item)} type="button">
                          <RotateCcw size={14} /> 복구
                        </button>
                        <button className="secondary compact danger-text" onClick={() => permanentlyDeleteTrashArticle(item)} type="button">
                          <Trash2 size={14} /> 영구 삭제
                        </button>
                      </div>
                    </div>
                  </article>
                );
              })
            ) : (
              <EmptyState title="휴지통이 비어 있습니다" body="제외된 뉴스에서 휴지통으로 이동한 기사가 이곳에 표시됩니다." />
            )}
          </div>
        </section>
      )}

      {viewMode === "priority" && (
        <div className="dongguk-layout">
          <div className="dongguk-category-panel">
            <div className="panel-heading">
              <strong>상위 분류</strong>
              <span>{activeRangeStart === activeRangeEnd ? activeRangeEnd : `${activeRangeStart} ~ ${activeRangeEnd}`}</span>
            </div>
            <div className="dongguk-category-tabs" role="tablist" aria-label="홍보처 상위 분류">
              {candidateCategoryTabs.map((tab) => (
                <button
                  className={activeDonggukCategory === tab.label ? "active" : ""}
                  key={tab.label}
                  onClick={() => {
                    setActiveDonggukCategory(tab.label);
                    setActiveDonggukSubcategory("전체");
                  }}
                  type="button"
                >
                  <span>{tab.label}</span>
                  <b>{tab.count}</b>
                </button>
              ))}
            </div>
            {activeDonggukCategory !== "전체" && (
              <div className="subcategory-panel">
                <div className="panel-heading compact-heading">
                  <strong>하위 카테고리</strong>
                  <span>{activeDonggukCategory}</span>
                </div>
                <div className="dongguk-category-tabs subcategory-tabs" role="tablist" aria-label="홍보처 하위 카테고리">
                  {candidateSubcategoryTabs.map((tab) => (
                    <button
                      className={activeDonggukSubcategory === tab.label ? "active" : ""}
                      key={`${activeDonggukCategory}-${tab.label}`}
                      onClick={() => setActiveDonggukSubcategory(tab.label)}
                      type="button"
                    >
                      <span>{tab.label}</span>
                      <b>{tab.count}</b>
                    </button>
                  ))}
                </div>
              </div>
            )}
            <div className="workspace-sidebar-actions">
              <button className="secondary" onClick={copyMailPreview} type="button">
                <Mail size={15} /> 문안 복사
              </button>
              <button className="secondary" onClick={downloadDonggukHwp} type="button">
                <Download size={15} /> HWP 저장
              </button>
              <button className="secondary scroll-top-button" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })} type="button">
                <ChevronUp size={15} /> 맨 위로
              </button>
            </div>
          </div>

          <div className="dongguk-article-list">
            {renderManualArticleImportPanel()}
            {renderUnifiedTestSendPanel()}
            <div className="article-date-range-toolbar">
              <div className="date-range-fields">
                <label>
                  <span>기준일</span>
                  <input type="date" value={mailDate} onChange={(event) => setMailDate(event.target.value)} />
                </label>
                <button
                  className="secondary compact"
                  onClick={() => {
                    setMailDate(localDateKey());
                  }}
                  type="button"
                >
                  오늘
                </button>
              </div>
              <div className="date-range-summary">
                <strong>{loadingWorkWindow || !workWindowMatchesMailDate ? "조회 범위 계산 중" : "자동 기사 조회 범위"}</strong>
                <span>{activeArticleWindow.label}</span>
                <span>주말·공휴일·캘린더에 등록한 휴일을 자동으로 포함합니다.</span>
                {workWindowMatchesMailDate && workWindow?.days?.some((day) => !day.is_business_day) && (
                  <span>
                    {workWindow.days
                      .filter((day) => !day.is_business_day)
                      .map((day) => `${day.date} ${day.public_holiday_name || day.personal_holiday_names?.join(", ") || day.school_holiday_names?.join(", ") || "주말"}`)
                      .join(" · ")}
                  </span>
                )}
              </div>
            </div>
            <div className="candidate-heading">
              <div>
                <strong>
                  {activeDonggukCategory === "전체"
                    ? "오늘 수집된 기사"
                    : `${activeDonggukCategory}${activeDonggukSubcategory !== "전체" ? ` · ${activeDonggukSubcategory}` : ""}`}
                </strong>
                <span>
                  {loadingCandidates
                    ? "불러오는 중"
                    : `조회 기사 ${candidateArticles.length}건${exactLinkDuplicateCount ? ` · 동일 원문 링크 ${exactLinkDuplicateCount}건 통합` : ""} · 검색 결과 ${filteredCandidateRows.length}건 · 메일 포함 ${effectiveMailArticles.length}건${duplicateExcludedCount ? ` · 중복 주제 ${duplicateExcludedCount}건` : ""} · ${normalizedCandidatePage}/${candidateTotalPages}페이지`}
                </span>
              </div>
              <div className="candidate-actions">
                <label className="candidate-search-field">
                  <Search size={15} />
                  <input
                    aria-label="수집 기사 검색"
                    value={candidateSearchQuery}
                    onChange={(event) => setCandidateSearchQuery(event.target.value)}
                    placeholder="제목, 언론사, 요약 검색"
                  />
                  {candidateSearchQuery && (
                    <button aria-label="검색어 지우기" onClick={() => setCandidateSearchQuery("")} type="button">
                      <X size={14} />
                    </button>
                  )}
                </label>
                <button
                  aria-label="중복 주제 제외: 기사 제목과 요약의 핵심 단어, 원문 URL, 언론사와 발행 시각을 비교해 같은 주제를 묶고 우선순위가 가장 높은 기사 1개만 남깁니다."
                  className="secondary compact duplicate-filter-toggle active"
                  data-tooltip={duplicateFilterNeedsRefresh
                    ? "추가한 링크 기사까지 다시 비교합니다. 기사 제목과 요약의 핵심 단어, 원문 URL, 언론사와 발행 시각을 비교해 같은 주제를 묶고 우선순위가 가장 높은 기사 1개만 남깁니다."
                    : "중복된 주제를 가진 기사들 중 우선순위가 가장 높은 기사 1개만 남깁니다. URL로 기사를 추가하면 다시 실행할 수 있습니다."}
                  disabled={!duplicateFilterNeedsRefresh || loadingPreview}
                  onClick={refreshDuplicateTopicFilter}
                  type="button"
                >
                  {loadingPreview ? <Loader2 className="spin" size={15} /> : <CopyMinus size={15} />}
                  AI로 중복 주제 확인
                </button>
                <label className="candidate-limit-field">
                  <span>페이지당</span>
                  <select value={maxVisibleCandidates} onChange={(event) => setMaxVisibleCandidates(Number(event.target.value))}>
                    <option value={10}>10건</option>
                    <option value={20}>20건</option>
                    <option value={50}>50건</option>
                  </select>
                </label>
                <button className="secondary compact" disabled={runningCandidateCrawl} onClick={runDonggukCandidateCrawl} type="button">
                  {runningCandidateCrawl ? <Loader2 className="spin" size={15} /> : <RefreshCw size={15} />}
                  새로 확인
                </button>
                <button className="secondary compact" disabled={loadingCandidates} onClick={loadCandidateArticles} type="button">
                  {loadingCandidates ? <Loader2 className="spin" size={15} /> : <RefreshCw size={15} />}
                  새로고침
                </button>
              </div>
            </div>
            {!loadingCandidates && candidateArticles.length === 0 && (
              <EmptyState
                title="수집된 기사 후보가 없습니다"
                body="실제 기사 부재가 아니라 수집 데이터가 없을 수 있습니다. 새 기사 확인을 실행하거나 기준일을 바꿔 주세요."
              />
            )}
            {!loadingCandidates && candidateArticles.length > 0 && visibleCandidateRows.length === 0 && (
              <EmptyState
                title={candidateSearchQuery ? "검색 결과가 없습니다" : "이 카테고리의 기사 후보가 없습니다"}
                body={candidateSearchQuery ? "검색어를 바꾸거나 지운 뒤 다시 확인해 주세요." : "다른 카테고리 탭을 선택해 주세요."}
              />
            )}
            <div className="flat-candidate-list">
              {visibleCandidateRows.map(({ article, index, key }, visibleIndex) => {
                    const links = realArticleLinks(article);
                    const thumbnailUrl = getArticleThumbnail(article);
                    const includedInMail = mailArticleKeySet.has(key);
                    const isTrashed = Boolean(article.isTrashed);
                    const isInlineEditing = inlineEditingArticleKey === key && inlineArticleDraft;
                    const displayRank = ((normalizedCandidatePage - 1) * candidatePageSize) + visibleIndex + 1;
                    return (
                      <details className={`dongguk-article-card collapsible-article-card ${includedInMail ? "included-in-mail" : "excluded-from-mail"} ${isTrashed ? "trashed-article" : ""}`} key={key}>
                        <summary className="article-card-summary">
                          <span className={`article-summary-rank ${includedInMail ? "is-included" : ""}`}>{displayRank}</span>
                          <span className="article-summary-media" aria-hidden="true">
                            <span className="article-summary-media-mark">D</span>
                            <span className="article-summary-media-name">dongguk</span>
                            {thumbnailUrl && (
                              <img
                                src={thumbnailUrl}
                                alt=""
                                loading="lazy"
                                onError={(event) => {
                                  event.currentTarget.style.display = "none";
                                }}
                              />
                            )}
                          </span>
                          <span className="article-card-summary-copy">
                            <span className="article-summary-preview-topline">
                              <span className="article-card-summary-meta">
                                <span className={`article-major-category ${normalizeDonggukSectionKey(article.sectionLabel) || "foundation"}`}>
                                  {article.sectionLabel || donggukSections.foundation}
                                </span>
                                <span>{article.category}</span>
                                <span className={`priority-pill ${article.priorityTone}`}>{priorityDisplayName(article)}</span>
                                {article.isSyndicated && <span className="pill warning">중복 보도</span>}
                              </span>
                              <span className="article-summary-published">{formatDate(article.published_at)}</span>
                            </span>
                            <strong className="article-summary-title">{article.title}</strong>
                            <span className="article-summary-preview-text">{article.summary || "요약문이 아직 없습니다."}</span>
                            <span className="article-summary-preview-reason">{articlePriorityReason(article)}</span>
                          </span>
                          <span className="article-summary-actions">
                              <label
                                className={`mail-inclusion-status ${includedInMail ? "is-included" : "is-excluded"}`}
                                onClick={(event) => event.stopPropagation()}
                                onKeyDown={(event) => event.stopPropagation()}
                              >
                                <input
                                  aria-label={`${article.title} 메일 포함 여부`}
                                  checked={includedInMail}
                                  disabled={isTrashed || !isArticleInActiveRange(article)}
                                  onChange={(event) => setCandidateMailIncluded(article, index, event.target.checked)}
                                  onClick={(event) => event.stopPropagation()}
                                  type="checkbox"
                                />
                                <span>{includedInMail ? "메일 포함" : "메일 제외"}</span>
                              </label>
                            <ChevronDown className="article-card-summary-chevron" size={17} />
                          </span>
                        </summary>
                        <div className="article-card-expanded">
                          <div>
                          <div className="candidate-card-topline">
                            {!isTrashed && !isInlineEditing && (
                              <button className="secondary compact" onClick={() => beginInlineArticleEdit(article, index)} type="button">
                                <Pencil size={14} /> 편집
                              </button>
                            )}
                          </div>
                          {isInlineEditing ? (
                            <div className="inline-article-editor">
                              <label className="field">
                                <span>기사 제목</span>
                                <input
                                  value={inlineArticleDraft.title || ""}
                                  onChange={(event) => setInlineArticleDraft((draft) => ({ ...draft, title: event.target.value }))}
                                />
                              </label>
                              <label className="field">
                                <span>요약</span>
                                <textarea
                                  value={inlineArticleDraft.summary || ""}
                                  onChange={(event) => setInlineArticleDraft((draft) => ({ ...draft, summary: event.target.value }))}
                                />
                              </label>
                              <div className="inline-article-editor-grid">
                                <label className="field">
                                  <span>상위 분류</span>
                                  <select
                                    value={inlineArticleDraft.sectionLabel || donggukSections.foundation}
                                    onChange={(event) => setInlineArticleDraft((draft) => ({ ...draft, sectionLabel: event.target.value, section: event.target.value }))}
                                  >
                                    {Object.values(donggukSections).map((label) => <option key={label} value={label}>{label}</option>)}
                                  </select>
                                </label>
                                <label className="field">
                                  <span>하위 카테고리</span>
                                  <select
                                    value={inlineArticleDraft.category || ""}
                                    onChange={(event) => setInlineArticleDraft((draft) => ({ ...draft, category: event.target.value }))}
                                  >
                                    {donggukCategoryRules.map((rule) => <option key={rule.key} value={rule.label}>{rule.label}</option>)}
                                  </select>
                                </label>
                                <label className="field">
                                  <span>우선순위</span>
                                  <select
                                    value={inlineArticleDraft.priority || "P3"}
                                    onChange={(event) => setInlineArticleDraft((draft) => ({ ...draft, priority: event.target.value }))}
                                  >
                                    {donggukPriorityBands.map((band) => <option key={band.label} value={band.label}>{band.name}</option>)}
                                  </select>
                                </label>
                                <label className="field">
                                  <span>점수</span>
                                  <input
                                    min="0"
                                    max="100"
                                    type="number"
                                    value={inlineArticleDraft.score ?? 0}
                                    onChange={(event) => setInlineArticleDraft((draft) => ({ ...draft, score: Math.max(0, Math.min(100, Number(event.target.value) || 0)) }))}
                                  />
                                </label>
                                <label className="field">
                                  <span>작성일</span>
                                  <input
                                    type="date"
                                    value={articlePublishedDateKey(inlineArticleDraft)}
                                    onChange={(event) => setInlineArticleDraft((draft) => ({ ...draft, published_at: `${event.target.value}T12:00:00+09:00` }))}
                                  />
                                </label>
                                <label className="field inline-url-field">
                                  <span>대표 URL</span>
                                  <input
                                    value={realArticleLinks(inlineArticleDraft)[0] || ""}
                                    onChange={(event) => setInlineArticleDraft((draft) => ({
                                      ...draft,
                                      url: event.target.value,
                                      links: [event.target.value, ...realArticleLinks(draft).slice(1)].filter(Boolean),
                                    }))}
                                  />
                                </label>
                              </div>
                              <div className="inline-article-editor-actions">
                                <button className="secondary" disabled={savingInlineArticle} onClick={cancelInlineArticleEdit} type="button">취소</button>
                                <button className="primary" disabled={savingInlineArticle || !inlineArticleDraft.title?.trim()} onClick={() => saveInlineArticleEdit(article, index)} type="button">
                                  {savingInlineArticle ? <Loader2 className="spin" size={15} /> : <CheckCircle2 size={15} />}
                                  저장
                                </button>
                              </div>
                            </div>
                          ) : (
                            <>
                              <div className="meta">
                                <span className={`pill ${includedInMail ? "include" : "muted"}`}>{isTrashed ? "휴지통" : includedInMail ? "메일 포함" : "메일 제외"}</span>
                                <span>{article.score}점</span>
                                {article.isSyndicated && <span className="pill warning">중복 보도</span>}
                                {article.isCampaign && <span className="pill">캠페인 +8</span>}
                              </div>
                              <p>{article.summary}</p>
                              <div className="priority-reason">
                                <span>{articlePriorityReason(article)}</span>
                              </div>
                              <div className="dongguk-link-row">
                                <span>{article.source}</span>
                                <span>작성 {articlePublishedDateKey(article) || "날짜 미상"}</span>
                                <span>수집 {articleCollectedDateKey(article) || "날짜 미상"}</span>
                                <span>원문 링크 {links.length}개</span>
                              </div>
                              {links.length > 0 && (
                                <div className="article-url-list">
                                  {links.map((link) => (
                                    <a href={link} target="_blank" rel="noreferrer" key={link}>
                                      <ExternalLink size={14} /> 원문 보기
                                    </a>
                                  ))}
                                </div>
                              )}
                            </>
                          )}
                          {!includedInMail && !isTrashed && (
                            <div className="excluded-reason">
                              <span>{excludedArticleReason(article, key)}</span>
                            </div>
                          )}
                          {!isTrashed && !isInlineEditing && (
                            <button className="danger compact candidate-toggle" onClick={() => deleteCandidateArticle(article, index)} type="button">
                              <Trash2 size={14} /> 휴지통으로 이동
                            </button>
                          )}
                          </div>
                        </div>
                      </details>
                    );
              })}
            </div>
            {!loadingCandidates && filteredCandidateRows.length > 0 && (
              <div className="candidate-pagination" aria-label="수집 기사 페이지 이동">
                <button
                  className="secondary compact"
                  disabled={normalizedCandidatePage <= 1}
                  onClick={() => setCandidatePage((page) => Math.max(1, page - 1))}
                  type="button"
                >
                  <ChevronLeft size={15} /> 이전
                </button>
                <div className="candidate-page-numbers" aria-label={`전체 ${candidateTotalPages}페이지`}>
                  {Array.from({ length: candidateTotalPages }, (_, index) => index + 1).map((pageNumber) => (
                    <button
                      aria-current={pageNumber === normalizedCandidatePage ? "page" : undefined}
                      aria-label={`${pageNumber}페이지로 이동`}
                      className={`candidate-page-number ${pageNumber === normalizedCandidatePage ? "active" : ""}`}
                      key={pageNumber}
                      onClick={() => setCandidatePage(pageNumber)}
                      type="button"
                    >
                      {pageNumber}
                    </button>
                  ))}
                </div>
                <button
                  className="secondary compact"
                  disabled={normalizedCandidatePage >= candidateTotalPages}
                  onClick={() => setCandidatePage((page) => Math.min(candidateTotalPages, page + 1))}
                  type="button"
                >
                  다음 <ChevronRight size={15} />
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {viewMode === "stats" && (
        <div className="dongguk-stats">
          <ChartCard
            title="상위 카테고리별 기사 수"
            data={sectionChart.map((item) => ({
              ...item,
              label: item.label === donggukSections.foundation
                ? "동국대·건학위"
                : item.label === donggukSections.education
                  ? "대학·교육"
                  : "불교·종단",
            }))}
            xKey="label"
            yKey="count"
            color="#2271b1"
            note="동국대 법인/건학위, 대학 교육, 불교 종단 기준"
            seriesName="기사 수"
            valueSuffix="건"
          />
          <ChartCard title="우선순위별 기사 수" data={priorityChart.map((item) => {
            const band = donggukPriorityBands.find((entry) => entry.label === item.label);
            return { ...item, label: priorityDisplayName(band) };
          })} xKey="label" yKey="count" color="#00a32a" note="최우선~낮음 점수 구간 기준" seriesName="기사 수" valueSuffix="건" />
          <div className="dongguk-stat-table">
            <div className="panel-heading">
              <strong>섹션별 구성</strong>
              <span>동국대·대학 교육·불교계 기준으로 분류</span>
            </div>
            {sectionChart.map(({ label: section, count }) => (
              <div className={`stat-row ${count ? "" : "is-empty"}`} key={section}>
                <span>{section}</span>
                <strong>{count}건</strong>
              </div>
            ))}
          </div>
          <div className="dongguk-stat-table">
            <div className="panel-heading">
              <strong>우선순위/대표 기사 선정 기준</strong>
              <span>사용자 지정 기준 반영</span>
            </div>
            {["상위/하위 카테고리", "기사별 1~2문장 요약", "관리자 입력 기준", "대표 기사 1건 선정 기준", "같은 주제 중복 보도 묶음", "데일리 발송 제목", "메일 포함/제외 편집 결과"].map((item) => (
              <div className="stat-row" key={item}>
                <span>{item}</span>
                <strong>반영</strong>
              </div>
            ))}
          </div>
          <section className="ai-insights-panel">
            <div className="ai-insights-heading">
              <div>
                <span className="ai-insights-icon"><Sparkles size={18} /></span>
                <div>
                  <strong>AI 인사이트</strong>
                  <p>관리자의 기사 포함·제외, 순서, 우선순위 수정을 학습해 선정 기준에 반영합니다.</p>
                </div>
              </div>
              <button
                className="secondary compact"
                disabled={generatingPriorityInsight || loadingPriorityInsights}
                onClick={generatePriorityInsight}
                type="button"
              >
                {generatingPriorityInsight ? <Loader2 className="spin" size={15} /> : <RefreshCw size={15} />}
                지난달 분석 실행
              </button>
            </div>

            <div className="insight-cadence-strip">
              <span><b>월별 학습</b>{priorityInsightCadence.monthly || "지난달 행동을 분석해 기준을 소폭 반영합니다."}</span>
              <span><b>분기 재조정</b>{priorityInsightCadence.quarterly || "직전 분기 전체 행동으로 기준을 다시 조정합니다."}</span>
            </div>

            <div className="ai-insights-grid">
              <div className="active-insight-rules">
                <div className="panel-heading clean">
                  <div>
                    <strong>현재 반영된 우선순위</strong>
                    <span>메일 대표 기사 선정 시 기본 기준과 함께 AI에 전달됩니다.</span>
                  </div>
                  <b>{activeInsightRules.length}개</b>
                </div>
                {activeInsightRules.length ? (
                  <div className="active-insight-list">
                    {activeInsightRules.map((rule, index) => (
                      <button
                        className="active-insight-rule"
                        key={`${rule.insight_id}-${rule.rule_text}-${index}`}
                        onClick={() => openPriorityInsight(rule.insight_id)}
                        type="button"
                      >
                        <span>{rule.target || "전체"}</span>
                        <strong>{rule.rule_text}</strong>
                        <small>{rule.period_key} · 근거 {rule.evidence_count || 0}건</small>
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="insight-empty">
                    <Sparkles size={20} />
                    <span>아직 반복 행동으로 반영된 기준이 없습니다.</span>
                  </div>
                )}
              </div>

              <div className="insight-history">
                <div className="panel-heading clean">
                  <div>
                    <strong>월별 반영 로그</strong>
                    <span>월을 선택하면 근거가 된 사용자 수행 기록을 볼 수 있습니다.</span>
                  </div>
                </div>
                {priorityInsights.length ? (
                  <div className="insight-history-list">
                    {priorityInsights.map((insight) => (
                      <button
                        className={selectedPriorityInsightId === insight.id ? "active" : ""}
                        key={insight.id}
                        onClick={() => openPriorityInsight(insight.id)}
                        type="button"
                      >
                        <span>
                          <strong>{insight.period_key}</strong>
                          <small>{insight.cadence_label}</small>
                        </span>
                        <span>
                          <b>{insight.changes?.length || 0}개 반영</b>
                          <em className={`insight-status ${insight.status}`}>
                            {insight.status === "applied" ? "반영 중" : insight.status === "deleted" ? "삭제됨" : "변경 없음"}
                          </em>
                        </span>
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="insight-empty">
                    <span>월별 분석 기록이 없습니다. 지난달 분석을 실행하면 이곳에 기록됩니다.</span>
                  </div>
                )}
              </div>
            </div>

            {priorityInsightDetail && (
              <div className="insight-detail">
                <div className="insight-detail-heading">
                  <div>
                    <span>{priorityInsightDetail.period_key} · {priorityInsightDetail.cadence_label}</span>
                    {!!priorityInsightDetail.demo_action_count && (
                      <span className="insight-demo-badge">
                        7월 확인용 목 데이터 {priorityInsightDetail.demo_action_count}건 포함
                      </span>
                    )}
                    <strong>{priorityInsightDetail.summary}</strong>
                    <p>{priorityInsightDetail.rationale}</p>
                  </div>
                  {priorityInsightDetail.status === "applied" && (
                    <button
                      className="secondary compact danger-text"
                      onClick={() => deletePriorityInsight(priorityInsightDetail)}
                      title="기준 반영만 취소되며 근거 행동 로그는 보존됩니다."
                      type="button"
                    >
                      <Trash2 size={14} /> 인사이트 삭제
                    </button>
                  )}
                </div>

                <div className="insight-change-list">
                  {(priorityInsightDetail.changes || []).map((change, index) => (
                    <div className="insight-change-card" key={`${change.rule_text}-${index}`}>
                      <span>{change.target || "전체"} · 근거 {change.evidence_count || 0}건</span>
                      <div>
                        <small>변경 전</small>
                        <p>{change.before || "기존 기준 유지"}</p>
                      </div>
                      <div>
                        <small>변경 후</small>
                        <strong>{change.rule_text || change.after}</strong>
                      </div>
                      <p className="insight-change-reason">{change.reason}</p>
                    </div>
                  ))}
                  {!priorityInsightDetail.changes?.length && (
                    <div className="insight-empty">반복 근거가 충분하지 않아 이 기간에는 기준을 변경하지 않았습니다.</div>
                  )}
                </div>

                <details className="insight-action-log">
                  <summary>
                    <span>이 판단에 사용한 사용자 수행 로그</span>
                    <b>{priorityInsightDetail.actions?.length || 0}건</b>
                  </summary>
                  <div className="insight-action-list">
                    {(priorityInsightDetail.actions || []).map((action) => (
                      <div key={action.id}>
                        <span>
                          <strong>{action.action_label}</strong>
                          <small>{action.created_at ? formatDate(action.created_at) : action.mail_date || ""}</small>
                        </span>
                        <p>{action.article_title || (action.action_type === "criteria_edit" ? "AI 기사 선정 기준" : "기사 정보 없음")}</p>
                        <small>
                          {formatInsightActionState(action.before)}
                          {Object.keys(action.before || {}).length && Object.keys(action.after || {}).length ? " → " : ""}
                          {formatInsightActionState(action.after)}
                        </small>
                        {action.reason && <em>{action.reason}</em>}
                      </div>
                    ))}
                    {!priorityInsightDetail.actions?.length && <div className="insight-empty">이 기간에 저장된 사용자 수행 로그가 없습니다.</div>}
                  </div>
                </details>
              </div>
            )}

            {loadingPriorityInsights && (
              <div className="loading-line"><Loader2 className="spin" size={16} /> AI 인사이트를 불러오는 중</div>
            )}
          </section>
        </div>
      )}

      {viewMode === "edit" && (
        <div className="article-edit-page">
          <div className="article-edit-header">
            <div>
              <h2>기사 편집</h2>
              <p>기사의 제목, 요약, 분류, 우선순위 정보를 조정합니다.</p>
            </div>
            <div className="article-edit-header-actions">
              <button
                className="primary"
                onClick={async () => {
                  await saveEditedPreview(editedMailArticles);
                  editBaselineArticles.current = cloneArticles(editedMailArticles);
                  setEditDirty(false);
                  showToast?.("기사 편집 내용을 저장했습니다.", "success");
                  setViewMode("mail");
                }}
                type="button"
              >
                저장
              </button>
            </div>
          </div>

          <section className="article-url-add-card">
            <div className="article-url-add-icon">
              <ExternalLink size={20} />
            </div>
            <div>
              <strong>기사 URL 추가 <span>(선택)</span></strong>
              <p>URL을 추가하면 일부 정보를 자동으로 불러옵니다.</p>
            </div>
            <input
              value={manualArticleUrl}
              onChange={(event) => setManualArticleUrl(event.target.value)}
              placeholder="https://example.com/article"
            />
            <button className="secondary" disabled={addingManualArticle} onClick={addManualArticleFromLink} type="button">
              {addingManualArticle ? <Loader2 className="spin" size={16} /> : <Plus size={16} />}
              링크 기사 추가
            </button>
          </section>

          {loadingPreview && (
            <div className="loading-line">
              <Loader2 className="spin" size={18} /> AI가 같은 주제 기사를 묶고 대표 기사를 고르는 중
            </div>
          )}

          <div className="article-edit-list">
            {editedMailArticles.map((article, index) => {
              const links = realArticleLinks(article);
              return (
                <article className="article-edit-row" key={`${article.id || article.title}-${index}`}>
                  <div className="article-edit-card">
                    <div className="article-edit-titlebar">
                      <span className="article-edit-number">{index + 1}</span>
                      <input
                        className="article-title-input"
                        value={article.title || ""}
                        onChange={(event) => updatePreviewArticle(index, { title: event.target.value })}
                      />
                      <div className="mail-editor-actions">
                        <button className="secondary compact icon-only" disabled={index === 0} onClick={() => movePreviewArticle(index, -1)} title="위로 이동" type="button">↑</button>
                        <button className="secondary compact icon-only" disabled={index === editedMailArticles.length - 1} onClick={() => movePreviewArticle(index, 1)} title="아래로 이동" type="button">↓</button>
                        <button className="danger compact icon-only" onClick={() => removePreviewArticle(index)} title="이번 메일에서 제외" type="button">
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>

                    <label className="field full">
                      <span>요약</span>
                      <textarea value={article.summary || ""} onChange={(event) => updatePreviewArticle(index, { summary: event.target.value })} />
                    </label>

                    <div className="article-edit-grid">
                      <label className="field">
                        <span>상위 카테고리</span>
                        <select value={article.sectionLabel} onChange={(event) => updatePreviewArticle(index, { sectionLabel: event.target.value, section: event.target.value })}>
                          {Object.values(donggukSections).map((label) => <option key={label} value={label}>{label}</option>)}
                        </select>
                      </label>
                      <label className="field">
                        <span>하위 카테고리</span>
                        <select value={article.category} onChange={(event) => updatePreviewArticle(index, { category: event.target.value })}>
                          {donggukCategoryRules.map((rule) => <option key={rule.key} value={rule.label}>{rule.label}</option>)}
                        </select>
                      </label>
                      <label className="field">
                        <span>우선순위</span>
                        <select value={article.priority} onChange={(event) => updatePreviewArticle(index, { priority: event.target.value })}>
                          {donggukPriorityBands.map((band) => <option key={band.label} value={band.label}>{band.name}</option>)}
                        </select>
                      </label>
                      <label className="field">
                        <span>점수</span>
                        <input
                          min="0"
                          max="100"
                          type="number"
                          value={article.score}
                          onChange={(event) => updatePreviewArticle(index, { score: Math.max(0, Math.min(100, Number(event.target.value) || 0)) })}
                        />
                      </label>
                      <label className="field">
                        <span>기사 작성일</span>
                        <input
                          type="date"
                          value={articlePublishedDateKey(article)}
                          onChange={(event) => updatePreviewArticle(index, { published_at: `${event.target.value}T12:00:00+09:00` })}
                        />
                      </label>
                      <label className="field article-url-field">
                        <span>대표 URL</span>
                        <input
                          value={links[0] || ""}
                          onChange={(event) => {
                            const nextUrl = event.target.value;
                            updatePreviewArticle(index, {
                              url: nextUrl,
                              links: [nextUrl, ...links.slice(1)].filter(Boolean),
                            });
                          }}
                        />
                      </label>
                    </div>
                  </div>

                  <aside className="article-edit-info">
                    <strong>선택 기사 정보</strong>
                    <div className="meta">
                      <span>{article.sectionLabel}</span>
                      <span>{article.category}</span>
                      <span>점수 {article.score}</span>
                      {article.isSyndicated && <span>중복 보도 {links.length}건</span>}
                    </div>
                    <div className="article-edit-links">
                      <b>기사 원문</b>
                      {links.length ? (
                        <ul>
                          {links.map((link) => (
                            <li key={link}>
                              <a href={link} target="_blank" rel="noreferrer">{link.replace(/^https?:\/\//i, "")}</a>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <span>등록된 원문 URL이 없습니다.</span>
                      )}
                    </div>
                  </aside>
                </article>
              );
            })}
          </div>

          {!loadingPreview && !editedMailArticles.length && (
            <EmptyState
              title="편집할 대표 기사가 없습니다"
              body="오늘 수집된 기사 화면에서 메일에 포함할 기사를 선택하거나 AI 미리보기를 갱신해 주세요."
            />
          )}
        </div>
      )}

      {viewMode === "mail" && (
        <div className="dongguk-mail-preview integrated-mail-preview">
          <div className="panel-heading">
            <div>
              <span className="preview-section-label">선택 기사 메일 미리보기</span>
              <strong>{mailSubject}</strong>
              <span>
                {loadingPreview
                  ? "AI 편집 미리보기를 생성하는 중입니다."
                  : previewCached
                    ? `저장된 AI 편집본 표시 · 제외 ${previewExcludedCount}건`
                    : previewEditorUsed
                      ? `AI 편집 적용 · 제외 ${previewExcludedCount}건`
                    : "선택한 기사를 AI로 편집해 대표 기사만 표시합니다."}
              </span>
            </div>
            <div className="candidate-actions">
              <button className="secondary compact" onClick={() => setViewMode("priority")} type="button">
                <ChevronUp size={15} /> 미리보기 접기
              </button>
              <button className="secondary compact" disabled={loadingPreview || !mailArticles.length} onClick={() => loadDifyPreview(true)} type="button">
                {loadingPreview ? <Loader2 className="spin" size={15} /> : <Sparkles size={15} />}
                AI 미리보기 갱신
              </button>
            </div>
          </div>
          {!isMailEditView && (
            <div className="test-send-panel">
              <div>
                <strong>테스트 전송</strong>
                <span>현재 미리보기 문안을 아래 테스트 수신인에게만 보내며, 발송 기록과 중복 제외 기준에는 반영하지 않습니다.</span>
                <textarea
                  className="test-send-input"
                  value={testEmails}
                  onChange={(event) => setTestEmails(event.target.value)}
                  placeholder="테스트로 받을 이메일 주소"
                />
                {recentRecipients.length > 0 && (
                  <div className="test-recipient-chips" aria-label="최근 수신인">
                    {recentRecipients.slice(0, 4).map((email) => (
                      <button
                        className="chip-button"
                        key={`test-${email}`}
                        onClick={() => {
                          const current = testEmails.replaceAll(",", "\n").split("\n").map((item) => item.trim()).filter(Boolean);
                          setTestEmails([...new Set([...current, email])].join("\n"));
                        }}
                        type="button"
                      >
                        {email}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <div className="test-send-meta">
                <span>테스트 수신인 {testRecipientList.length}명</span>
                <button className="primary compact" disabled={sending || !testRecipientList.length} onClick={() => sendDonggukEmail(true)} type="button">
                  {sending ? <Loader2 className="spin" size={15} /> : <Send size={15} />}
                  테스트 전송
                </button>
              </div>
            </div>
          )}
          {isMailEditView && (
            <div className="edit-section-panel">
              <div>
                <strong>편집</strong>
                <span>기사 순서, 제목, 요약, 분류, 우선순위 정보를 조정합니다.</span>
              </div>
              <div className="manual-article-add">
                <input
                  value={manualArticleUrl}
                  onChange={(event) => setManualArticleUrl(event.target.value)}
                  placeholder="추가할 기사 URL"
                />
                <button className="secondary compact" disabled={addingManualArticle} onClick={addManualArticleFromLink} type="button">
                  {addingManualArticle ? <Loader2 className="spin" size={15} /> : <Plus size={15} />}
                  링크 기사 추가
                </button>
              </div>
            </div>
          )}
          {loadingPreview && (
            <div className="loading-line">
              <Loader2 className="spin" size={18} /> AI가 같은 주제 기사를 묶고 대표 기사를 고르는 중
            </div>
          )}
          {Object.values(donggukSections).map((section) => {
            const rows = editedMailArticles.filter((article) => article.sectionLabel === section);
            if (!rows.length) return null;
            return (
              <div className="mail-section" key={section}>
                <h3>{section}</h3>
                {rows.map((article, index) => (
                  <article className="mail-editor-card" key={`${article.id || article.title}-${index}`}>
                    <div className="mail-editor-main">
                      <div className="mail-editor-title-row">
                        <strong>{index + 1}. {article.title} [{article.source}]</strong>
                        {isMailEditView && (
                          <div className="mail-editor-actions">
                            <button className="secondary compact icon-only" disabled={index === 0} onClick={() => movePreviewArticle(editedMailArticles.indexOf(article), -1)} title="위로 이동" type="button">↑</button>
                            <button className="secondary compact icon-only" disabled={index === rows.length - 1} onClick={() => movePreviewArticle(editedMailArticles.indexOf(article), 1)} title="아래로 이동" type="button">↓</button>
                            <button className="danger compact icon-only" onClick={() => removePreviewArticle(editedMailArticles.indexOf(article))} title="이번 메일에서 제외" type="button">
                              <Trash2 size={14} />
                            </button>
                          </div>
                        )}
                      </div>
                      {isMailEditView ? (
                        <>
                          <label className="field">
                            <span>제목</span>
                            <input value={article.title} onChange={(event) => updatePreviewArticle(editedMailArticles.indexOf(article), { title: event.target.value })} />
                          </label>
                          <label className="field">
                            <span>요약</span>
                            <textarea value={article.summary || ""} onChange={(event) => updatePreviewArticle(editedMailArticles.indexOf(article), { summary: event.target.value })} />
                          </label>
                          <div className="mail-editor-grid">
                            <label className="field">
                              <span>상위 카테고리</span>
                              <select value={article.sectionLabel} onChange={(event) => updatePreviewArticle(editedMailArticles.indexOf(article), { sectionLabel: event.target.value, section: event.target.value })}>
                                {Object.values(donggukSections).map((label) => <option key={label} value={label}>{label}</option>)}
                              </select>
                            </label>
                            <label className="field">
                              <span>하위 카테고리</span>
                              <select value={article.category} onChange={(event) => updatePreviewArticle(editedMailArticles.indexOf(article), { category: event.target.value })}>
                                {donggukCategoryRules.map((rule) => <option key={rule.key} value={rule.label}>{rule.label}</option>)}
                              </select>
                            </label>
                            <label className="field">
                              <span>우선순위</span>
                              <select value={article.priority} onChange={(event) => updatePreviewArticle(editedMailArticles.indexOf(article), { priority: event.target.value })}>
                                {donggukPriorityBands.map((band) => <option key={band.label} value={band.label}>{band.name}</option>)}
                              </select>
                            </label>
                            <label className="field">
                              <span>점수</span>
                              <input
                                min="0"
                                max="100"
                                type="number"
                                value={article.score}
                                onChange={(event) => updatePreviewArticle(editedMailArticles.indexOf(article), { score: Math.max(0, Math.min(100, Number(event.target.value) || 0)) })}
                              />
                            </label>
                          </div>
                        </>
                      ) : (
                        <>
                          <p>{article.summary || "요약문이 아직 없습니다."}</p>
                          {realArticleLinks(article).length > 0 && (
                            <div className="mail-preview-links">
                              {realArticleLinks(article).map((link) => (
                                <a href={link} target="_blank" rel="noreferrer" key={link}>{link}</a>
                              ))}
                            </div>
                          )}
                        </>
                      )}
                    </div>
                    {isMailEditView && (
                      <aside className="mail-editor-side">
                        <div className="meta">
                          <span className={`priority-pill ${article.priorityTone}`}>{priorityDisplayName(article)}</span>
                          <span>{article.sectionLabel}</span>
                          <span>{article.category}</span>
                          <span>점수 {article.score}</span>
                          {article.isSyndicated && <span>중복 보도 {realArticleLinks(article).length}건</span>}
                        </div>
                        <strong>기사 원문</strong>
                        {realArticleLinks(article).map((link) => <a href={link} target="_blank" rel="noreferrer" key={link}>{link}</a>)}
                      </aside>
                    )}
                  </article>
                ))}
              </div>
            );
          })}
          {!loadingPreview && !editedMailArticles.length && (
            <EmptyState
              title={mailArticles.length ? "메일에 넣을 대표 기사가 없습니다" : "AI 편집 미리보기가 없습니다"}
              body={mailArticles.length
                ? "전날 발송된 유사 기사이거나 AI 대표 기사 선정 기준에서 제외된 기사일 수 있습니다. 필요하면 AI 미리보기 갱신을 다시 실행해 주세요."
                : "기준일을 선택해 기사 후보를 불러오거나, 오늘 수집된 기사 화면에서 발송할 기사를 선택한 뒤 미리보기를 갱신해 주세요."}
            />
          )}
        </div>
      )}

      {viewMode === "history" && (
        <div className="dongguk-history">
          <div className="panel-heading">
            <div>
              <strong>홍보처 발송 기록</strong>
              <span>최근 발송 메일과 제외된 유사 기사 수를 확인합니다.</span>
            </div>
            <button className="secondary compact" onClick={() => loadDonggukHistory(false)} type="button">
              <RefreshCw size={15} /> 새로고침
            </button>
          </div>
          {history.length ? history.map((item) => (
            <article className="history-card" key={`${item.id}-${item.sent_at}`}>
              <div>
                <strong>{item.subject}</strong>
                <span>{formatDate(item.sent_at)} · 수신자 {item.recipients?.join(", ")}</span>
              </div>
              <div className="history-stats">
                <b>발송 {item.article_count}건</b>
                <b>유사 제외 {item.excluded_count || 0}건</b>
              </div>
              <div className="history-articles">
                {(item.articles || []).slice(0, 5).map((article, index) => (
                  <p key={`${article.title}-${index}`}>{index + 1}. {article.title}</p>
                ))}
              </div>
            </article>
          )) : (
            <EmptyState title="발송 기록 없음" body="홍보처 메일을 발송하면 이곳에 모입니다." />
          )}
        </div>
      )}
      {recipientContextMenu && (
        <div
          className="inline-context-menu"
          onClick={(event) => event.stopPropagation()}
          style={{ left: recipientContextMenu.x, top: recipientContextMenu.y }}
        >
          <button type="button" onClick={() => editRecipientFromMenu(recipientContextMenu.index)}>
            수정
          </button>
          <button className="danger-text" type="button" onClick={() => {
            deleteRecipient(recipientContextMenu.index);
            setRecipientContextMenu(null);
          }}>
            삭제
          </button>
        </div>
      )}
      {priorityContextMenu && (
        <div
          className="inline-context-menu"
          onClick={(event) => event.stopPropagation()}
          style={{ left: priorityContextMenu.x, top: priorityContextMenu.y }}
        >
          <button type="button" onClick={() => focusPriorityRule(priorityContextMenu.index)}>
            수정
          </button>
          <button className="danger-text" type="button" onClick={() => {
            deletePriorityRule(priorityContextMenu.index);
            setPriorityContextMenu(null);
          }}>
            삭제
          </button>
        </div>
      )}
    </section>
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
  const [dashboardMode, setDashboardMode] = useState("general");
  const [loadedDashboardMode, setLoadedDashboardMode] = useState(null);
  const [donggukViewMode, setDonggukViewMode] = useState("priority");
  const [toast, setToast] = useState(null);
  const [loadingSide, setLoadingSide] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [chatSidebarOpen, setChatSidebarOpen] = useState(false);
  const [notificationOpen, setNotificationOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [loadingNotifications, setLoadingNotifications] = useState(false);
  const [keywordArticleCountOverrides, setKeywordArticleCountOverrides] = useState({});
  const [donggukArticleSummary, setDonggukArticleSummary] = useState({});
  const shellRequestIdRef = useRef(0);
  const chatsLoadedRef = useRef(false);

  const selectedKeyword = keywords.find((item) => item.id === selectedKeywordId);
  const donggukKeyword = keywords.find((item) => keywordName(item).includes("동국"));
  const activeKeyword = dashboardMode === "dongguk" && donggukKeyword ? donggukKeyword : selectedKeyword;
  const activeKeywordId = activeKeyword?.id || selectedKeywordId;
  const showToast = (message, type = "info") => setToast({ message, type });
  const unreadNotificationCount = notifications.filter((item) => !item.read).length;

  async function loadNotifications() {
    setLoadingNotifications(true);
    try {
      const data = await endpoints.donggukNotifications();
      setNotifications(data.items || []);
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      setLoadingNotifications(false);
    }
  }

  async function loadShell(mode = dashboardMode) {
    const requestId = ++shellRequestIdRef.current;
    setLoadingSide(true);
    try {
      const [keywordData, chatData] = await Promise.all([
        endpoints.keywords(mode, localDateKey()),
        chatsLoadedRef.current ? Promise.resolve(null) : endpoints.chats(),
      ]);
      if (requestId !== shellRequestIdRef.current) return;
      const nextKeywords = keywordData.items || [];
      const nextDonggukKeyword = nextKeywords.find((item) => keywordName(item).includes("동국"));

      setKeywords(nextKeywords);
      if (chatData) {
        setChats(chatData.items || []);
        chatsLoadedRef.current = true;
      }
      setSelectedKeywordId((current) => {
        if (current && nextKeywords.some((item) => item.id === current)) return current;
        return mode === "dongguk"
          ? nextDonggukKeyword?.id || nextKeywords[0]?.id || null
          : nextKeywords[0]?.id || null;
      });
      setLoadedDashboardMode(mode);
      setLoginRequired(false);
    } catch (err) {
      if (requestId !== shellRequestIdRef.current) return;
      if (String(err.message).includes("Authentication")) setLoginRequired(true);
      else showToast(err.message, "error");
    } finally {
      if (requestId === shellRequestIdRef.current) {
        setBootstrapped(true);
        setLoadingSide(false);
      }
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
    setLoadedDashboardMode(null);
    loadShell(dashboardMode);
  }, [dashboardMode]);

  useEffect(() => {
    if (bootstrapped && !loginRequired) loadNotifications();
  }, [bootstrapped, loginRequired]);

  useEffect(() => {
    if (activeTab !== "dongguk") return;
    if (!donggukKeyword?.id) return;
    if (selectedKeywordId === donggukKeyword.id) return;
    setSelectedKeywordId(donggukKeyword.id);
  }, [activeTab, donggukKeyword?.id, selectedKeywordId]);

  useEffect(() => {
    if (dashboardMode === "general") {
      loadSummary(selectedKeywordId);
    }
  }, [selectedKeywordId, dashboardMode]);

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

  async function openChatSidebar() {
    setChatSidebarOpen(true);
    await ensureChatSession(activeKeywordId || selectedKeywordId);
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

  const modeReady = loadedDashboardMode === dashboardMode;

  return (
    <div className={`app-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""} ${chatSidebarOpen ? "chat-sidebar-open" : ""}`}>
      <Sidebar
        keywords={modeReady ? keywords : []}
        selectedKeywordId={selectedKeywordId}
        setSelectedKeywordId={setSelectedKeywordId}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        dashboardMode={dashboardMode}
        setDashboardMode={setDashboardMode}
        donggukViewMode={donggukViewMode}
        setDonggukViewMode={setDonggukViewMode}
        chatSidebarOpen={chatSidebarOpen}
        onOpenChat={openChatSidebar}
        onCreateKeyword={createKeyword}
        onUpdateKeyword={updateKeyword}
        onDeleteKeyword={deleteKeyword}
        loading={loadingSide}
        collapsed={sidebarCollapsed}
        keywordArticleCountOverrides={keywordArticleCountOverrides}
        donggukArticleSummary={donggukArticleSummary}
      />
      <button
        aria-label={sidebarCollapsed ? "왼쪽 사이드바 열기" : "왼쪽 사이드바 닫기"}
        aria-expanded={!sidebarCollapsed}
        className={`sidebar-edge-toggle ${sidebarCollapsed ? "is-collapsed" : "is-expanded"}`}
        onClick={() => setSidebarCollapsed((collapsed) => !collapsed)}
        title={sidebarCollapsed ? "왼쪽 사이드바 열기" : "왼쪽 사이드바 닫기"}
        type="button"
      >
        {sidebarCollapsed ? <ChevronRight size={19} /> : <ChevronLeft size={19} />}
      </button>
      <main className="main">
        {!(dashboardMode === "dongguk" && activeTab === "dongguk" && donggukViewMode === "trash") && (
          <header className="topbar">
            <div className="topbar-title">
              <span className="console-mark" aria-hidden="true" />
              <div>
                <span className="eyebrow">뉴스 인텔리전스 콘솔</span>
                <h1>{activeKeyword ? keywordName(activeKeyword) : "키워드를 선택하세요"}</h1>
              </div>
            </div>
            {dashboardMode !== "dongguk" && (
              <div className="topbar-actions">
              <div className="notification-menu">
                <button
                  className="ghost icon-round"
                  title="알림"
                  type="button"
                  onClick={() => {
                    setNotificationOpen((open) => !open);
                    loadNotifications();
                  }}
                >
                  <Bell size={19} />
                  {unreadNotificationCount > 0 && <span className="notification-dot">{unreadNotificationCount}</span>}
                </button>
                {notificationOpen && (
                  <div className="notification-panel">
                    <div className="notification-head">
                      <strong>알림</strong>
                      <button className="ghost compact" onClick={loadNotifications} type="button">새로고침</button>
                    </div>
                    {loadingNotifications ? (
                      <div className="notification-empty"><Loader2 className="spin" size={16} /> 불러오는 중</div>
                    ) : notifications.length ? (
                      <div className="notification-list">
                        {notifications.map((item) => (
                          <div className="notification-item" key={item.id}>
                            <span className={`notification-type ${item.type}`}>{item.type === "dify" ? "AI" : "수집"}</span>
                            <strong>{item.title}</strong>
                            <p>{item.message}</p>
                            <small>{formatDate(item.created_at)}</small>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="notification-empty">아직 표시할 알림이 없습니다.</div>
                    )}
                  </div>
                )}
              </div>
              </div>
            )}
          </header>
        )}

        {!modeReady && (
          <div className="mode-loading" role="status">
            <Loader2 className="spin" size={22} />
            <span>{dashboardMode === "dongguk" ? "홍보처 화면을 불러오는 중" : "대시보드를 불러오는 중"}</span>
          </div>
        )}

        {modeReady && dashboardMode === "general" && activeTab === "stats" && (
          <Summary selectedKeyword={selectedKeyword} articlePage={articlePage} importancePage={importancePage} />
        )}

        {modeReady && activeTab === "articles" && (
          <Articles selectedKeywordId={selectedKeywordId} selectedKeyword={selectedKeyword} topItems={topItems} showToast={showToast} refreshSummary={() => loadSummary()} />
        )}
        {modeReady && activeTab === "dongguk" && (
          <DonggukPrConsole
            selectedKeyword={activeKeyword}
            selectedKeywordId={activeKeywordId}
            selectedKeywordName={activeKeyword ? keywordName(activeKeyword) : ""}
            showToast={showToast}
            onUpdateKeyword={updateKeyword}
            viewMode={donggukViewMode}
            setViewMode={setDonggukViewMode}
            onCandidateCountChange={(keywordId, summary) => {
              setDonggukArticleSummary(summary || {});
              setKeywordArticleCountOverrides((prev) => {
                const next = { ...prev };
                if (summary == null) delete next[keywordId];
                else next[keywordId] = Number(summary.total || 0);
                return next;
              });
            }}
          />
        )}
        {modeReady && activeTab === "stats" && (
          <Stats
            selectedKeywordId={selectedKeywordId}
            selectedKeyword={selectedKeyword}
            selectedKeywordName={selectedKeyword ? keywordName(selectedKeyword) : ""}
            showToast={showToast}
          />
        )}
      </main>
      <aside className={`right-chat-sidebar ${chatSidebarOpen ? "open" : ""}`} aria-label="AI 채팅">
        <div className="right-chat-head">
          <div>
            <strong>AI 채팅</strong>
            <span>{activeKeyword ? keywordName(activeKeyword) : "키워드를 선택하세요"}</span>
          </div>
          <button className="icon-button" onClick={() => setChatSidebarOpen(false)} title="오른쪽 사이드바 닫기" type="button">
            <X size={17} />
          </button>
        </div>
        {chatSidebarOpen && (
          <Chat
            chatId={selectedChatId}
            conversationId={chatConversationId}
            setConversationId={setChatConversationId}
            messages={chatMessages}
            setMessages={setChatMessages}
            ensureChat={() => ensureChatSession(activeKeywordId || selectedKeywordId)}
            onReset={resetCurrentChat}
            selectedKeywordId={activeKeywordId || selectedKeywordId}
            selectedKeywordName={activeKeyword ? keywordName(activeKeyword) : ""}
            showToast={showToast}
          />
        )}
      </aside>
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
