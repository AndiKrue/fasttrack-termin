// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Andreas Krueger
// FastTrack Termin web UI: streams /ask/stream, renders routes with evidence, call and route actions.
// All data goes into the DOM through textContent; no innerHTML with data.
"use strict";

const $ = (id) => document.getElementById(id);
const EXAMPLES = [
  ["Köpenick, knee, orthopaedics", "I live in Köpenick, have knee pain for three weeks and a referral from my GP without urgency code. How do I get an orthopaedics appointment fastest?"],
  ["Friedrichshain, dermatology", "I live in Friedrichshain and have a skin rash for two months. My GP gave me a referral. What is the fastest way to see a dermatologist?"],
  ["Pankow, cardiology", "I live in Pankow, my GP referred me to a cardiologist with urgency code. How fast can I get an appointment and how?"],
];
const STEPS = [
  ["plan", "Planning with Nemotron"],
  ["query", "Querying Zetaris (3 sources)"],
  ["web", "Searching the web (Firecrawl)"],
  ["recall", "Recalling memory (Meterless H-MEM)"],
  ["verify", "Verifying every claim"],
];

let here = null;            // {lat, lon} once the visitor shares a location
const geoCache = new Map(); // address -> Promise<{lat, lon} | null>
let geoQueue = Promise.resolve();
let mapsKey = "";           // Maps Embed key from /config; empty -> OSM/Google links only
fetch("/config").then((r) => r.json()).then((c) => { if (c.maps) mapsKey = c.embed_key || ""; }).catch(() => {});

// Booking pages the user opens themselves; the app never fetches these sites.
// Doctolib slugs as Doctolib links them (checked 2026-10-27); unknown specialty -> Doctolib start page.
const DOCTOLIB = [
  [/derma|haut/i, "hautarzt"], [/ortho/i, "teilfachgebiet-orthopaedie"], [/cardio|kardio/i, "kardiologie"],
  [/ophthal|augen/i, "augenheilkunde"], [/\bENT\b|hno/i, "facharzt-fur-hno"], [/gyn|frauen/i, "frauenarzt"],
  [/neuro/i, "neurologie"],
];
const TERMINSERVICE = "https://www.116117-termine.de/"; // linked as "Termin vereinbaren" on 116117.de
// Source: kvberlin.de -> Patientenservice 116117 -> KV-Notdienstpraxen (checked 2026-10-27)
const KV_NOTDIENST = "https://www.kvberlin.de/fuer-patienten/aerztlicher-bereitschaftsdienst-116117/kv-notdienstpraxen";

function doctolibUrl(...texts) {
  for (const t of texts) for (const [re, slug] of DOCTOLIB) if (re.test(t || "")) return `https://www.doctolib.de/${slug}/berlin`;
  return "https://www.doctolib.de/";
}

function mapSrc(address) {
  const dest = encodeURIComponent(address);
  const key = encodeURIComponent(mapsKey);
  return here
    ? `https://www.google.com/maps/embed/v1/directions?key=${key}&origin=${here.lat},${here.lon}&destination=${dest}&mode=transit`
    : `https://www.google.com/maps/embed/v1/place?key=${key}&q=${dest}`;
}

// ---- acute or unsure: fixed text, the same for every question, never decided by a model ----
function acutePanel() {
  const box = el("section", "card acute");
  box.setAttribute("aria-label", "Acute or unsure?");
  box.append(el("h2", null, "Acute or unsure?"));
  const ul = el("ul");
  const li1 = el("li");
  li1.append("Life-threatening: ", link("tel:112", null, "call 112"));
  const li2 = el("li");
  li2.append("Urgent outside practice hours: on-call doctor service ", link("tel:116117", null, "116117"), " (", link("https://www.116117.de", null, "116117.de"), ")");
  const li3 = el("li", null, "Hospital emergency rooms treat emergencies.");
  const li4 = el("li");
  li4.append(link(KV_NOTDIENST, null, "KV Berlin on-call practices (Notdienstpraxen)"));
  ul.append(li1, li2, li3, li4);
  box.append(ul);
  return box;
}
$("results").before(acutePanel());
let lastQuestion = "";

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = String(text);
  return n;
}

function link(href, cls, text) {
  const a = el("a", cls, text);
  a.href = href;
  if (!href.startsWith("tel:")) { a.target = "_blank"; a.rel = "noopener"; }
  return a;
}

