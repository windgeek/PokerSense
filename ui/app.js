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

function equityTier(rate) {
  if (rate >= 0.55) return "";
  if (rate >= 0.35) return "mid";
  return "low";
}

function render(analysis, mode) {
  els.connDot.className = "dot " + (mode === "live" ? "live" : "demo");
  els.connLabel.textContent = mode === "live" ? "PokerSense" : "PokerSense · demo data";

  const state = analysis.state;
  els.streetBadge.textContent = state.street;

  renderCardSlots(els.boardSlots, state.board_cards, 5, lastBoardCount);
  lastBoardCount = state.board_cards.length;
  renderCardSlots(els.heroSlots, state.hero_cards, 2);

  els.potValue.innerHTML = `${state.pot}<span class="unit">bb</span>`;

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

// --- demo fallback: a scripted preflop -> river hand, looping ---

const DEMO_SEQUENCE = [
  {
    frame_seq: 1,
    state: { street: "preflop", hero_cards: ["Ah", "Kh"], board_cards: [], pot: "1.5" },
    equity: { win_rate: 0.64, tie_rate: 0.02 },
    confidence: {
      overall_confidence: 0.98,
      field_status: [
        ["hero_cards", "valid"], ["board_cards", "valid"], ["street", "valid"],
        ["pot", "valid"], ["stacks", "valid"], ["bet_size", "valid"], ["action", "valid"],
      ],
    },
  },
  {
    frame_seq: 2,
    state: { street: "flop", hero_cards: ["Ah", "Kh"], board_cards: ["Qh", "9h", "2c"], pot: "6" },
    equity: { win_rate: 0.71, tie_rate: 0.01 },
    confidence: {
      overall_confidence: 0.95,
      field_status: [
        ["hero_cards", "valid"], ["board_cards", "valid"], ["street", "valid"],
        ["pot", "valid"], ["stacks", "valid"], ["bet_size", "low_confidence"], ["action", "valid"],
      ],
    },
  },
  {
    frame_seq: 3,
    state: { street: "turn", hero_cards: ["Ah", "Kh"], board_cards: ["Qh", "9h", "2c", "5h"], pot: "18" },
    equity: { win_rate: 0.86, tie_rate: 0.01 },
    confidence: {
      overall_confidence: 0.97,
      field_status: [
        ["hero_cards", "valid"], ["board_cards", "valid"], ["street", "valid"],
        ["pot", "valid"], ["stacks", "valid"], ["bet_size", "valid"], ["action", "valid"],
      ],
    },
  },
  {
    frame_seq: 4,
    state: { street: "river", hero_cards: ["Ah", "Kh"], board_cards: ["Qh", "9h", "2c", "5h", "7s"], pot: "42" },
    equity: { win_rate: 0.91, tie_rate: 0.0 },
    confidence: {
      overall_confidence: 0.6,
      field_status: [
        ["hero_cards", "valid"], ["board_cards", "conflict"], ["street", "valid"],
        ["pot", "valid"], ["stacks", "unknown"], ["bet_size", "valid"], ["action", "valid"],
      ],
    },
  },
];

let demoStarted = false;

function startDemoLoop() {
  if (demoStarted) return;
  demoStarted = true;
  lastBoardCount = 0;
  let i = 0;
  render(DEMO_SEQUENCE[0], "demo");
  setInterval(() => {
    i = (i + 1) % DEMO_SEQUENCE.length;
    if (i === 0) lastBoardCount = 0;
    render(DEMO_SEQUENCE[i], "demo");
  }, 3200);
}

// --- live connection ---

function connect() {
  const url = (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws";
  let socket;
  try {
    socket = new WebSocket(url);
  } catch (e) {
    startDemoLoop();
    return;
  }

  const fallbackTimer = setTimeout(startDemoLoop, 800);

  socket.onopen = () => clearTimeout(fallbackTimer);
  socket.onmessage = (event) => {
    clearTimeout(fallbackTimer);
    try {
      const analysis = JSON.parse(event.data);
      render(analysis, "live");
    } catch (e) {
      // ignore malformed frame
    }
  };
  socket.onerror = () => {
    clearTimeout(fallbackTimer);
  };
  socket.onclose = () => {
    startDemoLoop();
  };
}

connect();
