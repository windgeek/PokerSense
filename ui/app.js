// PokerSense companion panel. Language follows the local system on first run
// and is persisted when the player changes it in Settings.

const SUIT_SYMBOL = { s: "♠", h: "♥", d: "♦", c: "♣" };
const RED_SUITS = new Set(["h", "d"]);
const LANGUAGE_STORAGE_KEY = "pokersense.language";
const FIELD_ORDER = ["hero_cards", "board_cards", "street", "pot", "stacks", "bet_size", "action"];
const TRANSLATIONS = {
  en: {
    board: "Board", hero: "Hero", pot: "Pot", winRate: "Win Rate", settings: "Settings",
    language: "Language", languageAuto: "System default", languageHint: "Changes are saved automatically.",
    close: "Close", notCalibrated: "not calibrated", confidence: "confidence", tie: "tie",
    frame: "frame", noData: "no data", live: "PokerSense · live", connecting: "PokerSense · connecting",
    cannotReach: "PokerSense · cannot reach engine", waiting: "PokerSense · waiting for table",
    connectionError: "PokerSense · connection error", disconnected: "PokerSense · engine disconnected, reconnecting",
    fields: { hero_cards: "Hero", board_cards: "Board", street: "Street", pot: "Pot", stacks: "Stacks", bet_size: "Bet", action: "Action" },
  },
  zh: {
    board: "公共牌", hero: "底牌", pot: "底池", winRate: "胜率", settings: "设置",
    language: "语言", languageAuto: "跟随系统", languageHint: "更改会自动保存。",
    close: "关闭", notCalibrated: "尚未标定", confidence: "置信度", tie: "平局",
    frame: "帧", noData: "暂无数据", live: "PokerSense · 已连接", connecting: "PokerSense · 正在连接",
    cannotReach: "PokerSense · 无法连接引擎", waiting: "PokerSense · 等待牌桌",
    connectionError: "PokerSense · 连接错误", disconnected: "PokerSense · 引擎已断开，正在重连",
    fields: { hero_cards: "底牌", board_cards: "公共牌", street: "街道", pot: "底池", stacks: "筹码", bet_size: "下注", action: "行动" },
  },
};

const els = {
  connDot: document.getElementById("conn-dot"), connLabel: document.getElementById("conn-label"),
  streetBadge: document.getElementById("street-badge"), boardSlots: document.getElementById("board-slots"),
  heroSlots: document.getElementById("hero-slots"), potValue: document.getElementById("pot-value"),
  winRate: document.getElementById("win-rate"), tieRate: document.getElementById("tie-rate"),
  segWin: document.getElementById("seg-win"), segTie: document.getElementById("seg-tie"),
  equityBar: document.querySelector(".equity-bar"), confidenceBadge: document.getElementById("confidence-badge"),
  confidenceValue: document.getElementById("confidence-value"), confidenceFields: document.getElementById("confidence-fields"),
  footerLeft: document.getElementById("footer-left"), footerRight: document.getElementById("footer-right"),
  settingsButton: document.getElementById("settings-button"), settingsDialog: document.getElementById("settings-dialog"),
  settingsClose: document.getElementById("settings-close"), languageSelect: document.getElementById("language-select"),
};

let lastBoardCount = 0;
let lastAnalysis = null;
let status = { message: "connecting", tone: "", raw: false };

function systemLanguage() {
  const locale = (navigator.languages && navigator.languages[0]) || navigator.language || "en";
  return locale.toLowerCase().startsWith("zh") ? "zh" : "en";
}

function languagePreference() {
  const value = localStorage.getItem(LANGUAGE_STORAGE_KEY) || "auto";
  return ["auto", "en", "zh"].includes(value) ? value : "auto";
}

function activeLanguage() {
  const value = languagePreference();
  return value === "auto" ? systemLanguage() : value;
}

function t(key) { return TRANSLATIONS[activeLanguage()][key] || key; }

function applyLanguage() {
  document.documentElement.lang = activeLanguage() === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-i18n]").forEach((node) => { node.textContent = t(node.dataset.i18n); });
  els.settingsButton.setAttribute("aria-label", t("settings"));
  els.settingsClose.setAttribute("aria-label", t("close"));
  els.languageSelect.value = languagePreference();
  if (lastAnalysis) render(lastAnalysis); else renderEmpty();
  showStatus(status.message, status.tone, status.raw);
}

function makeCardEl(code, isNew) {
  const el = document.createElement("div");
  if (!code) { el.className = "card empty"; return el; }
  const rank = code.slice(0, -1);
  const suit = code.slice(-1);
  el.className = "card " + (RED_SUITS.has(suit) ? "red" : "black") + (isNew ? " new-card" : "");
  const rankEl = document.createElement("div"); rankEl.textContent = rank;
  const suitEl = document.createElement("div"); suitEl.className = "suit"; suitEl.textContent = SUIT_SYMBOL[suit] || suit;
  el.append(rankEl, suitEl);
  return el;
}