// ---- examples and location ----
for (const [label, text] of EXAMPLES) {
  const b = el("button", "chip", label);
  b.type = "button";
  b.onclick = () => { $("q").value = text; $("q").focus(); };
  $("examples").append(b);
}

$("locate").onclick = () => {
  if (!navigator.geolocation) { $("locstate").textContent = "Location is not available in this browser."; return; }
  $("locstate").textContent = "Locating…";
  navigator.geolocation.getCurrentPosition(
    (p) => {
      here = { lat: p.coords.latitude, lon: p.coords.longitude };
      $("locstate").textContent = "Location set; distances are shown on the cards.";
      document.querySelectorAll("span[data-address]").forEach(fillDistance);
      document.querySelectorAll("iframe[data-address]").forEach((f) => { f.src = mapSrc(f.dataset.address); });
    },
    () => { $("locstate").textContent = "Location was not shared."; },
    { enableHighAccuracy: false, timeout: 10000 },
  );
};

// ---- timeline ----
function resetTimeline() {
  const ol = $("steps");
  ol.replaceChildren();
  for (const [key, title] of STEPS) {
    const li = el("li");
    li.dataset.step = key;
    li.append(el("span", "dot"), Object.assign(el("div"), {}));
    li.lastChild.append(el("div", "title", title), el("div", "detail", ""));
    ol.append(li);
  }
  setActive("plan");
  const prog = $("progress");
  prog.classList.remove("hidden", "compact");
  prog.querySelector("h2").textContent = "Working on it";
  prog.dataset.started = String(Date.now());
}

// After the answer, the timeline folds to one line so the routes sit right below the question.
function foldTimeline() {
  const prog = $("progress");
  const secs = Math.round((Date.now() - Number(prog.dataset.started || Date.now())) / 1000);
  const done = prog.querySelectorAll("li.done").length;
  const h2 = prog.querySelector("h2");
  h2.textContent = `Done in ${secs} s · ${done} steps checked · show steps`;
  h2.tabIndex = 0;
  h2.setAttribute("role", "button");
  prog.classList.add("compact");
  const toggle = () => {
    const open = prog.classList.toggle("compact") === false;
    h2.textContent = `Done in ${secs} s · ${done} steps checked · ${open ? "hide" : "show"} steps`;
  };
  h2.onclick = toggle;
  h2.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } };
}

function setActive(key) {
  for (const li of $("steps").children) {
    if (li.dataset.step === key && !li.classList.contains("done")) li.classList.add("active");
  }
}

function stepDetail(s) {
  switch (s.step) {
    case "plan": return `${(s.questions || []).length} questions: ${(s.questions || []).join(" · ")}`;
    case "query": {
      const q = s.queries || [];
      const ok = q.filter((x) => !x.error);
      const rows = ok.reduce((n, x) => n + (x.evidence || []).length, 0);
      return `${ok.length}/${q.length} queries answered, ${rows} evidence rows`;
    }
    case "web": return s.error ? `web search failed: ${s.error}` : `"${s.query}" → ${s.practices} practices with source links`;
    case "recall": return `${s.records} earlier verified findings`;
    case "verify": return `${s.kept} routes kept, ${s.dropped} dropped`;
    default: return "";
  }
}

function onStep(s) {
  const keys = STEPS.map((x) => x[0]);
  const li = [...$("steps").children].find((x) => x.dataset.step === s.step);
  if (!li) return;
  li.classList.remove("active");
  li.classList.add(s.error ? "failed" : "done");
  li.querySelector(".dot").textContent = s.error ? "!" : "✓";
  li.querySelector(".detail").textContent = stepDetail(s);
  // Web search is optional: when it is off, the next step after query is recall.
  const next = keys[keys.indexOf(s.step) + 1];
  if (next) setActive(next);
}

function skipUnfinished() {
  for (const li of $("steps").children) {
    if (!li.classList.contains("done") && !li.classList.contains("failed")) {
      li.classList.remove("active");
      li.querySelector(".detail").textContent = "skipped";
    }
  }
}

// ---- results ----
function practiceOf(route, evidence) {
  // The first cited row that names a phone or an address is the practice to act on.
  for (const id of route.evidence || []) {
    const row = (evidence[id] || {}).row || {};
    if (row.phone || row.address) return row;
  }
  return null;
}

