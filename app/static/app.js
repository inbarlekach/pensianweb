"use strict";

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const ils = (x) => `₪${Math.round(x).toLocaleString("he-IL")}`;
const pct = (x) => `${Number(x).toFixed(2)}%`;
const N = (s) => `<span class="num">${s}</span>`;
const period = (p) => (p ? `${String(p).slice(4)}/${String(p).slice(0, 4)}` : "—");
const dateHe = (iso) => (iso ? new Date(iso).toLocaleDateString("he-IL") : "—");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const fmtCalc = (c) => (c.unit === "ILS" ? ils(c.value) : pct(c.value));

const CERT = { 1: ["ודאות: מידע מאומת", "pill-emerald"], 2: ["ודאות: אינדיקציה – בדיקה נדרשת", "pill-amber"], 3: ["ודאות: אין די מידע", "pill-danger"] };
const RISK = { low: ["סיכון נמוך", "pill-emerald"], high: ["סיכון גבוה יותר", "pill-amber"] };
const SUB = { entry: "כניסה", profile: "פרופיל", results: "תוצאות וניתוח", survey: "שאלון משוב" };
const GLOSSARY = [
  ["דמי ניהול מהפקדות", "אחוז שהקרן גובה מכל הפקדה חודשית, לפני שהכסף נכנס לחיסכון. למשל, 2% מהפקדה של 1,000 ₪ הם 20 ₪."],
  ["דמי ניהול מצבירה", "אחוז שנתי שהקרן גובה מכל הכסף שכבר נצבר. מכיוון שהצבירה גדלה עם השנים, השפעתו בטווח הארוך גדולה במיוחד."],
  ["קרן פנסיה חדשה מקיפה", "המוצר העיקרי לחיסכון פנסיוני של שכירים בישראל. משלבת חיסכון לקצבה עם ביטוח לנכות ולשארים."],
  ["ממוצע שנגבה בפועל", "דמי הניהול הממוצעים שהקרן גבתה מכלל העמיתים שלה. זה לא מחיר שמוצע לך. חוסכים שונים משלמים שיעורים שונים."],
  ["תשואה ריאלית", "תשואה אחרי ניכוי אינפלציה. הסכומים מוצגים בכוח הקנייה של היום."],
  ["פנסיה-נט", "מאגר נתונים ציבורי של רשות שוק ההון על קרנות הפנסיה: דמי ניהול ממוצעים, נכסים ותשואות."],
];
const SURVEY_DEFAULTS = { q1: "new", q2: "4", q3: "yes", q3a: ["fund", "advisor"], q4: "4", q5: "רציתי לדעת מה הקרן הנוכחית שלי מציעה בפועל, ולא רק מה הממוצע." };

const state = { profile: null, source: null, sources: null, result: null, chart: null, unlocked: new Set(["entry"]),
  chat: { state: null, log: [], quick: [], summary: null } };

// Per-tab persistence only (never sent to the server for storage).
const STORE_KEY = "pension-demo-v1";
function save() {
  try {
    sessionStorage.setItem(STORE_KEY, JSON.stringify({ profile: state.profile, source: state.source, chat: state.chat }));
  } catch { /* storage unavailable: the app still works for this page view */ }
}
function load() {
  try { return JSON.parse(sessionStorage.getItem(STORE_KEY) || "null"); } catch { return null; }
}

async function getJSON(url, opts) {
  const r = await fetch(url, opts);
  let body = null;
  try { body = await r.json(); } catch { /* handled below */ }
  if (!r.ok && !(body && body.status)) throw new Error(`שגיאת שרת (${r.status})`);
  return body;
}

// ---------------- theme (light / dark) ----------------
// The initial theme is applied by an inline script in index.html; this only handles the toggle.
function currentTheme() { return document.documentElement.dataset.theme === "dark" ? "dark" : "light"; }
function applyTheme(t, { persist = true } = {}) {
  document.documentElement.dataset.theme = t;
  if (persist) { try { localStorage.setItem("pension-theme", t); } catch { /* storage unavailable: theme applies for this page view */ } }
  const btn = $("#theme-toggle");
  if (btn) {
    const dark = t === "dark";
    btn.setAttribute("aria-pressed", String(dark));
    const label = dark ? "מעבר למצב בהיר" : "מעבר למצב כהה";
    btn.setAttribute("aria-label", label);
    btn.title = label;
    btn.querySelector(".ms").textContent = dark ? "light_mode" : "dark_mode";
  }
  const on = document.querySelector("#scen-card .seg .on");
  if (state.chart && on) drawChart(on.dataset.sc);   // chart colours are read from the theme tokens
}

// ---------------- navigation ----------------
function go(name) {
  if (!state.unlocked.has(name)) return;
  document.querySelectorAll(".screen").forEach((s) => (s.hidden = s.id !== `screen-${name}`));
  document.querySelectorAll(".bottomnav button").forEach((b) => b.classList.toggle("on", b.dataset.goto === name));
  $("#appbar-sub").textContent = SUB[name];
  window.scrollTo({ top: 0 });
  if (name === "results" && state.result && state.chart === null) drawChart("central");
}
function unlock(name) {
  state.unlocked.add(name);
  const b = document.querySelector(`.bottomnav button[data-goto="${name}"]`);
  if (b) b.disabled = false;
}
function lock(name) {
  state.unlocked.delete(name);
  const b = document.querySelector(`.bottomnav button[data-goto="${name}"]`);
  if (b) b.disabled = true;
}

