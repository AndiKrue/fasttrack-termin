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
      document.querySelectorAll("[data-address]").forEach(fillDistance);
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
  $("progress").classList.remove("hidden");
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
  }

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
      for (const v of [m.role, String(m.model || "").replace(/^nvidia\//, ""), m.seconds, `${m.tokens_in ?? "?"}/${m.tokens_out ?? "?"}`]) tr.append(el("td", null, v));
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
    `${(r.model_calls || []).length} Nemotron calls`;
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
        else if (msg.result) { skipUnfinished(); renderResult(msg.result); }
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