// ---- why: one plain line per cited fact ----
function sourceName(ev) {
  if (ev.url) { try { return new URL(ev.url).host; } catch { return "web page"; } }
  const tables = [...String(ev.sql || "").matchAll(/\b(?:FROM|JOIN)\s+([\w.]+)/gi)].map((m) => m[1]);
  return tables.length ? "Zetaris " + [...new Set(tables)].join(" + ") : "Zetaris";
}

function factLine(row) {
  return Object.entries(row || {})
    .filter(([k, v]) => v != null && v !== "" && k !== "url")
    .slice(0, 5)
    .map(([k, v]) => `${k}: ${v}`)
    .join(" · ");
}

function whyBlock(route, evidence) {
  const det = el("details", "whyof");
  det.append(el("summary", null, "Why this route"));
  const ol = el("ol", "facts");
  for (const id of route.evidence || []) {
    const ev = evidence[id];
    if (!ev) continue;
    const li = el("li");
    li.append(el("span", "src", `${id} · ${sourceName(ev)}`), el("span", "fact", factLine(ev.row)));
    li.append(ev.url ? link(ev.url, "q", ev.url) : el("code", "q", ev.sql));
    ol.append(li);
  }
  det.append(ol);
  return det;
}

function renderRoute(route, i, evidence) {
  const card = el("article", "card route");
  card.append(el("div", "rank", i + 1), el("h3", null, route.route));
  if (route.expected_days != null) card.append(el("span", "days", `≈ ${route.expected_days} days`));
  card.append(el("p", "why", route.why));

  const p = practiceOf(route, evidence);
  card.append(readAloudButton(`Read route ${i + 1} aloud`, () => routeSpeech(route, p)));
  if (p) {
    const box = el("div", "practice");
    if (p.name) box.append(el("strong", null, p.name));
    if (p.phone) box.append(link("tel:" + String(p.phone).replace(/[^\d+]/g, ""), "call", "Call " + p.phone));
    if (p.address) {
      const dest = encodeURIComponent(p.address);
      box.append(
        link(`https://www.openstreetmap.org/directions?to=${dest}`, "link", "Route (OSM)"),
        link(`https://www.google.com/maps/dir/?api=1&destination=${dest}`, "link", "Route (Google)"),
      );
      const d = el("span", "dist");
      d.dataset.address = p.address;
      box.append(d);
      fillDistance(d);
    }
    card.append(box);
    if (p.address && mapsKey) {
      const f = el("iframe", "map");
      f.dataset.address = p.address;
      f.src = mapSrc(p.address);
      f.loading = "lazy";
      f.width = "100%";
      f.height = "220";
      f.title = `Route to ${p.name || p.address} by public transport`;
      f.referrerPolicy = "no-referrer-when-downgrade";
      card.append(f);
    }
  }

  const specialties = (route.evidence || []).map((id) => ((evidence[id] || {}).row || {}).specialty).join(" ");
  const book = el("div", "practice");
  book.append(
    link(doctolibUrl(specialties, route.route, lastQuestion), "link", "Search on Doctolib"),
    link(TERMINSERVICE, "link", "Book via 116117"),
  );
  card.append(book);

  const chips = el("div", "evchips");
  const detail = el("div");
  for (const id of route.evidence || []) {
    const ev = evidence[id];
    if (!ev) continue;
    const chip = el("button", "ev" + (ev.url ? " web" : ""), ev.url ? `${id} · web` : id);
    chip.type = "button";
    chip.onclick = () => {
      if (detail.dataset.open === id) { detail.replaceChildren(); detail.dataset.open = ""; return; }
      const box = el("div", "evbox");
      box.append(el("pre", "sql", ev.sql), el("pre", null, JSON.stringify(ev.row, null, 2)));
      if (ev.url) box.append(link(ev.url, null, "Open source"));
      detail.replaceChildren(box);
      detail.dataset.open = id;
    };
    chips.append(chip);
  }
  card.append(whyBlock(route, evidence), chips, detail);
  return card;
}

