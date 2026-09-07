"use strict";

const state = {
  reportIndex: [], currentYear: null, currentMonth: null,
  today: null, selectedDate: null, loadedReports: [], viewingMode: "today"
};

const $ = selector => document.querySelector(selector);
const escapeHTML = (value = "") => String(value).replace(/[&<>'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"})[char]);
const safeURL = (value = "") => /^https?:\/\//i.test(value) ? value : "";
const formatNumber = value => Number(value || 0).toLocaleString("ko-KR");
const gradeTitles = {A: "주요 종합지·경제지·통신사", B: "중견 경제지·전문지·방송사", C: "기타매체"};

function formatShortDate(dateString) {
  if (!dateString) return "";
  const match = String(dateString).match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return dateString;
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (!month || month > 12 || !day || day > 31) return dateString;
  return `'${match[1].slice(-2)}.${month}.${day}.`;
}

function formatReportTitle(baseDate, slot) {
  const slotLabel = {morning: "Morning Report", evening: "Evening Report", night: "Night Report"}[slot] || "Morning Report";
  return `${formatShortDate(baseDate)} ${slotLabel}`;
}

function formatShortDateTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hour12: false
  }).formatToParts(date);
  const map = Object.fromEntries(parts.map(part => [part.type, part.value]));
  return `'${map.year.slice(-2)}.${Number(map.month)}.${Number(map.day)}. ${map.hour}:${map.minute}`;
}

function getGradeCount(reportData, grade) {
  return Number(reportData?.grade_counts?.[grade] ?? groupArticlesByGradeAndSource(reportData?.articles || [])[grade].length);
}

function getTotalCount(reportData) {
  return Number(reportData?.total_deduped_count ?? reportData?.articles?.length ?? 0);
}

function getDailySummary(loadedReports) {
  if (!loadedReports.some(({meta, data}) => (data?.slot || meta?.slot) === "night")) return null;
  return loadedReports.reduce((summary, {data}) => {
    summary.total += getTotalCount(data);
    for (const grade of "ABC") summary[grade] += getGradeCount(data, grade);
    return summary;
  }, {total: 0, A: 0, B: 0, C: 0});
}

function renderDailySummary(loadedReports) {
  const summary = getDailySummary(loadedReports);
  if (!summary) return "";
  return `<span class="daily-summary">(총 ${formatNumber(summary.total)}건, A ${formatNumber(summary.A)}건, B ${formatNumber(summary.B)}건, C ${formatNumber(summary.C)}건)</span>`;
}

function renderGradeSummary(reportData) {
  return `<div class="grade-summary">총 ${formatNumber(getTotalCount(reportData))}건, A ${formatNumber(getGradeCount(reportData, "A"))}건, B ${formatNumber(getGradeCount(reportData, "B"))}건, C ${formatNumber(getGradeCount(reportData, "C"))}건</div>
    <div class="grade-caption"><div>A: ${gradeTitles.A}</div><div>B: ${gradeTitles.B}</div><div>C: ${gradeTitles.C}</div></div>`;
}

function getTodayKSTDateString() {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit"
  }).format(new Date());
}

function renderReportSummary(reportData) {
  const summary = reportData?.summary;
  if (!summary) return "";
  const lines = Array.isArray(summary) ? summary : [summary];
  return `<section class="report-summary"><strong>요약</strong>${lines.map(line => `<p>${escapeHTML(line)}</p>`).join("")}</section>`;
}

async function fetchJSON(path) {
  const response = await fetch(path, {cache: "no-store"});
  if (!response.ok) throw new Error(`${path}을(를) 불러오지 못했습니다. (${response.status})`);
  return response.json();
}

function isReportPath(path) {
  return /^data\/reports\/[0-9]{4}-[0-9]{2}-[0-9]{2}-(morning|evening|night)\.json$/.test(path || "");
}

async function loadReportByPath(jsonPath) {
  if (!isReportPath(jsonPath)) throw new Error(`올바르지 않은 리포트 경로입니다: ${jsonPath || "(없음)"}`);
  return fetchJSON(jsonPath);
}

async function loadReportIndex() {
  const index = await fetchJSON("data/report-index.json");
  state.reportIndex = Array.isArray(index) ? index : [];
}

function sortReportsBySlotPriority(a, b) {
  const priority = {morning: 0, evening: 1, night: 2};
  return (priority[a.slot] ?? 9) - (priority[b.slot] ?? 9);
}