// A new profile invalidates every downstream screen.
async function applyProfile(raw, source, { silent = false } = {}) {
  const clean = { ...raw };
  delete clean.derived; delete clean.validation_errors;
  let p;
  try {
    p = await getJSON("/api/profile/preview", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ profile: clean }) });
  } catch {
    p = { ...clean, derived: {}, validation_errors: ["לא ניתן לבדוק את הפרופיל מול השרת"] };
  }
  state.profile = p;
  state.source = source;
  state.result = null;
  if (state.chart) { state.chart.destroy(); state.chart = null; }
  $("#results").innerHTML = "";
  $("#results-empty").hidden = false;
  $("#btn-to-results").hidden = true;
  $("#analyze-error").hidden = true;
  lock("results"); lock("survey");
  renderProfile();
  renderSurvey();
  unlock("profile");
  $("#entry-next").hidden = false;
  $("#entry-next-text").textContent = source === "demo"
    ? "נטען פרופיל ההדגמה של עידו. הנתונים לא נשלפו ממאגר ממשלתי או מקרן פנסיה."
    : `נוצר פרופיל מהשיחה (${p.name}). הנתונים לא אומתו מול מקור כלשהו.`;
  save();
  if (!silent) $("#entry-next").scrollIntoView({ behavior: "smooth", block: "center" });
}

// ---------------- 1. entry ----------------
function setStatus(key, done, text, pillText, pillCls) {
  const li = document.querySelector(`#entry-status li[data-k="${key}"]`);
  li.classList.toggle("done", done);
  li.querySelector(".st").textContent = done ? "check_circle" : "error";
  if (text) li.querySelector(".grow").innerHTML = text;
  const p = li.querySelector(".pill");
  p.className = `pill ${pillCls}`;
  p.textContent = pillText;
}

async function connect() {
  const btn = $("#btn-connect");
  btn.disabled = true;
  btn.innerHTML = '<span class="ms" aria-hidden="true">progress_activity</span> טוען…';
  const t0 = Date.now();
  let demo;
  try {
    [demo, state.sources] = await Promise.all([getJSON("/api/profile"), getJSON("/api/sources")]);
  } catch (e) {
    btn.disabled = false;
    btn.innerHTML = '<span class="ms" aria-hidden="true">sync</span> נסה שוב';
    setStatus("profile", false, null, "נכשל", "pill-danger");
    return;
  }
  await sleep(Math.max(0, 1100 - (Date.now() - t0)));
  setStatus("profile", true, "טעינת פרופיל ההדגמה (מוגדר מראש)", "הושלם", "pill-emerald");
  await sleep(400);
  const snap = state.sources?.snapshot;
  const last = state.sources?.manifest?.last_attempt;
  if (snap) {
    const failed = last?.status === "failed";
    setStatus("market", true,
      `נתוני שוק: פנסיה-נט · תקופה ${period(snap.latest_report_period)} · נאסף ${dateHe(snap.collected_at)}`,
      failed ? "רענון אחרון נכשל" : "זמין", failed ? "pill-amber" : "pill-emerald");
  } else {
    setStatus("market", false, "נתוני שוק: לא נמצא מאגר מקומי", "חסר", "pill-danger");
  }
  btn.disabled = false;
  btn.innerHTML = '<span class="ms" aria-hidden="true">check</span> נטען – לטעינה מחדש לחץ שוב';
  await applyProfile(demo, "demo");
}

// ---------------- 1b. chat ----------------
function renderChat() {
  const log = $("#chat-log");
  log.innerHTML = state.chat.log.map((m) => {
    if (m.who === "summary") {
      const rows = m.rows.map((r) => `<div class="row"><span class="k">${esc(r.label)}</span><span class="v${r.missing ? " miss" : ""}">${esc(r.value)}</span>${m.final ? "" : `<button type="button" data-edit="${esc(r.label)}">תיקון</button>`}</div>`).join("");
      return `<div class="summary" role="group" aria-label="סיכום הפרופיל">${rows}</div>`;
    }
    return `<div class="msg ${m.who}${m.err ? " err" : ""}">${esc(m.text)}</div>`;
  }).join("");
  $("#chat-quick").innerHTML = state.chat.quick.map((q) =>
    `<button type="button" class="chip${q === "אישור ויצירת פרופיל" ? " primary" : ""}" data-q="${esc(q)}">${esc(q)}</button>`).join("")
    + (state.chat.state?.phase !== "done" && state.chat.state?.current === "name" ? `<button type="button" class="chip" data-demo="1">טען את פרופיל ההדגמה (עידו)</button>` : "");
  log.scrollTop = log.scrollHeight;
}

async function chatSend(text) {
  if (text) state.chat.log.push({ who: "user", text });
  state.chat.quick = [];
  state.chat.log.push({ who: "bot", text: "…", typing: true });
  renderChat();
  $("#chat-text").disabled = true;
  let turn;
  try {
    turn = await getJSON("/api/interview", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state: state.chat.state, message: text || null }) });
  } catch (e) {
    state.chat.log.pop();
    state.chat.log.push({ who: "bot", text: `השיחה נכשלה: ${e.message}. אפשר לנסות שוב.`, err: true });
    $("#chat-text").disabled = false;
    renderChat();
    return;
  }
  state.chat.log.pop();
  await sleep(250);
  if (text === "התחל מחדש") state.chat.log = [];
  state.chat.state = turn.state;
  for (const m of turn.messages) state.chat.log.push({ who: "bot", text: m });
  // keep only the latest summary in the log
  state.chat.log = state.chat.log.filter((m) => m.who !== "summary");
  if (turn.summary) state.chat.log.push({ who: "summary", rows: turn.summary, final: !!turn.profile });
  state.chat.quick = turn.quick_replies || [];
  $("#chat-text").disabled = turn.state.phase === "done";
  $("#chat-text").placeholder = turn.state.phase === "done" ? "הפרופיל נוצר" : "כתוב/י תשובה…";
  renderChat();
  save();
  if (turn.profile) await applyProfile(turn.profile, "chat");
  else $("#chat-text").focus({ preventScroll: true });
}

