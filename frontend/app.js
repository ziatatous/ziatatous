// ASFALTO frontend: tiny hash-router SPA, no build step.
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const api = (p, o) => fetch("/api/" + p, o).then((r) => r.json());
const store = { get: (k, d) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } },
                set: (k, v) => { try { localStorage.setItem(k, v); } catch {} } };

// ---------- i18n (UI strings only) ----------
const T = {
  fr: { home: "Live", terrain: "Terrain", mouvements: "Mouvements actifs", surv: "Surveillance", system: "Système",
    latest: "Dernières infos de rue", upcoming: "À venir", none: "Rien d'annoncé.", nonews: "Aucun article. Va dans Système → Collecter.",
    all: "Tous", calm: "Mode calme", new: "NOUVEAU", source: "source", search: "Rechercher…", list: "Liste", type: "Type", scene: "Scène", city: "Ville",
    orient: "Orientation", feed: "Fil", annuaire: "Annuaire de canaux publics", collect: "Collecter maintenant", export: "Exporter la base",
    import: "Importer une base", state_ok: "OK", state_ko: "MORT", palette: "Aller à…", add_events: "Ajoute des agendas dans data/agenda.yaml",
    window: "Fenêtre", articles: "articles", world: "Monde / non localisé", noactive: "Rien de détecté sur cette période. Lance une collecte (Système).", onlyaction: "Seulement les articles d'action" },
  es: { home: "Live", terrain: "Terreno", mouvements: "Movimientos activos", surv: "Vigilancia", system: "Sistema",
    latest: "Últimas noticias de calle", upcoming: "Próximos", none: "Nada anunciado.", nonews: "Sin artículos. Ve a Sistema → Recopilar.",
    all: "Todos", calm: "Modo calma", new: "NUEVO", source: "fuente", search: "Buscar…", list: "Lista", type: "Tipo", scene: "Escena", city: "Ciudad",
    orient: "Orientación", feed: "Noticias", annuaire: "Directorio de canales públicos", collect: "Recopilar ahora", export: "Exportar base",
    import: "Importar base", state_ok: "OK", state_ko: "CAÍDO", palette: "Ir a…", add_events: "Añade agendas en data/agenda.yaml",
    window: "Ventana", articles: "artículos", world: "Mundo / sin localizar", noactive: "Nada detectado. Recopila (Sistema).", onlyaction: "Solo artículos de acción" },
  en: { home: "Live", terrain: "Field", mouvements: "Active movements", surv: "Surveillance", system: "System",
    latest: "Latest street news", upcoming: "Upcoming", none: "Nothing announced.", nonews: "No articles. Go to System → Collect.",
    all: "All", calm: "Calm mode", new: "NEW", source: "source", search: "Search…", list: "List", type: "Type", scene: "Scene", city: "City",
    orient: "Orientation", feed: "Feed", annuaire: "Public channels directory", collect: "Collect now", export: "Export database",
    import: "Import database", state_ok: "OK", state_ko: "DEAD", palette: "Go to…", add_events: "Add calendars in data/agenda.yaml",
    window: "Window", articles: "articles", world: "World / unlocated", noactive: "Nothing detected. Collect first (System).", onlyaction: "Action articles only" },
};
let lang = store.get("lang", "fr");
const t = (k) => (T[lang] && T[lang][k]) || T.fr[k] || k;
const ROUTES = [["", "home"], ["mouvements", "mouvements"], ["terrain", "terrain"], ["surv", "surv"], ["system", "system"]];
const lastVisit = store.get("lastVisit", "");  // used to flag really new items only
let cache = {};
const data = async (n) => (cache[n] ??= await api("data/" + n));
const ORIENTS = ["généraliste", "gauche", "gauche radicale", "libertaire", "droite", "extrême droite", "ONG", "indépendant"];
const COUNTRY = { FR: "France", ES: "España", GB: "United Kingdom", US: "USA", DE: "Deutschland", IT: "Italia", GR: "Ελλάδα", PT: "Portugal", BR: "Brasil", AR: "Argentina", CL: "Chile", MX: "México", CO: "Colombia", "": "" };

const itemHTML = (i) => `<div class="panel"><div class="meta">${i.first_seen > lastVisit && lastVisit ? `<span class="new">${t("new")}</span>` : ""}<span class="tag ${esc(i.orient)}">${esc(i.orient)}</span>${esc(i.source)} · ${esc((i.published || "").slice(0, 16).replace("T", " "))}</div>
  <h3><a href="${esc(i.link)}" target="_blank" rel="noopener">${esc(i.title)}</a></h3><div>${esc(i.summary)}</div></div>`;