function getReportsByDate(baseDate) {
  return state.reportIndex
    .filter(item => item.base_date === baseDate)
    .sort(sortReportsBySlotPriority);
}

function renderArticle(article) {
  const link = safeURL(article.url || article.canonical_url);
  const title = escapeHTML(article.title || "제목 없음");
  const titleMarkup = link
    ? `<a class="article-link" href="${escapeHTML(link)}" target="_blank" rel="noopener noreferrer">${title}</a>`
    : `<span class="article-link">${title}</span>`;
  const snippet = article.snippet ? `<details class="snippet"><summary>검색 결과 문맥 보기</summary><p>${escapeHTML(article.snippet)}</p></details>` : "";
  return `<li class="article-item"><div class="article-main">${titleMarkup}${snippet}</div></li>`;
}

function renderArticlesBySource(articles) {
  if (!articles.length) return `<p class="quiet-message grade-empty">표시할 기사가 없습니다.</p>`;
  const media = new Map();
  articles.forEach(article => {
    const source = article.source_normalized || article.source || "매체 미상";
    if (!media.has(source)) media.set(source, []);
    media.get(source).push(article);
  });
  return [...media.entries()].map(([source, items]) =>
    `<article class="media-card"><h4 class="media-title">${escapeHTML(source)}<span>${formatNumber(items.length)}건</span></h4><ul class="article-list">${items.map(renderArticle).join("")}</ul></article>`
  ).join("");
}

function groupArticlesByGradeAndSource(articles) {
  return (articles || []).reduce((groups, article) => {
    const grade = ["A", "B", "C"].includes(article.grade) ? article.grade : "C";
    groups[grade].push(article);
    return groups;
  }, {A: [], B: [], C: []});
}

function renderGradeSection(grade, title, articles) {
  const collapsible = grade !== "A";
  return `<section class="grade-section grade-${grade.toLowerCase()} ${collapsible ? "is-collapsed" : "is-open"}">
    <div class="grade-header"><div><span class="badge grade-mark grade-mark-${grade.toLowerCase()}">${grade}</span><h3>${escapeHTML(title)}</h3></div><span class="grade-count">${formatNumber(articles.length)}건</span></div>
    ${collapsible ? `<button class="grade-toggle-btn" type="button" data-toggle-grade="${grade}" aria-expanded="false">${escapeHTML(title)} 보기</button>` : ""}
    <div class="grade-body" ${collapsible ? "hidden" : ""}>${renderArticlesBySource(articles)}</div>
  </section>`;
}

function renderSingleReportBody(reportData) {
  const articles = reportData.articles || [];
  const grouped = groupArticlesByGradeAndSource(articles);
  return `${renderReportSummary(reportData)}${renderGradeSection("A", gradeTitles.A, grouped.A)}
    ${renderGradeSection("B", gradeTitles.B, grouped.B)}
    ${renderGradeSection("C", gradeTitles.C, grouped.C)}`;
}

function formatReportPeriod(reportData, meta) {
  const start = reportData.period_start || meta.period_start;
  const end = reportData.period_end || meta.period_end;
  return start && end ? `${formatShortDateTime(start)} ~ ${formatShortDateTime(end)}` : "";
}

function renderReportAccordionItem(meta, reportData, openByDefault = false) {
  const bodyId = `report-accordion-${escapeHTML(meta.base_date)}-${escapeHTML(meta.slot)}`;
  return `<article class="report-accordion-item ${openByDefault ? "is-open" : ""}" data-report-slot="${escapeHTML(meta.slot)}">
    <button type="button" class="report-accordion-header" data-toggle-report="${escapeHTML(meta.slot)}" aria-expanded="${openByDefault}" aria-controls="${bodyId}">
      <div class="accordion-title"><strong class="report-title">${escapeHTML(formatReportTitle(reportData.base_date || meta.base_date, meta.slot))}</strong>${renderGradeSummary(reportData)}</div>
      <small class="report-meta">${escapeHTML(formatReportPeriod(reportData, meta))}</small>
      <span class="accordion-arrow">${openByDefault ? "숨기기" : "펼치기"}</span>
    </button>
    <div id="${bodyId}" class="report-accordion-body" ${openByDefault ? "" : "hidden"}>${renderSingleReportBody(reportData)}</div>
  </article>`;
}