function bindChat() {
  $("#chat-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const t = $("#chat-text").value.trim();
    if (!t || $("#chat-text").disabled) return;
    $("#chat-text").value = "";
    chatSend(t);
  });
  $("#chat-quick").addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.dataset.demo) { $("#btn-connect").scrollIntoView({ behavior: "smooth", block: "center" }); connect(); return; }
    chatSend(b.dataset.q);
  });
  $("#chat-log").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-edit]");
    if (b) chatSend(`לתקן: ${b.dataset.edit}`);
  });
}

// ---------------- 2. profile ----------------
function renderProfile() {
  const p = state.profile;
  const d = p.derived || {};
  const has = (v) => v !== null && v !== undefined && v !== "";
  const MISSING = "חסר";
  $("#p-name").textContent = p.name || "משתמש/ת";
  const fam = [has(p.age) ? `גיל ${p.age}` : null,
    has(p.marital_status) ? p.marital_status + (has(p.spouse_age) ? ` (בן/בת זוג בגיל ${p.spouse_age})` : "") : null,
    has(p.children) ? `${p.children} ילדים` : null].filter(Boolean);
  $("#p-family").textContent = fam.join(" | ") || "פרטים אישיים לא הוזנו";
  $("#p-ret").textContent = has(p.planned_retirement_age) ? `גיל ${p.planned_retirement_age}` : MISSING;
  $("#p-ret-in").textContent = has(d.years_to_retirement) ? `בעוד ${d.years_to_retirement} שנים` : "";
  $("#p-salary").textContent = has(p.gross_monthly_salary) ? ils(p.gross_monthly_salary) : MISSING;
  $("#p-reason").textContent = p.reason || "—";
  $("#p-balance").textContent = has(p.accumulated_balance) ? ils(p.accumulated_balance) : MISSING;
  $("#p-deposit").textContent = has(d.monthly_deposit) ? ils(d.monthly_deposit) : "—";
  $("#p-deposit-note").textContent = has(d.contribution_rate) ? `${(d.contribution_rate * 100).toFixed(1)}% מהשכר (עובד + מעביד + פיצויים)` : "";
  $("#p-acc").textContent = has(p.accumulation_fee_pct) ? pct(p.accumulation_fee_pct) : MISSING;
  $("#p-dep").textContent = has(p.deposit_fee_pct) ? pct(p.deposit_fee_pct) : MISSING;
  $("#p-insurance").textContent = p.insurance?.note ?? "";
  $("#p-source").textContent = state.source === "chat" ? "הוזן בשיחה – לא אומת" : "נתוני הדגמה – פרופיל פיקטיבי";
  const errs = p.validation_errors || [];
  $("#p-errors").hidden = !errs.length;
  $("#p-errors").innerHTML = errs.length ? `<span class="ms" aria-hidden="true">warning</span><div><b>חסרים נתונים או שיש בהם בעיה. הניתוח יציין זאת ולא יציג השוואה:</b><ul class="mini-list">${errs.map((e) => `<li>${esc(e)}</li>`).join("")}</ul></div>` : "";
  $("#btn-analyze").innerHTML = '<span class="ms" aria-hidden="true">bolt</span> נתח את המצב הפנסיוני שלי';
  $("#steps").innerHTML = ["בדיקת פרופיל", "טעינת נתוני שוק (פנסיה-נט)", "חישוב בקוד", "ניסוח ממצאים", "אימות פלט", "דירוג לפי סיכון ותועלת"]
    .map((t) => `<li><span class="ms st" aria-hidden="true">radio_button_unchecked</span><div class="grow"><div class="t">${t}</div></div><span class="pill pill-neutral">ממתין</span></li>`).join("");
}

const STEP_ICON = { ok: "check_circle", warning: "warning", failed: "cancel" };
const STEP_PILL = { ok: ["הושלם", "pill-emerald"], warning: ["אזהרה", "pill-amber"], failed: ["נכשל", "pill-danger"] };

async function analyze() {
  const btn = $("#btn-analyze");
  const list = $("#steps");
  const err = $("#analyze-error");
  btn.disabled = true;
  err.hidden = true;
  $("#btn-to-results").hidden = true;
  list.innerHTML = '<li class="running"><span class="ms st" aria-hidden="true">progress_activity</span><div class="grow"><div class="t">מריץ את הניתוח בשרת…</div></div></li>';
  let res;
  try {
    const profile = { ...state.profile };
    delete profile.derived; delete profile.validation_errors;
    res = await getJSON("/api/analyze", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ profile }) });
  } catch (e) {
    list.innerHTML = "";
    err.hidden = false;
    err.innerHTML = `<span class="ms" aria-hidden="true">error</span><div><b>הניתוח לא הושלם.</b> ${esc(e.message)}. לא מוצגות תוצאות.</div>`;
    btn.disabled = false;
    return;
  }
  list.innerHTML = "";
  for (const s of res.steps || []) {
    await sleep(320);
    const [pt, pc] = STEP_PILL[s.status] || ["?", "pill-neutral"];
    list.insertAdjacentHTML("beforeend",
      `<li class="${esc(s.status)}"><span class="ms st" aria-hidden="true">${STEP_ICON[s.status] || "help"}</span><div class="grow"><div class="t">${esc(s.step)}</div><div class="d">${esc(s.detail)}</div></div><span class="pill ${pc}">${pt}</span></li>`);
  }
  btn.disabled = false;
  btn.innerHTML = '<span class="ms" aria-hidden="true">refresh</span> הרץ ניתוח מחדש';
  if (res.status === "failed" || res.status === "invalid_input") {
    err.hidden = false;
    err.innerHTML = `<span class="ms" aria-hidden="true">error</span><div><b>הניתוח לא הושלם.</b> ${esc(res.error)} השלבים למעלה מוצגים כפי שבוצעו בשרת.</div>`;
    return;
  }
  state.result = res;
  if (state.chart) { state.chart.destroy(); state.chart = null; }
  renderResults();
  unlock("results");
  unlock("survey");
  $("#btn-to-results").hidden = false;
}