const evHTML = (e) => `<div class="panel"><div class="meta"><span class="tag">${esc(e.type)}</span>${esc((e.start || "").slice(0, 16).replace("T", " "))} · ${esc(e.city)}</div>
  <h3>${e.link ? `<a href="${esc(e.link)}" target="_blank" rel="noopener">${esc(e.title)}</a>` : esc(e.title)}</h3><div class="meta">${esc(e.place)} · ${t("source")}: ${esc(e.source)}</div></div>`;

function feedBlock() {
  return `<div class="filters"><input id="fq" placeholder="${t("search")}"><select id="fo"><option value="">${t("orient")}: ${t("all")}</option>${ORIENTS.map((o) => `<option>${esc(o)}</option>`).join("")}</select></div><div id="fl"></div>`;
}
async function loadFeed(base) {
  const run = async () => {
    const items = await api(`items?${base}&orient=${encodeURIComponent($("#fo").value)}&q=${encodeURIComponent($("#fq").value)}&limit=80`);
    $("#fl").innerHTML = items.map(itemHTML).join("") || `<p class="empty">${t("nonews")}</p>`;
  };
  $("#fq").oninput = run; $("#fo").onchange = run; run();
}

// ---------- pages ----------
const pages = {
  async home() {
    const [items, ev] = await Promise.all([api("items?action=true&hours=48&limit=25"), api("events")]);
    $("#app").innerHTML = `<h1>ASFALTO · LIVE</h1><div class="grid" style="grid-template-columns:2fr 1fr"><div><h2>${t("latest")} (48 h)</h2>${items.map(itemHTML).join("") || `<p class="empty">${t("nonews")}</p>`}</div>
      <div><h2>${t("upcoming")}</h2>${ev.slice(0, 8).map(evHTML).join("") || `<p class="empty">${t("none")}</p>`}</div></div>`;
  },
  async mouvements(country) {
    const hours = +store.get("win", "72");
    const act = await api("active?hours=" + hours);
    const sel = country === undefined ? null : decodeURIComponent(country || "");
    $("#app").innerHTML = `<h1>${t("mouvements")}</h1><div class="filters"><span class="meta">${t("window")}:</span>
      <select id="win">${[[24, "24 h"], [72, "72 h"], [168, "7 j"]].map(([h, l]) => `<option value="${h}" ${h === hours ? "selected" : ""}>${l}</option>`).join("")}</select></div>
      <div class="grid">${act.map((a) => `<a class="panel" style="text-decoration:none;color:inherit;${sel === a.country ? "border-color:var(--yellow)" : ""}" href="#/mouvements/${encodeURIComponent(a.country)}">
        <h3>${esc(COUNTRY[a.country] || a.country || t("world"))}</h3><div class="int" style="font:700 28px Rajdhani">${a.n} <span class="meta">${t("articles")}</span></div></a>`).join("") || `<p class="empty">${t("noactive")}</p>`}</div>
      ${sel !== null ? `<h2>${esc(COUNTRY[sel] || sel || t("world"))}</h2>` + feedBlock() : ""}`;
    $("#win").onchange = (e) => { store.set("win", e.target.value); render(); };
    if (sel !== null) loadFeed(`country=${encodeURIComponent(sel)}&action=true&hours=${hours}`);
  },
  async terrain() {
    const cities = await data("cities");
    $("#app").innerHTML = `<h1>${t("terrain")}</h1><div class="filters">
      <select id="fc">${Object.entries(cities).map(([k, v]) => `<option value="${k}">${esc(v.name)}</option>`).join("")}<option value="">${t("city")}: ${t("all")}</option></select>
      <select id="ft"><option value="">${t("type")}: ${t("all")}</option>${["manifestation", "concert", "rassemblement", "collage", "festival", "assemblée", "other"].map((x) => `<option>${x}</option>`).join("")}</select>
      <input id="fs" placeholder="${t("scene")}"></div><div id="map"></div><div id="el"></div><div id="ann"></div>`;
    const map = L.map("map").setView([cities.madrid.lat, cities.madrid.lon], 12);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "© OpenStreetMap" }).addTo(map);
    const layer = L.layerGroup().addTo(map);
    const run = async () => {
      const c = $("#fc").value;
      if (c) map.setView([cities[c].lat, cities[c].lon], 12);
      const ev = await api(`events?city=${c}&type=${$("#ft").value}&scene=${encodeURIComponent($("#fs").value)}`);
      layer.clearLayers();
      ev.filter((e) => e.lat).forEach((e) => L.marker([e.lat, e.lon]).bindPopup(`<b>${esc(e.title)}</b><br>${esc((e.start || "").slice(0, 16))}<br>${esc(e.place)}`).addTo(layer));
      $("#el").innerHTML = `<h2>${t("list")}</h2>` + (ev.map(evHTML).join("") || `<p class="empty">${t("none")} <span class="meta">(${t("add_events")})</span></p>`);
      const an = (await data("annuaire")).annuaire.filter((a) => !c || a.city === c);
      $("#ann").innerHTML = `<h2>${t("annuaire")}</h2><div class="grid">${an.map((a) => `<div class="panel"><span class="tag">${esc(a.type)}</span><h3><a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.name)}</a></h3><div class="meta">${esc(a.scene)}</div></div>`).join("")}</div>`;
    };
    $("#fc").onchange = $("#ft").onchange = run; $("#fs").oninput = run; run();
  },
  async surv() {
    $("#app").innerHTML = `<h1>${t("surv")}</h1>${feedBlock()}`;
    loadFeed("category=surveillance");
  },
  async system() {
    const s = await api("system");
    $("#app").innerHTML = `<h1>${t("system")}</h1><p class="meta">${s.items} articles · ${s.events} événements</p>
    <button id="col">${t("collect")}</button> <a href="/api/export"><button>${t("export")}</button></a> <label class="meta">${t("import")} <input type="file" id="imp"></label>
    <div id="runs">${runsHTML(s.runs)}</div>`;
    $("#col").onclick = async () => { $("#col").textContent = "…"; $("#runs").innerHTML = runsHTML((await api("collect", { method: "POST" })).runs); $("#col").textContent = t("collect"); };
    $("#imp").onchange = async (e) => { const f = new FormData(); f.append("file", e.target.files[0]); await fetch("/api/import", { method: "POST", body: f }); location.reload(); };
  },
};
const runsHTML = (r) => `<table style="width:100%;margin-top:14px;font:13px 'JetBrains Mono'">${r.map((x) => `<tr><td class="${x.ok ? "ok" : "ko"}">${x.ok ? t("state_ok") : t("state_ko")}</td><td>${esc(x.name)}</td><td>${x.count}</td><td class="meta">${esc((x.last_run || "").slice(0, 16))}</td><td class="ko">${esc((x.error || "").slice(0, 120))}</td></tr>`).join("")}</table>`;