function bindReportAccordionEvents() {
  $("#report-root").querySelectorAll("[data-toggle-report]").forEach(button => {
    button.addEventListener("click", () => {
      const item = button.closest(".report-accordion-item");
      const body = item.querySelector(".report-accordion-body");
      const willOpen = body.hidden;
      body.hidden = !willOpen;
      item.classList.toggle("is-open", willOpen);
      button.setAttribute("aria-expanded", String(willOpen));
      item.querySelector(".accordion-arrow").textContent = willOpen ? "숨기기" : "펼치기";
    });
  });
}

function bindGradeToggleEvents() {
  $("#report-root").querySelectorAll("[data-toggle-grade]").forEach(button => {
    button.addEventListener("click", () => {
      const section = button.closest(".grade-section");
      const body = section.querySelector(".grade-body");
      const grade = button.dataset.toggleGrade;
      const willOpen = body.hidden;
      body.hidden = !willOpen;
      section.classList.toggle("is-open", willOpen);
      section.classList.toggle("is-collapsed", !willOpen);
      button.setAttribute("aria-expanded", String(willOpen));
      button.textContent = `${gradeTitles[grade]} ${willOpen ? "숨기기" : "보기"}`;
    });
  });
}

function bindReturnTodayButton() {
  document.querySelectorAll("[data-return-today]").forEach(button => button.addEventListener("click", showTodayReport));
}

function renderDateReportsAccordion(baseDate, loadedReports, mode, preferredSlot = null) {
  const root = $("#report-root");
  if (!loadedReports.length) {
    root.innerHTML = `<section class="empty-report-card"><h2>${escapeHTML(formatShortDate(baseDate))}</h2><p>${baseDate === state.today ? "오늘 생성된 리포트가 아직 없습니다." : "해당 날짜의 리포트가 없습니다."}</p>${mode === "past" ? `<button class="return-today-btn" type="button" data-return-today>오늘 기사 보기</button>` : ""}</section>`;
    bindReturnTodayButton();
    return;
  }
  const latestSlot = loadedReports.some(item => item.meta.slot === "night") ? "night" : loadedReports.some(item => item.meta.slot === "evening") ? "evening" : "morning";
  const openSlot = preferredSlot || (mode === "today" ? latestSlot : null);
  const items = loadedReports
    .sort((a, b) => sortReportsBySlotPriority(a.meta, b.meta))
    .map(({meta, data}) => renderReportAccordionItem(meta, data, meta.slot === openSlot))
    .join("");
  root.innerHTML = `<section class="selected-date-report">
    <div class="selected-date-header"><div><p class="eyebrow dark">FULL COVERAGE</p><div class="selected-date-title"><h2>${escapeHTML(formatShortDate(baseDate))}</h2>${renderDailySummary(loadedReports)}</div></div>${mode === "past" ? `<button class="return-today-btn" type="button" data-return-today>오늘 기사 보기</button>` : ""}</div>
    ${items}
  </section>`;
  bindReportAccordionEvents();
  bindGradeToggleEvents();
  bindReturnTodayButton();
}

function markSelectedCalendarDate(baseDate) {
  state.selectedDate = baseDate;
  renderCalendar($("#calendar-grid"), buildCalendar(state.currentYear, state.currentMonth));
}

async function loadAndRenderDate(baseDate, {scroll = false, preferredSlot = null} = {}) {
  const reports = getReportsByDate(baseDate);
  state.selectedDate = baseDate;
  state.viewingMode = baseDate === state.today ? "today" : "past";
  markSelectedCalendarDate(baseDate);
  const results = await Promise.allSettled(reports.map(async meta => ({meta, data: await loadReportByPath(meta.json_path)})));
  const loadedReports = results.filter(result => result.status === "fulfilled").map(result => result.value);
  results.filter(result => result.status === "rejected").forEach(result => console.error("[F-Issue] failed to load report:", result.reason));
  state.loadedReports = loadedReports;
  renderDateReportsAccordion(baseDate, loadedReports, state.viewingMode, preferredSlot);
  $("#loading").hidden = true;
  $("#error-panel").hidden = true;
  $("#dashboard").hidden = false;
  if (scroll) $("#report-root").scrollIntoView({behavior: "smooth", block: "start"});
}

async function onCalendarDateClick(baseDate) {
  try {
    await loadAndRenderDate(baseDate, {scroll: true});
  } catch (error) {
    showError(error);
  }
}