// ---------------- 3. results ----------------
function renderResults() {
  const res = state.result;
  const c = res.calcs || {};
  const m = res.market || {};
  const p = state.profile;
  const parts = [];

  // banners
  if (res.generated_by === "template") {
    parts.push(`<div class="alert alert-info"><span class="ms" aria-hidden="true">info</span><div>הטקסט המילולי בממצאים נוצר <b>מתבנית קבועה בקוד, לא על ידי מודל AI</b>. החישובים, רמות הוודאות והדירוג נקבעו בקוד.</div></div>`);
  }
  if (m.last_refresh_failed) parts.push(`<div class="alert alert-warn"><span class="ms" aria-hidden="true">warning</span><div>${esc((m.messages || []).join(" "))}</div></div>`);

  // hero
  const ids = (res.findings || []).map((f) => f.finding_id);
  if (res.status === "insufficient") {
    parts.push(`<div class="rhero"><span class="pill pill-danger">אין די מידע להשוואה</span><p>${esc((m.messages || []).join(" "))}</p><p class="fine">ללא נתוני שוק עדכניים ואמינים, המערכת אינה מציגה סכומים או המלצות.</p></div>`);
  } else if (ids.includes("F-no-gap")) {
    parts.push(`<div class="rhero"><span class="pill pill-emerald">לא נמצא פער משמעותי בדמי הניהול</span><p>דמי הניהול שלך קרובים לממוצעים שנגבו בפועל בקרנות שנבדקו.</p></div>`);
  } else {
    const y1 = [c.median_y1?.value, c.alt1_y1?.value].filter((v) => v != null).sort((a, b) => a - b);
    const g = [c.median_gap_central?.value, c.alt1_gap_central?.value].filter((v) => v != null).sort((a, b) => a - b);
    const range = (a) => (a.length === 2 && Math.round(a[0]) !== Math.round(a[1])
      ? `<span class="r">${ils(a[0])}</span> <span class="to">עד</span> <span class="r">${ils(a[1])}</span>` : `<span class="r">${ils(a[a.length - 1])}</span>`);
    parts.push(`<div class="rhero">
      <div class="row gap"><span class="pill pill-emerald"><span class="ms sm" aria-hidden="true">search_insights</span> זוהתה הזדמנות לבדיקה בדמי הניהול</span><span class="pill pill-amber">${CERT[2][0]}</span></div>
      <div class="rhero-kpi"><div class="grow"><div class="k">חיסכון משוער בשנה הראשונה</div><div class="v">${range(y1)}</div></div><span class="ic ms" aria-hidden="true">trending_up</span></div>
      <div class="rhero-kpi"><div class="grow"><div class="k">פער משוער בצבירה בגיל ${p.planned_retirement_age} (תרחיש מרכזי)</div><div class="v">${range(g)}</div></div><span class="ic ms" aria-hidden="true">savings</span></div>
      <p class="fine">הטווח: מתנאים בגובה הקרן האמצעית בשוק ועד הקרן עם דמי הניהול הנמוכים ביותר עבורך, לפי הממוצעים שנגבו בפועל. זו הערכה לפי הנחות, לא הבטחה ולא הצעה.</p>
    </div>`);
  }

  // fee matrix
  if (c.alt1_dep && res.status !== "insufficient") {
    const fund = (res.findings.find((f) => f.finding_id === "F-switch-1")?.title || "").replace(/^לבחון מעבר ל/, "");
    const delta = (cur, alt) => `${Math.round(((alt - cur) / cur) * 100)}%`;
    parts.push(`<div class="card">
      <div class="card-head"><span class="ms" aria-hidden="true">compare_arrows</span><h2 class="grow">דמי הניהול שלך מול השוק</h2><span class="pill pill-neutral">השוואת שוק</span></div>
      <div class="matrix">
        <div class="mcol"><div class="h">מצב נוכחי <span class="dot"></span></div>
          <div class="mval"><div class="l">מצבירה</div><div class="v">${N(pct(p.accumulation_fee_pct))}</div></div>
          <div class="mval"><div class="l">מהפקדה</div><div class="v">${N(pct(p.deposit_fee_pct))}</div></div>
          <div class="foot">נתון פרופיל (הדגמה)</div></div>
        <div class="mcol alt"><div class="h">ממוצע בקרן הזולה ביותר עבורך <span class="dot"></span></div>
          <div class="mval"><div class="l">מצבירה</div><div class="v">${N(pct(c.alt1_acc.value))}<span class="delta">${delta(p.accumulation_fee_pct, c.alt1_acc.value)}</span></div></div>
          <div class="mval"><div class="l">מהפקדה</div><div class="v">${N(pct(c.alt1_dep.value))}<span class="delta">${delta(p.deposit_fee_pct, c.alt1_dep.value)}</span></div></div>
          <div class="foot">${esc(fund)} · ממוצע שנגבה בפועל, לא הצעה עבורך</div></div>
      </div>
      <div class="meta-box">
        <div class="line"><span class="pill pill-amber">${CERT[2][0]}</span></div>
        <div class="line"><span class="ms" aria-hidden="true">verified</span><div><b>מקור הנתונים:</b> פנסיה-נט, רשות שוק ההון (data.gov.il) · תקופת דיווח ${period(m.report_period)} · נאסף ${dateHe(m.collected_at)} · ${m.context?.funds_compared ?? "—"} קרנות מקיפות</div></div>
        <div class="line"><span class="ms" aria-hidden="true">info</span><div>אלה ממוצעים שנגבו מכלל העמיתים בכל קרן. לא ידוע אם התנאים זמינים לך. כדי לדעת, צריך לבקש הצעה אישית מהקרן.</div></div>
      </div>
      ${allFundsBars(m, p)}
    </div>`);
  }

  // scenarios
  if (res.scenarios) {
    const s = res.scenarios;
    parts.push(`<div class="card" id="scen-card">
      <div class="card-head"><span class="ms" aria-hidden="true">query_stats</span><div class="grow"><h2>שלושה תרחישים עד הפרישה (גיל ${p.planned_retirement_age})</h2><div class="sub">תנאים נוכחיים מול ממוצע ${esc(s.compared_fund)}</div></div></div>
      <div class="seg" role="tablist">${s.items.map((i) => `<button role="tab" data-sc="${esc(i.scenario)}" class="${i.scenario === "central" ? "on" : ""}"><b>${esc(i.label)}</b>${(i.annual_real_return * 100).toFixed(1)}%</button>`).join("")}</div>
      <div class="scen-panel" id="scen-panel"></div>
      <div class="note"><span class="ms" aria-hidden="true">lock_clock</span><div>החישוב מתבצע בקוד, בסימולציה חודשית עם ריבית דריבית. התשואות הן <b>הנחות</b> ריאליות להמחשה (ממתינות לאישור), ולא תחזית. קצבה חודשית תחושב בשלב הבא.</div></div>
    </div>`);
  }

  // action plan
  const plan = (res.findings || []).filter((f) => f.finding_id !== "F-insufficient");
  if (plan.length) {
    let n = 0;
    const item = (f) => `<div class="plan-item ${esc(f.risk)}"><div class="top"><span class="n">${++n}</span><div class="grow"><h3>${esc(f.title)}</h3>
      <div class="row gap" style="margin-top:6px"><span class="pill ${RISK[f.risk][1]}">${RISK[f.risk][0]}</span><span class="pill ${CERT[f.certainty][1]}">${CERT[f.certainty][0]}</span></div>
      ${f.ranking_value_ils != null ? `<div class="val">פער משוער בצבירה בפרישה (תרחיש מרכזי): כ-${N(ils(f.ranking_value_ils))}</div>` : `<div class="val">ללא הערכה כספית</div>`}
      <div class="why">${esc(f.next_step)}</div></div></div></div>`;
    const low = plan.filter((f) => f.risk === "low"), high = plan.filter((f) => f.risk === "high");
    parts.push(`<div class="card">
      <div class="card-head"><span class="ms" aria-hidden="true">checklist_rtl</span><h2 class="grow">תוכנית פעולה מדורגת</h2><span class="sub small">לפי סיכון, ואז לפי תועלת</span></div>
      ${low.length ? `<div class="plan-group-title"><span class="ms sm" aria-hidden="true">shield</span> קודם: פעולות בסיכון נמוך</div>${low.map(item).join("")}` : ""}
      ${high.length ? `<div class="plan-group-title"><span class="ms sm" aria-hidden="true">warning</span> אחר כך: לבחון בזהירות</div>${high.map(item).join("")}` : ""}
    </div>`);
  }

  // findings detail
  parts.push(`<details class="disclosure"><summary><span class="ms" aria-hidden="true">fact_check</span> פירוט הממצאים: נתונים, חישובים והנחות<span class="ms chev" aria-hidden="true">expand_more</span></summary>
    <div class="body"><div class="legend"><span class="f">עובדה: נתון מפרופיל או ממקור</span><span class="e">הערכה: חישוב לפי הנחות</span><span class="a">ניסוח: טקסט אוטומטי</span></div>
    ${(res.findings || []).map((f) => findingCard(f, c)).join("")}</div></details>`);

  // sources
  parts.push(sourcesBlock());

  // glossary
  parts.push(`<details class="disclosure"><summary><span class="ms" aria-hidden="true">menu_book</span> מילון מונחים<span class="ms chev" aria-hidden="true">expand_more</span></summary>
    <div class="body"><dl class="gloss">${GLOSSARY.map(([t, d]) => `<dt>${esc(t)}</dt><dd>${esc(d)}</dd>`).join("")}</dl></div></details>`);

  parts.push(`<button class="btn btn-primary btn-block" data-goto="survey">מעבר לשאלון המשוב <span class="ms" aria-hidden="true">arrow_back</span></button>
    <p class="fine" style="text-align:center">אבטיפוס לימודי. ההמלצות מבוססות על נתוני הדגמה ועל נתוני שוק ציבוריים, ואינן ייעוץ פנסיוני אישי.</p>`);

  $("#results-empty").hidden = true;
  $("#results").innerHTML = parts.join("");
  bindDynamic($("#results"));
  if (res.scenarios) {
    renderScenario("central");
    document.querySelectorAll("#scen-card .seg button").forEach((b) => b.addEventListener("click", () => {
      document.querySelectorAll("#scen-card .seg button").forEach((x) => x.classList.toggle("on", x === b));
      renderScenario(b.dataset.sc);
      drawChart(b.dataset.sc);
    }));
  }
}