function renderResult(r) {
  const out = $("results");
  out.replaceChildren();
  const evidence = r.evidence || {};
  if (!(r.routes || []).length) {
    out.append(el("div", "card error", "No route survived verification. Open the trace to see which steps had no evidence."));
  } else {
    const head = el("div", "resulthead");
    head.append(el("h2", null, "Fastest routes"), readAloudButton("Read all routes aloud",
      () => r.routes.map((route) => routeSpeech(route, practiceOf(route, evidence))).join(" ")));
    out.append(head);
  }
  (r.routes || []).forEach((route, i) => out.append(renderRoute(route, i, evidence)));

  if ((r.caveats || []).length) {
    const c = el("section", "card");
    c.append(el("h2", null, "Caveats"));
    const ul = el("ul", "caveats");
    for (const x of r.caveats) ul.append(el("li", null, x));
    c.append(ul);
    out.append(c);
  }

  if ((r.dropped || []).length) {
    const c = el("section", "card dropped");
    c.append(el("h2", null, "Removed by the verifier"));
    const ul = el("ul");
    for (const d of r.dropped) {
      const li = el("li");
      li.append(el("strong", null, d.route || "(unnamed route)"), el("span", null, " — " + (d.note || d.reason || "")));
      ul.append(li);
    }
    c.append(ul);
    if (!r.dropped.some((d) => d.note) && (r.verifier_notes || []).length) {
      c.append(el("p", "muted", "Verifier notes: " + r.verifier_notes.join(" · ")));
    }
    out.append(c);
  }

  if ((r.model_calls || []).length) {
    const c = el("details", "card calls");
    c.append(el("summary", null, `Model calls (${r.model_calls.length})`));
    const table = el("table");
    const head = el("tr");
    for (const h of ["Role", "Model", "Seconds", "Tokens in/out"]) head.append(el("th", null, h));
    table.append(head);
    for (const m of r.model_calls) {
      const tr = el("tr");
      for (const v of [m.role, String(m.model || "").replace(/^nvidia\//, "") + (m.served_model && m.served_model !== m.model ? ` → ${m.served_model}` : "") + (m.provider ? ` via ${m.provider}` : ""), m.seconds, `${m.tokens_in ?? "?"}/${m.tokens_out ?? "?"}`]) tr.append(el("td", null, v));
      table.append(tr);
    }
    c.append(table);
    out.append(c);
  }

  const t = r.trace || {};
  const det = el("details", "card trace");
  det.append(el("summary", null, "Trace: every step, query and verifier note"), el("pre", null, JSON.stringify(t.steps || [], null, 2)));
  out.append(det);

  $("runinfo").textContent =
    `Run ${r.run_id} · source ${t.source || "?"} · web ${t.web || "off"} · memory ${t.memory || "?"} · ` +
    `${(r.model_calls || []).length} Nemotron calls via ${((r.model_calls || [])[0] || {}).provider || "nvidia-api"}`;
}

// ---- distance (Nominatim, sequential, at most one request per second, cached) ----
function geocode(address) {
  if (!geoCache.has(address)) {
    const job = geoQueue.then(async () => {
      try {
        const q = encodeURIComponent(address + ", Berlin");
        const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${q}`, { headers: { Accept: "application/json" } });
        const hit = (await res.json())[0];
        return hit ? { lat: +hit.lat, lon: +hit.lon } : null;
      } catch { return null; }
    });
    geoQueue = job.then(() => new Promise((ok) => setTimeout(ok, 1100)));
    geoCache.set(address, job);
  }
  return geoCache.get(address);
}

function km(a, b) {
  const R = 6371, rad = (x) => (x * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat), dLon = rad(b.lon - a.lon);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

async function fillDistance(node) {
  if (!here) return;
  node.textContent = "measuring…";
  const at = await geocode(node.dataset.address);
  node.textContent = at ? `≈ ${km(here, at).toFixed(1)} km away` : "";
}

// ---- ask ----
async function ask() {
  const question = $("q").value.trim();
  if (!question) return;
  lastQuestion = question;
  $("go").disabled = true;
  $("results").replaceChildren();
  resetTimeline();
  try {
    const res = await fetch("/ask/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let nl;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl).trim();
        buf = buf.slice(nl + 1);
        if (!line) continue;
        const msg = JSON.parse(line);
        if (msg.step) onStep(msg.step);
        else if (msg.result) {
          skipUnfinished();
          renderResult(msg.result);
          foldTimeline();
          const first = document.querySelector("#results article.route");
          if (first) first.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
        }
        else if (msg.error) throw new Error(msg.error);
      }
    }
  } catch (e) {
    skipUnfinished();
    $("results").replaceChildren(el("div", "card error", "Something went wrong: " + e.message));
  } finally {
    $("go").disabled = false;
  }
}

$("go").onclick = ask;
$("q").addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) ask(); });

// ---- speech: Web Speech API only, started by the user, never auto-played ----
// Recognition follows the browser language; answers are written in English, so they are read in English.
const SPEECH_LANG = /^de/i.test(navigator.language || "") ? "de-DE" : "en-US";
const READ_LANG = "en-US";
let speakingBtn = null;
let utterances = []; // kept referenced: Chrome drops utterances that are garbage-collected mid-speech
const MIC_ERRORS = {
  "not-allowed": "Microphone blocked: allow it in the address bar",
  "service-not-allowed": "Speech service blocked in this browser",
  "network": "Speech service unreachable",
  "no-speech": "No speech heard, try again",
  "audio-capture": "No microphone found",
};
function pickVoice() {
  const voices = speechSynthesis.getVoices();
  return voices.find((v) => v.lang === READ_LANG) || voices.find((v) => /^en/i.test(v.lang || "")) || null;
}
if ("speechSynthesis" in window) speechSynthesis.getVoices(); // starts loading the voice list early
function speakText(text, onDone) {
  speechSynthesis.cancel();
  const voice = pickVoice();
  // Short chunks: Chrome stops long utterances after ~15 s.
  utterances = (text.match(/[^.!?]+[.!?]*/g) || [text]).map((chunk) => {
    const u = new SpeechSynthesisUtterance(chunk.trim());
    u.lang = READ_LANG;
    if (voice) u.voice = voice;
    u.onerror = onDone;
    return u;
  });
  utterances[utterances.length - 1].onend = onDone;
  // speak() right after cancel() is dropped by Chrome; a short delay lets the cancel settle.
  setTimeout(() => utterances.forEach((u) => speechSynthesis.speak(u)), 150);
}

function routeSpeech(route, p) {
  const parts = [route.route + "."];
  if (route.expected_days != null) parts.push(`About ${route.expected_days} days.`);
  if (route.why) parts.push(route.why);
  if (p && p.name) parts.push(`Practice: ${p.name}.`);
  if (p && p.phone) parts.push(`Phone: ${p.phone}.`);
  return parts.join(" ");
}

function stopReading() {
  if (!speakingBtn) return;
  speakingBtn.setAttribute("aria-pressed", "false");
  speakingBtn.textContent = "Read aloud";
  speakingBtn = null;
}

function readAloudButton(label, text) {
  const b = el("button", "ghost speak", "Read aloud");
  b.type = "button";
  b.setAttribute("aria-label", label);
  b.setAttribute("aria-pressed", "false");
  if (!("speechSynthesis" in window)) { b.hidden = true; return b; }
  b.onclick = () => {
    const again = speakingBtn === b;
    speechSynthesis.cancel();
    stopReading();
    if (again) return; // second press stops
    speakingBtn = b;
    b.setAttribute("aria-pressed", "true");
    b.textContent = "Stop reading";
    speakText(text(), () => { if (speakingBtn === b) stopReading(); });
  };
  return b;
}

(function micButton() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return; // unsupported: no button
  const mic = el("button", "ghost mic", "Speak");
  mic.type = "button";
  mic.setAttribute("aria-label", "Speak your question");
  mic.setAttribute("aria-pressed", "false");
  let rec = null;
  const done = () => { rec = null; mic.setAttribute("aria-pressed", "false"); mic.classList.remove("listening"); mic.textContent = "Speak"; };
  mic.onclick = () => {
    if (rec) { rec.stop(); return; }
    rec = new SR();
    rec.lang = SPEECH_LANG;
    rec.interimResults = true;
    rec.onresult = (e) => { $("q").value = [...e.results].map((x) => x[0].transcript).join(""); }; // interim, then final; never submits
rec.onend = () => { if (rec) done(); };
    rec.onerror = (e) => {
      done();
      mic.textContent = MIC_ERRORS[e.error] || "Speech error: " + e.error;
      setTimeout(() => { if (!rec) mic.textContent = "Speak"; }, 4000);
    };
    rec.start();
    mic.setAttribute("aria-pressed", "true");
    mic.classList.add("listening");
    mic.textContent = "Listening… tap to stop";
  };
  $("go").after(mic);
})();