function buildCalendar(year, month) {
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const reportsByDate = {};
  state.reportIndex.forEach(report => {
    if (!reportsByDate[report.base_date]) reportsByDate[report.base_date] = [];
    reportsByDate[report.base_date].push(report);
  });
  const days = Array(firstDay).fill(null);
  for (let day = 1; day <= daysInMonth; day += 1) {
    const date = `${year}-${String(month + 1).padStart(2,"0")}-${String(day).padStart(2,"0")}`;
    days.push({day, date, reports: reportsByDate[date] || []});
  }
  while (days.length % 7) days.push(null);
  return {year, month, days};
}

function renderCalendar(container, calendarData) {
  $("#calendar-month").textContent = `${calendarData.year}년 ${calendarData.month + 1}월`;
  const weekdays = ["일", "월", "화", "수", "목", "금", "토"].map(day => `<div class="calendar-weekday" role="columnheader">${day}</div>`).join("");
  const days = calendarData.days.map(item => {
    if (!item) return `<div class="calendar-day empty" role="gridcell"></div>`;
    const morning = item.reports.find(report => report.slot === "morning");
    const evening = item.reports.find(report => report.slot === "evening");
    const night = item.reports.find(report => report.slot === "night");
    const total = item.reports.reduce((sum, report) => sum + Number(report.total_deduped_count || 0), 0);
    const classes = ["calendar-day", item.reports.length ? "has-report" : "", item.date === state.today ? "today" : "", item.date === state.selectedDate ? "selected" : ""].filter(Boolean).join(" ");
    const badges = item.reports.length ? `<span class="calendar-badges">${morning ? `<span class="calendar-badge morning">M</span>` : ""}${evening ? `<span class="calendar-badge evening">E</span>` : ""}${night ? `<span class="calendar-badge night">N</span>` : ""}</span><span class="calendar-count">${formatNumber(total)}건</span>` : "";
    return `<button class="${classes}" type="button" role="gridcell" data-calendar-date="${item.date}" aria-pressed="${item.date === state.selectedDate}" aria-label="${item.date}, ${item.reports.length ? `리포트 ${item.reports.length}개` : "리포트 없음"}"><span class="day-number">${item.day}</span>${badges}</button>`;
  }).join("");
  container.innerHTML = weekdays + days;
  container.querySelectorAll("[data-calendar-date]").forEach(button => button.addEventListener("click", () => onCalendarDateClick(button.dataset.calendarDate)));
}

async function showTodayReport() {
  state.today = getTodayKSTDateString();
  const [year, month] = state.today.split("-").map(Number);
  state.currentYear = year;
  state.currentMonth = month - 1;
  await loadAndRenderDate(state.today, {scroll: true});
}

function goToPreviousMonth() {
  state.currentMonth -= 1;
  if (state.currentMonth < 0) { state.currentMonth = 11; state.currentYear -= 1; }
  renderCalendar($("#calendar-grid"), buildCalendar(state.currentYear, state.currentMonth));
}

function goToNextMonth() {
  state.currentMonth += 1;
  if (state.currentMonth > 11) { state.currentMonth = 0; state.currentYear += 1; }
  renderCalendar($("#calendar-grid"), buildCalendar(state.currentYear, state.currentMonth));
}

function goToCurrentMonth() {
  const [year, month] = state.today.split("-").map(Number);
  state.currentYear = year;
  state.currentMonth = month - 1;
  renderCalendar($("#calendar-grid"), buildCalendar(state.currentYear, state.currentMonth));
}

function showError(error) {
  $("#loading").hidden = true;
  $("#error-panel").hidden = false;
  $("#error-panel").innerHTML = `<strong>리포트를 표시하지 못했습니다.</strong><p>${escapeHTML(error.message || error)}</p>`;
}

async function initDashboard() {
  try {
    await loadReportIndex();
    state.today = getTodayKSTDateString();
    const requestedPath = new URLSearchParams(location.search).get("report");
    const requestedReport = isReportPath(requestedPath)
      ? state.reportIndex.find(item => item.json_path === requestedPath)
      : null;
    const initialDate = requestedReport?.base_date || state.today;
    const [year, month] = initialDate.split("-").map(Number);
    state.currentYear = year;
    state.currentMonth = month - 1;
    await loadAndRenderDate(initialDate, {preferredSlot: requestedReport?.slot || null});
  } catch (error) {
    showError(error);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  $("#refresh-button").addEventListener("click", () => location.reload());
  $("#calendar-prev").addEventListener("click", goToPreviousMonth);
  $("#calendar-next").addEventListener("click", goToNextMonth);
  $("#calendar-today").addEventListener("click", goToCurrentMonth);
  initDashboard();
});