function allFundsBars(m, p) {
  const funds = (m.funds || []).filter((f) => f.comparable);
  if (!funds.length) return "";
  const block = (title, key, mine) => {
    const rows = funds.map((f) => ({ name: f.parent_company, v: f[key] })).concat([{ name: "אתה", v: mine, me: true }]).sort((a, b) => b.v - a.v);
    const max = Math.max(...rows.map((r) => r.v)) || 1;
    return `<div class="label mt">${title}</div><div class="bars">${rows.map((r) => `<div class="bar-row${r.me ? " me" : ""}"><span class="bar-name" title="${esc(r.name)}">${esc(r.name)}</span><span class="bar-track"><span class="bar-fill" style="width:${(r.v / max) * 100}%"></span></span><span class="bar-val">${pct(r.v)}</span></div>`).join("")}</div>`;
  };
  return `<details class="disclosure" style="box-shadow:none"><summary><span class="ms" aria-hidden="true">bar_chart</span> השוואה לכל ${funds.length} הקרנות<span class="ms chev" aria-hidden="true">expand_more</span></summary>
    <div class="body">${block("דמי ניהול מהפקדה – ממוצע בפועל", "deposit_fee_pct", p.deposit_fee_pct)}${block("דמי ניהול מצבירה – ממוצע בפועל", "accumulation_fee_pct", p.accumulation_fee_pct)}</div></details>`;
}

