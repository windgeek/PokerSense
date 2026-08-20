// PokerSense companion panel.
//
// Renders whatever RealtimeAnalysis-shaped JSON it receives, either from a
// live WebSocket (real backend) or, when that connection isn't available,
// from a local scripted demo sequence -- so this file always shows *something
// real running*, never a blank screen, whether or not the engine backend is
// up. The wire contract is defined once here and must match
// `poker_engine.desktop.serialize.analysis_to_dict`.

const SUIT_SYMBOL = { s: "♠", h: "♥", d: "♦", c: "♣" };
const RED_SUITS = new Set(["h", "d"]);

const FIELD_ORDER = [
  ["hero_cards", "Hero"],
  ["board_cards", "Board"],
  ["street", "Street"],
  ["pot", "Pot"],
  ["stacks", "Stacks"],
  ["bet_size", "Bet"],
  ["action", "Action"],
];

const els = {
  connDot: document.getElementById("conn-dot"),
  connLabel: document.getElementById("conn-label"),
  streetBadge: document.getElementById("street-badge"),
  boardSlots: document.getElementById("board-slots"),
  heroSlots: document.getElementById("hero-slots"),
  potValue: document.getElementById("pot-value"),
  winRate: document.getElementById("win-rate"),
  tieRate: document.getElementById("tie-rate"),
  segWin: document.getElementById("seg-win"),
  segTie: document.getElementById("seg-tie"),
  equityBar: document.querySelector(".equity-bar"),
  confidenceBadge: document.getElementById("confidence-badge"),
  confidenceValue: document.getElementById("confidence-value"),
  confidenceFields: document.getElementById("confidence-fields"),
  footerLeft: document.getElementById("footer-left"),
  footerRight: document.getElementById("footer-right"),
};

let lastBoardCount = 0;

function makeCardEl(code, isNew) {
  const el = document.createElement("div");
  if (!code) {
    el.className = "card empty";
    return el;
  }
  const rank = code.slice(0, -1);
  const suit = code.slice(-1);
  el.className = "card " + (RED_SUITS.has(suit) ? "red" : "black") + (isNew ? " new-card" : "");
  const rankEl = document.createElement("div");
  rankEl.textContent = rank;
  const suitEl = document.createElement("div");
  suitEl.className = "suit";
  suitEl.textContent = SUIT_SYMBOL[suit] || suit;
  el.appendChild(rankEl);
  el.appendChild(suitEl);
  return el;
}

function renderCardSlots(container, cards, slotCount, animateFromIndex) {
  container.innerHTML = "";
  for (let i = 0; i < slotCount; i++) {
    const code = cards[i] || null;
    const isNew = animateFromIndex !== undefined && i >= animateFromIndex && code;
    container.appendChild(makeCardEl(code, isNew));
  }
}

function statusOf(analysis, field) {
  const entry = (analysis.confidence.field_status || []).find((e) => e[0] === field);
  return entry ? entry[1] : "unknown";
}

function equityTier(rate) {
  if (rate >= 0.55) return "";
  if (rate >= 0.35) return "mid";
  return "low";
}

function render(analysis) {
  els.connDot.className = "dot live";
  els.connLabel.textContent = "PokerSense";

  const state = analysis.state;
  els.streetBadge.textContent =
    statusOf(analysis, "street") === "valid" ? state.street : "—";

  renderCardSlots(els.boardSlots, state.board_cards, 5, lastBoardCount);
  lastBoardCount = state.board_cards.length;
  renderCardSlots(els.heroSlots, state.hero_cards, 2);

  const potKnown = statusOf(analysis, "pot") === "valid";
  els.potValue.innerHTML = potKnown
    ? `${state.pot}<span class="unit">bb</span>`
    : '<span class="unknown">not calibrated</span>';

  els.equityBar.classList.remove("idle");
  const winPct = analysis.equity.win_rate * 100;
  const tiePct = analysis.equity.tie_rate * 100;
  els.winRate.textContent = winPct.toFixed(1) + "%";
  els.winRate.className = "win " + equityTier(analysis.equity.win_rate);
  els.tieRate.textContent = "tie " + tiePct.toFixed(1) + "%";
  els.segWin.style.width = winPct + "%";
  els.segTie.style.width = tiePct + "%";

  const conf = analysis.confidence.overall_confidence;
  els.confidenceValue.textContent = "confidence " + (conf * 100).toFixed(0) + "%";
  els.confidenceBadge.style.background =
    conf >= 0.9 ? "var(--good)" : conf >= 0.6 ? "var(--warn)" : "var(--bad)";

  const statusByField = Object.fromEntries(analysis.confidence.field_status);
  els.confidenceFields.innerHTML = "";
  for (const [field, label] of FIELD_ORDER) {
    const dot = document.createElement("span");
    dot.className = "field-dot";
    dot.title = `${label}: ${statusByField[field] || "unknown"}`;
    dot.dataset.status = statusByField[field] || "unknown";
    els.confidenceFields.appendChild(dot);
  }

  els.footerLeft.textContent = "frame " + analysis.frame_seq;
  els.footerRight.textContent = new Date().toLocaleTimeString();
}

// --- empty state ---

function renderEmpty() {
  renderCardSlots(els.boardSlots, [], 5);
  renderCardSlots(els.heroSlots, [], 2);
  els.streetBadge.textContent = "—";
  els.potValue.innerHTML = '<span class="unknown">—</span>';
  els.winRate.textContent = "—";
  els.winRate.className = "win idle";
  els.tieRate.textContent = "tie —";
  els.segWin.style.width = "0%";
  els.segTie.style.width = "0%";
  els.equityBar.classList.add("idle");
  els.confidenceValue.textContent = "confidence —";
  els.confidenceBadge.style.background = "var(--text-faint)";
  els.confidenceFields.innerHTML = "";
  for (const [field, label] of FIELD_ORDER) {
    const dot = document.createElement("span");
    dot.className = "field-dot";
    dot.title = `${label}: no data`;
    dot.dataset.status = "unknown";
    els.confidenceFields.appendChild(dot);
  }
  els.footerLeft.textContent = "frame —";
  els.footerRight.textContent = "—";
}

// --- connection status ---

function showStatus(message, tone) {
  els.connDot.className = "dot " + (tone || "");
  els.connLabel.textContent = message;
}

// --- live connection ---

function connect() {
  const url = (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws";
  showStatus("PokerSense · connecting", "");

  let socket;
  try {
    socket = new WebSocket(url);
  } catch (e) {
    showStatus("PokerSense · cannot reach engine", "error");
    return;
  }

  socket.onopen = () => showStatus("PokerSense · waiting for table", "");

  socket.onmessage = (event) => {
    let payload;
    try {
      payload = JSON.parse(event.data);
    } catch (e) {
      return; // ignore malformed frame
    }
    if (payload.error) {
      showStatus(payload.error, "error");
      return;
    }
    render(payload);
  };

  socket.onerror = () => showStatus("PokerSense · connection error", "error");

  socket.onclose = () => {
    showStatus("PokerSense · engine disconnected, reconnecting", "error");
    setTimeout(connect, 3000);
  };
}

renderEmpty();
connect();