// ---------- router, nav, palette ----------
function render() {
  const [, a, b] = location.hash.split("/");
  const route = a || "";
  document.querySelectorAll("nav a").forEach((n) => n.classList.toggle("on", n.getAttribute("href") === "#/" + route));
  (pages[route] || pages.home)(b);
  window.scrollTo(0, 0);
}
function nav() {
  $("#nav").innerHTML = ROUTES.map(([h, k]) => `<a href="#/${h}">${t(k)}</a>`).join("");
  $("#calm").textContent = t("calm");
  $("#palin").placeholder = t("palette");
}
async function openPalette() {
  const p = $("#pal"); p.hidden = false; $("#palin").value = ""; $("#palin").focus();
  const act = await api("active?hours=168");
  const all = [...ROUTES.map(([h, k]) => [t(k), "#/" + h]), ...act.map((a) => [`${t("mouvements")} · ${COUNTRY[a.country] || a.country || t("world")}`, "#/mouvements/" + encodeURIComponent(a.country)])];
  const go = (h) => { location.hash = h; p.hidden = true; };
  const draw = () => {
    const q = $("#palin").value.toLowerCase();
    $("#pallist").innerHTML = all.filter((x) => x[0].toLowerCase().includes(q)).slice(0, 10).map((x, i) => `<li class="${i ? "" : "sel"}" data-h="${x[1]}">${esc(x[0])}</li>`).join("");
  };
  draw(); $("#palin").oninput = draw;
  $("#palin").onkeydown = (e) => { if (e.key === "Enter") { const li = $("#pallist li"); if (li) go(li.dataset.h); } if (e.key === "Escape") p.hidden = true; };
  $("#pallist").onclick = (e) => e.target.dataset.h && go(e.target.dataset.h);
}
$("#k").onclick = openPalette;
document.addEventListener("keydown", (e) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); openPalette(); } });
$("#calm").onclick = () => { const on = !document.body.classList.contains("calm"); document.body.classList.toggle("calm", on); store.set("calm", on ? "1" : ""); };
if (store.get("calm", "")) document.body.classList.add("calm");
$("#lang").value = lang;
$("#lang").onchange = (e) => { lang = e.target.value; store.set("lang", lang); nav(); render(); };
window.addEventListener("hashchange", render);
nav(); render();
store.set("lastVisit", new Date().toISOString().slice(0, 19));  // next visit: only newer items get the NEW flag