function renderScenario(name) {
  const it = state.result.scenarios.items.find((i) => i.scenario === name);
  $("#scen-panel").innerHTML = `
    <div class="row between"><h3>תרחיש ${esc(it.label)}</h3><span class="pill pill-neutral">תשואה ריאלית ${(it.annual_real_return * 100).toFixed(1)}% (הנחה)</span></div>
    <div class="scen-kpis">
      <div><div class="k">צבירה משוערת בפרישה – תנאים נוכחיים</div>${N(ils(it.current_final))}</div>
      <div class="gain"><div class="k">תוספת משוערת אילו קיבלת תנאים בגובה הממוצע</div>כ-${N(ils(it.gap))}</div>
    </div>
    <div class="chart-box"><canvas id="chart" aria-label="גרף צבירה לפי גיל"></canvas></div>`;
  if (state.chart) { state.chart.destroy(); state.chart = null; }
  if (!$("#screen-results").hidden) drawChart(name);
}

function drawChart(name) {
  const s = state.result?.scenarios;
  const cv = $("#chart");
  if (!s || !cv) return;
  if (!window.Chart) { cv.parentElement.innerHTML = '<p class="sub">הגרף לא נטען. הנתונים מופיעים למעלה.</p>'; return; }
  const it = s.items.find((i) => i.scenario === name);
  if (state.chart) state.chart.destroy();
  const css = getComputedStyle(document.documentElement);
  Chart.defaults.color = css.getPropertyValue("--muted").trim() || "#64748b";
  Chart.defaults.borderColor = css.getPropertyValue("--line").trim() || "#e2e8f0";
  state.chart = new Chart(cv, {
    type: "line",
    data: { labels: it.current_yearly.map((_, k) => s.start_age + k + 1), datasets: [
      { label: "תנאים נוכחיים", data: it.current_yearly, borderColor: "#64748b", backgroundColor: "#64748b", pointRadius: 0, borderWidth: 2 },
      { label: `ממוצע ${s.compared_fund}`, data: it.alternative_yearly, borderColor: "#059669", backgroundColor: "rgba(5,150,105,.08)", fill: "-1", pointRadius: 0, borderWidth: 2.5 },
    ] },
    options: {
      maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
      plugins: { legend: { rtl: true, labels: { boxWidth: 12, font: { family: "Rubik" } } },
        tooltip: { rtl: true, callbacks: { title: (t) => `גיל ${t[0].label}`, label: (ctx) => `${ctx.dataset.label}: ${ils(ctx.parsed.y)}` } } },
      scales: { x: { grid: { display: false }, ticks: { font: { family: "Rubik" }, maxTicksLimit: 8 } },
        y: { ticks: { font: { family: "Rubik" }, callback: (v) => `${(v / 1e6).toFixed(1)} מ׳` } } },
    },
  });
}

function findingCard(f, calcs) {
  const refs = f.calc_refs.map((id) => calcs[id]).filter(Boolean);
  const kv = (arr) => `<div class="kv">${arr.map((x) => `<div><div class="l">${esc(x.label)}</div>${N(fmtCalc(x))}<div class="f">${esc(x.formula)}</div></div>`).join("")}</div>`;
  const facts = refs.filter((x) => x.kind === "fact"), ests = refs.filter((x) => x.kind === "estimate");
  const src = f.source_refs.length
    ? f.source_refs.map((s) => (s === "pensianet_2024_now" ? '<li><a href="https://data.gov.il/dataset/pensia-net" target="_blank" rel="noopener">פנסיה-נט – רשות שוק ההון (data.gov.il)</a></li>' : `<li>${esc(s)}</li>`)).join("")
    : "<li>נתוני פרופיל ההדגמה בלבד</li>";
  return `<div class="finding"><h3>${esc(f.title)}</h3>
    <div class="tags"><span class="pill ${CERT[f.certainty][1]}">${CERT[f.certainty][0]}</span><span class="pill ${RISK[f.risk][1]}">${RISK[f.risk][0]}</span><span class="pill pill-sky">${f.generated_by === "template" ? "ניסוח: תבנית, לא AI" : "ניסוח: מודל AI"}</span></div>
    ${facts.length ? `<div class="blk fact"><div class="lbl">עובדות</div>${kv(facts)}</div>` : ""}
    ${ests.length ? `<div class="blk est"><div class="lbl">הערכות (חישוב לפי הנחות)</div>${kv(ests)}</div>` : ""}
    <div class="blk ai"><div class="lbl">ממצא והסבר</div><p>${esc(f.finding)}</p><p>${esc(f.explanation)}</p></div>
    <p><b>הצעד הבא:</b> ${esc(f.next_step)}</p>
    ${f.assumptions.length ? `<div class="label mt">הנחות</div><ul class="mini-list">${f.assumptions.map((a) => `<li>${esc(a)}</li>`).join("")}</ul>` : ""}
    ${f.limitations.length ? `<div class="label mt">מגבלות</div><ul class="mini-list">${f.limitations.map((a) => `<li>${esc(a)}</li>`).join("")}</ul>` : ""}
    <div class="label mt">מקורות</div><ul class="mini-list">${src}</ul></div>`;
}