function renderCardSlots(container, cards, slotCount, animateFromIndex) {
  container.innerHTML = "";
  for (let i = 0; i < slotCount; i++) {
    const code = cards[i] || null;
    container.appendChild(makeCardEl(code, animateFromIndex !== undefined && i >= animateFromIndex && code));
  }
}

function statusOf(analysis, field) {
  const entry = (analysis.confidence.field_status || []).find((item) => item[0] === field);
  return entry ? entry[1] : "unknown";
}

function renderFieldStatuses(statuses) {
  els.confidenceFields.innerHTML = "";
  for (const field of FIELD_ORDER) {
    const dot = document.createElement("span");
    dot.className = "field-dot";
    dot.title = `${TRANSLATIONS[activeLanguage()].fields[field]}: ${statuses[field] || t("noData")}`;
    dot.dataset.status = statuses[field] || "unknown";
    els.confidenceFields.appendChild(dot);
  }
}

function render(analysis) {
  lastAnalysis = analysis;
  showStatus("live", "live");
  const state = analysis.state;
  els.streetBadge.textContent = statusOf(analysis, "street") === "valid" ? state.street : "—";
  renderCardSlots(els.boardSlots, state.board_cards, 5, lastBoardCount);
  lastBoardCount = state.board_cards.length;
  renderCardSlots(els.heroSlots, state.hero_cards, 2);
  const potKnown = statusOf(analysis, "pot") === "valid";
  els.potValue.classList.toggle("unknown", !potKnown);
  els.potValue.replaceChildren();
  if (potKnown) {
    els.potValue.append(document.createTextNode(state.pot));
    const unit = document.createElement("span"); unit.className = "unit"; unit.textContent = "bb";
    els.potValue.append(unit);
  } else els.potValue.textContent = t("notCalibrated");
  const winPct = analysis.equity.win_rate * 100;
  const tiePct = analysis.equity.tie_rate * 100;
  els.equityBar.classList.remove("idle");
  els.winRate.textContent = `${winPct.toFixed(1)}%`;
  els.winRate.className = "win " + (analysis.equity.win_rate >= 0.55 ? "" : analysis.equity.win_rate >= 0.35 ? "mid" : "low");
  els.tieRate.textContent = `${t("tie")} ${tiePct.toFixed(1)}%`;
  els.segWin.style.width = `${winPct}%`; els.segTie.style.width = `${tiePct}%`;
  const confidence = analysis.confidence.overall_confidence;
  els.confidenceValue.textContent = `${t("confidence")} ${(confidence * 100).toFixed(0)}%`;
  els.confidenceBadge.style.background = confidence >= 0.9 ? "var(--good)" : confidence >= 0.6 ? "var(--warn)" : "var(--bad)";
  renderFieldStatuses(Object.fromEntries(analysis.confidence.field_status));
  els.footerLeft.textContent = `${t("frame")} ${analysis.frame_seq}`;
  els.footerRight.textContent = new Date().toLocaleTimeString(activeLanguage() === "zh" ? "zh-CN" : "en");
}

function renderEmpty() {
  renderCardSlots(els.boardSlots, [], 5); renderCardSlots(els.heroSlots, [], 2);
  els.streetBadge.textContent = "—"; els.potValue.textContent = "—"; els.potValue.classList.add("unknown");
  els.winRate.textContent = "—"; els.winRate.className = "win idle"; els.tieRate.textContent = `${t("tie")} —`;
  els.segWin.style.width = "0%"; els.segTie.style.width = "0%"; els.equityBar.classList.add("idle");
  els.confidenceValue.textContent = `${t("confidence")} —`; els.confidenceBadge.style.background = "var(--text-faint)";
  renderFieldStatuses({}); els.footerLeft.textContent = `${t("frame")} —`; els.footerRight.textContent = "—";
}

function showStatus(message, tone, raw = false) {
  status = { message, tone, raw };
  els.connDot.className = "dot " + (tone || "");
  els.connLabel.textContent = raw ? message : t(message);
}

function connect() {
  const url = (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws";
  showStatus("connecting", "");
  let socket;
  try { socket = new WebSocket(url); } catch (_) { showStatus("cannotReach", "error"); return; }
  socket.onopen = () => showStatus("waiting", "");
  socket.onmessage = (event) => {
    let payload; try { payload = JSON.parse(event.data); } catch (_) { return; }
    if (payload.error) { showStatus(payload.error, "error", true); return; }
    render(payload);
  };
  socket.onerror = () => showStatus("connectionError", "error");
  socket.onclose = () => { showStatus("disconnected", "error"); setTimeout(connect, 3000); };
}

els.settingsButton.addEventListener("click", () => els.settingsDialog.showModal());
els.languageSelect.addEventListener("change", () => {
  localStorage.setItem(LANGUAGE_STORAGE_KEY, els.languageSelect.value);
  applyLanguage();
});

applyLanguage();
connect();