const VSTATUS = { verified: ["אומת", "pill-emerald"], partial: ["אומת חלקית", "pill-amber"], not_checked: ["לא נבדק", "pill-amber"], failed: ["נכשל", "pill-danger"] };

function sourcesBlock() {
  const man = state.sources?.manifest || {};
  const snap = state.sources?.snapshot;
  const last = man.last_attempt;
  const cov = snap?.coverage;
  const rejected = snap?.rejected || [];
  const srcs = (man.sources || []).map((s) => {
    const [t, cls] = VSTATUS[s.verification_status] || [s.verification_status, "pill-neutral"];
    return `<div class="tile tile-col"><div class="row between"><a href="${esc(s.url)}" target="_blank" rel="noopener"><b>${esc(s.name)}</b></a><span class="pill ${cls}">${esc(t)}</span></div>
      <div class="sub">${esc(s.publisher)} · ${esc(s.data_type)}</div>
      ${s.collected_at ? `<div class="sub">נאסף: ${dateHe(s.collected_at)} · עודכן במקור: ${dateHe(s.published_or_updated)}</div>` : ""}
      ${s.coverage ? `<div class="sub">כיסוי: ${esc(s.coverage)}</div>` : ""}
      ${(s.known_limitations || []).length ? `<ul class="mini-list">${s.known_limitations.map((l) => `<li>${esc(l)}</li>`).join("")}</ul>` : ""}</div>`;
  }).join("");
  return `<details class="disclosure"><summary><span class="ms" aria-hidden="true">policy</span> אסמכתאות, הנחות ומגבלות הניתוח<span class="ms chev" aria-hidden="true">expand_more</span></summary>
    <div class="body">
      <div class="meta-box"><div class="line"><span class="ms" aria-hidden="true">database</span><div><b>מצב מאגר נתוני השוק:</b> רענון אחרון ${dateHe(last?.at)}: ${last?.status === "success" ? "הצליח" : `<b style="color:var(--danger)">נכשל</b> (${esc(last?.error)})`}.
        ${cov ? ` נכללו ${cov.funds_comparable} קרנות מקיפות ו-${cov.tracks_included} מסלולים, תקופה ${period(snap.latest_report_period)}. ${esc(cov.note)}` : ""}</div></div>
        ${rejected.length ? `<div class="line"><span class="ms" aria-hidden="true">filter_alt_off</span><div>${rejected.length} מסלולים לא נכללו (לא דווחו בתקופה האחרונה או חסרים בהם נתונים).</div></div>` : ""}</div>
      ${srcs}
      <div class="label mt">הנחות החישוב</div><div id="assumptions-table" class="table-wrap"><p class="sub">טוען…</p></div>
      <div class="label mt">מה לא נבדק בגרסה זו</div>
      <ul class="mini-list"><li>כיסוי ביטוחי (נכות ושארים), והשלכות של מעבר קרן עליו.</li><li>חישוב קצבה חודשית.</li><li>תשואות, שירות ואיתנות של הקרנות.</li><li>הצעות אישיות של קרנות וזכאות של עידו לתנאים.</li></ul>
    </div></details>`;
}

async function loadAssumptions() {
  const el = $("#assumptions-table");
  if (!el) return;
  try {
    const a = await getJSON("/api/assumptions");
    const rows = Object.entries(a).filter(([k, v]) => v && typeof v === "object" && "status" in v && k !== "_meta").map(([k, v]) => {
      const val = k === "scenarios" ? ["conservative", "central", "optimistic"].map((n) => `${v[n].label} ${(v[n].annual_real_return * 100).toFixed(1)}%`).join(" · ")
        : k === "legal_fee_caps_pct" ? `הפקדה ${v.deposit}% · צבירה ${v.accumulation}%`
        : k === "market_data_max_age_months" ? `${v.value} חודשים`
        : k === "materiality_threshold_first_year_ils" ? ils(v.value)
        : `${(v.value * 100).toFixed(1)}%`;
      const st = v.status === "pending_approval" ? '<span class="pill pill-amber xs">ממתין לאישור</span>' : v.status === "needs_official_source" ? '<span class="pill pill-amber xs">דורש מקור רשמי</span>' : esc(v.status);
      return `<tr><td>${esc(v.note)}</td><td class="n">${esc(val)}</td><td>${st}</td></tr>`;
    }).join("");
    el.innerHTML = `<table><thead><tr><th>הנחה</th><th>ערך</th><th>סטטוס</th></tr></thead><tbody>${rows}</tbody></table>`;
  } catch {
    el.innerHTML = '<p class="sub">לא ניתן לטעון את ההנחות.</p>';
  }
}

// ---------------- 4. survey ----------------
function renderSurvey() {
  const demo = state.source === "demo";
  const SURVEY_DEMO = demo ? SURVEY_DEFAULTS : { q1: null, q2: null, q3: null, q3a: [], q4: null, q5: "" };
  const intro = document.querySelector("#screen-survey .card-soft p.sub");
  if (intro) intro.innerHTML = demo
    ? "בגרסה החיה המשתמשים ימלאו את השאלון אחרי קבלת הדוח. בדמו הזה התשובות הן תשובות לדוגמה של עידו, המשתמש הפיקטיבי. הן <b>אינן</b> תוצאות מדידה אמיתיות, ושום תשובה לא נשמרת."
    : "בגרסה החיה המשתמשים ימלאו את השאלון אחרי קבלת הדוח. זוהי הדמיה: התשובות <b>אינן נשמרות</b> ואינן נספרות כמדידה.";
  const radio = (name, opts) => opts.map(([v, l]) => `<label class="opt"><input type="radio" name="${name}" value="${v}" ${SURVEY_DEMO[name] === v ? "checked" : ""}> ${l}</label>`).join("");
  const scale = (name, lo, hi) => `<div class="scale">${[1, 2, 3, 4, 5].map((n) => `<label><input type="radio" name="${name}" value="${n}" ${SURVEY_DEMO[name] === String(n) ? "checked" : ""} aria-label="${n}"><span>${n}</span></label>`).join("")}</div><div class="scale-legend"><span>1 = ${lo}</span><span>5 = ${hi}</span></div>`;
  const checks = [["fund", "לפנות לקרן בנוגע לדמי ניהול"], ["insurance", "לבדוק את הכיסוי הביטוחי"], ["advisor", "להתייעץ עם יועץ פנסיוני מורשה"], ["other_funds", "לבחון קרנות או מסלולים אחרים"], ["other", "אחר"]]
    .map(([v, l]) => `<label class="opt"><input type="checkbox" name="q3a" value="${v}" ${SURVEY_DEMO.q3a.includes(v) ? "checked" : ""}> ${l}</label>`).join("");
  const q = (n, title, body) => `<div class="card"><div class="q-head"><span class="q-num">${n}</span><div class="q-title">${title}</div></div>${body}</div>`;
  $("#survey-form").innerHTML =
    q(1, "האם זיהית בדוח לפחות הזדמנות אחת לשיפור במצב הפנסיוני שלך?", radio("q1", [["new", "כן, וזה היה חדש לי"], ["known", "כן, אבל כבר ידעתי על זה"], ["none", "לא זיהיתי הזדמנות"]])) +
    q(2, "עד כמה ברורים לך הממצאים וההשלכות הכלכליות שלהם?", scale("q2", "לא ברורים בכלל", "ברורים מאוד")) +
    q(3, "האם אתה מתכוון לפעול בעקבות אחד הממצאים בחודש הקרוב?", radio("q3", [["yes", "כן, בהחלט"], ["likely", "כנראה"], ["unsure", "לא בטוח"], ["no", "לא"]]) +
      `<div id="q3a-wrap"><div class="label mt">איזו פעולה? (אפשר לסמן כמה)</div>${checks}</div>`) +
    q(4, "עד כמה אתה סומך על הממצאים שהוצגו?", scale("q4", "כלל לא", "מאוד")) +
    q(5, "מה היה חסר או לא ברור?", `<textarea name="q5" aria-label="תשובה פתוחה">${esc(SURVEY_DEMO.q5)}</textarea>`) +
    `<button class="btn btn-primary btn-block" type="submit"><span class="ms" aria-hidden="true">task_alt</span> סיום (הדמיה – לא נשמר)</button><p class="fine" id="survey-msg" role="status" style="text-align:center"></p>`;
  const form = $("#survey-form");
  const toggle = () => { const v = form.q3.value; $("#q3a-wrap").hidden = !(v === "yes" || v === "likely"); };
  form.addEventListener("change", toggle);
  toggle();
  form.addEventListener("submit", (e) => { e.preventDefault(); $("#survey-msg").textContent = "התשובות לא נשלחו ולא נשמרו. זוהי הדמיה של השאלון בגרסה החיה."; });
}

// ---------------- wiring ----------------
function bindDynamic(root) {
  root.querySelectorAll("[data-goto]").forEach((b) => b.addEventListener("click", () => go(b.dataset.goto)));
  root.querySelectorAll("details.disclosure").forEach((d) => d.addEventListener("toggle", () => { if (d.open) loadAssumptions(); }, { once: true }));
}

document.addEventListener("DOMContentLoaded", () => {
  bindDynamic(document);
  applyTheme(currentTheme(), { persist: false });
  $("#theme-toggle").addEventListener("click", () => applyTheme(currentTheme() === "dark" ? "light" : "dark"));
  bindChat();
  $("#btn-connect").addEventListener("click", connect);
  $("#btn-analyze").addEventListener("click", analyze);
  go("entry");
  getJSON("/api/sources").then((s) => { state.sources = state.sources || s; }).catch(() => {});
  const saved = load();
  if (saved?.chat?.state) {
    state.chat = saved.chat;
    state.chat.log = state.chat.log.filter((m) => !m.typing);
    $("#chat-text").disabled = state.chat.state.phase === "done";
    renderChat();
  } else {
    chatSend(null);
  }
  if (saved?.profile) applyProfile(saved.profile, saved.source, { silent: true });
  else renderSurvey();
});
