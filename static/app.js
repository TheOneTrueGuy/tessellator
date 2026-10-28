/* Tessellator frontend */
const $ = (id) => document.getElementById(id);

let network = null, nodesDS = null, edgesDS = null;
let selection = [];            // ordered, max 2
let activeLens = null;
let pathTrace = null;          // interpolation polyline in the 3D view
let currentEmbed = null;       // active embedder name (for reset warning)

function status(msg, isErr) {
  const s = $("status");
  s.textContent = msg || "";
  s.className = isErr ? "err" : "";
}

async function api(path, body) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}

async function getJSON(path) {
  const r = await fetch(path);
  return r.json();
}

/* ---------- graph rendering ---------- */

const ROLE_COLOR = { pole: "#e8934a", "beyond-pole": "#b07ac8" };
const EDGE_STYLE = {
  axis:      { color: "#e8934a", width: 3 },
  perp:      { color: "#4a6ea8", width: 1 },
  extension: { color: "#b07ac8", width: 2, dashes: true },
};

function nodeVis(n) {
  const sel = selection.includes(n.id);
  return {
    id: n.id,
    label: n.id,
    title: `depth ${n.depth ?? "?"}${n.perp_score != null ? " · perp " + n.perp_score.toFixed(2) : ""}`,
    color: {
      background: ROLE_COLOR[n.role] || "#4a6ea8",
      border: sel ? "#ffffff" : "#2a3a55",
      highlight: { background: "#6a9ee8", border: "#fff" },
    },
    borderWidth: sel ? 3 : 1,
    size: n.role === "pole" ? 22 : 14,
    font: { color: "#eee", size: 12 },
  };
}

function drawGraph(g) {
  nodesDS = new vis.DataSet(g.nodes.map(nodeVis));
  edgesDS = new vis.DataSet(g.edges.map((e, i) => ({
    id: i, from: e.source, to: e.target, ...(EDGE_STYLE[e.kind] || EDGE_STYLE.perp),
  })));
  network = new vis.Network($("graph2d"), { nodes: nodesDS, edges: edgesDS }, {
    physics: { solver: "forceAtlas2Based", forceAtlas2Based: { gravitationalConstant: -60 } },
    interaction: { hover: true },
  });
  network.on("click", (p) => { if (p.nodes.length) toggleSelect(p.nodes[0]); });
  network.on("doubleClick", async (p) => {
    if (!p.nodes.length) return;
    status("expanding " + p.nodes[0] + "…");
    try {
      const j = await api("/api/expand", {
        node: p.nodes[0], breadth: +$("breadth").value, mode: $("mode").value,
      });
      status(`added: ${j.added.join(", ") || "(nothing)"}`);
      drawGraph(j.graph);
      if (activeLens) viewLens(activeLens);
    } catch (e) { status(e.message, true); }
  });
}

function toggleSelect(id) {
  const i = selection.indexOf(id);
  if (i >= 0) selection.splice(i, 1);
  else { selection.push(id); if (selection.length > 2) selection.shift(); }
  $("selLabel").textContent = selection.length ? "· " + selection.join(" , ") : "";
  $("interpBtn").disabled = selection.length !== 2;
  $("extendBtn").disabled = selection.length !== 2;
  if (nodesDS) nodesDS.update(nodesDS.get().map(n =>
    ({ id: n.id, borderWidth: selection.includes(n.id) ? 3 : 1,
       color: { ...n.color, border: selection.includes(n.id) ? "#fff" : "#2a3a55" } })));
}

/* ---------- 3D lens view ---------- */

async function viewLens(name) {
  status("projecting into lens " + name + "…");
  try {
    const j = await api("/api/project", { lens: name });
    activeLens = name; pathTrace = null;
    const nodes = Object.keys(j.coords);
    const coord = (n, i) => (j.coords[n][i] ?? 0);
    Plotly.react($("plot3d"), [{
      type: "scatter3d", mode: "markers+text",
      x: nodes.map(n => coord(n, 0)),
      y: nodes.map(n => coord(n, 1)),
      z: nodes.map(n => coord(n, 2)),
      text: nodes, textposition: "top center",
      marker: { size: 5, color: "#6a9ee8" },
      textfont: { color: "#ccc", size: 10 },
    }], {
      paper_bgcolor: "#1a1b1e", scene_bgcolor: "#1a1b1e",
      margin: { l: 0, r: 0, t: 30, b: 0 },
      title: { text: `${name} · k=${j.k} · var kept ${(100 * j.variance_kept).toFixed(0)}%`,
               font: { color: "#9ab", size: 13 } },
      scene: {
        xaxis: { title: "eig 1", color: "#789" },
        yaxis: { title: "eig 2", color: "#789" },
        zaxis: { title: "eig 3", color: "#789" },
      },
    });
    status(`lens "${name}": showing first ${Math.min(3, j.k)} of ${j.k} axes`);
  } catch (e) { status(e.message, true); }
}

/* ---------- lens management ---------- */

async function createLens() {
  const name = $("lensName").value.trim();
  if (!name) return status("lens needs a name", true);
  const prompts = $("lensPrompts").value.trim();
  const concept = $("lensConcept").value.trim();
  if (!prompts && !concept) return status("give a concept or prompt list", true);
  status("building lens " + name + "…");
  try {
    const j = await api("/api/lens", {
      name, concept: concept || undefined,
      prompts: prompts || undefined,
      k: $("lensK").value || undefined,
      variance_keep: +$("lensVar").value,
    });
    addLensItem(j);
    status(`lens "${j.name}": k=${j.k}, ${(100 * j.variance_kept).toFixed(0)}% variance kept, ${j.prompts.length} prompts`);
  } catch (e) { status(e.message, true); }
}

function addLensItem(j) {
  const div = document.createElement("div");
  div.className = "lens-item";
  const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;");
  div.innerHTML =
    `<b>${j.name}</b><span class="meta">k=${j.k} · ${(100 * j.variance_kept).toFixed(0)}% var · ${j.prompts.length} prompts</span>` +
    `<details class="prompts"><summary>prompts</summary><ul>` +
    j.prompts.map(p => `<li>${esc(p)}</li>`).join("") +
    `</ul></details>`;
  const act = document.createElement("div");
  act.className = "actions";
  const btn = document.createElement("button");
  btn.className = "small"; btn.textContent = "3D view";
  btn.onclick = () => viewLens(j.name);
  act.appendChild(btn);
  div.appendChild(act);
  $("lensList").appendChild(div);
}

/* ---------- actions ---------- */

async function build() {
  status("building graph…");
  try {
    const j = await api("/api/build", {
      a: $("conceptA").value.trim(), b: $("conceptB").value.trim(),
      depth: +$("depth").value, breadth: +$("breadth").value, mode: $("mode").value,
    });
    if (j.error) throw new Error(j.error);
    selection = []; toggleSelect("__none__");
    drawGraph(j);
    status(`graph: ${j.nodes.length} nodes, ${j.edges.length} edges`);
    if (activeLens) viewLens(activeLens);
  } catch (e) { status(e.message, true); }
}

async function interpolate() {
  const [a, b] = selection;
  status(`interpolating ${a} → ${b}…`);
  try {
    const j = await api("/api/interpolate", {
      a, b, steps: 7, top_n: 3, lens: activeLens || undefined,
    });
    $("pathOut").innerHTML = j.path.map(s => {
      const label = s.node
        ? `<b>${s.node}</b> <span class="score">(node)</span>`
        : s.terms.map(([t, sc]) => `${t} <span class="score">${sc.toFixed(2)}</span>`).join(" · ");
      return `<div class="step">t=${s.t} → ${label}</div>`;
    }).join("");
    if (j.coords && activeLens) {
      const pad = (i) => j.coords.map(c => c[i] ?? 0);
      if (pathTrace != null) Plotly.deleteTraces($("plot3d"), pathTrace);
      Plotly.addTraces($("plot3d"), {
        type: "scatter3d", mode: "lines+markers",
        x: pad(0), y: pad(1), z: pad(2),
        line: { color: "#e8934a", width: 5 },
        marker: { size: 4, color: "#e8934a" },
      }).then(() => { pathTrace = 1; });
    }
    status("interpolation done");
  } catch (e) { status(e.message, true); }
}

async function extendPole() {
  const [pole, partner] = selection;
  status(`extending beyond ${pole}…`);
  try {
    const j = await api("/api/extend", { pole, partner, t: 0.6 });
    if (j.node) {
      status(`beyond ${pole}: "${j.node}" — near: ` +
             j.hits.map(([t, s]) => `${t} ${s.toFixed(2)}`).join(", "));
      drawGraph(j.graph);
      if (activeLens) viewLens(activeLens);
    } else status("no concept found beyond pole", true);
  } catch (e) { status(e.message, true); }
}

/* ---------- session save/load ---------- */

async function saveSession() {
  status("saving session…");
  try {
    const j = await api("/api/save", { file: $("saveFile").value.trim() || undefined });
    status(`saved ${j.nodes} nodes + ${j.lenses} lenses → ${j.saved}`);
  } catch (e) { status(e.message, true); }
}

async function loadSession() {
  status("loading session…");
  try {
    const j = await api("/api/load", { file: $("saveFile").value.trim() || undefined });
    selection = []; activeLens = null;
    drawGraph(j.graph);
    $("lensList").innerHTML = "";
    (j.lenses || []).forEach(addLensItem);
    status(`loaded ${j.graph.nodes.length} nodes + ${(j.lenses || []).length} lenses ← ${j.loaded}`);
  } catch (e) { status(e.message, true); }
}

/* ---------- backends ---------- */

const EMBED_BACKENDS = ["auto", "ollama", "lmstudio", "openai", "local", "hash"];
const LLM_BACKENDS = ["auto", "ollama", "lmstudio", "openai", "mock"];
const BACKEND_FIELDS = {
  ollama:   [["url", "endpoint URL (blank = current/default)", ""],
             ["model", "model (blank = env/default)", ""]],
  lmstudio: [["url", "endpoint URL (blank = default :1234)", ""],
             ["model", "model (blank = auto-detect)", ""]],
  openai:   [["key", "API key", ""],
             ["url", "base URL (blank = default)", ""],
             ["model", "model override", ""]],
  local:    [["model", "ST model", "all-MiniLM-L6-v2"]],
  auto: [], hash: [], mock: [],
};

async function loadBackends() {
  try {
    const j = await getJSON("/api/backends");
    fillSel("embedBackend", EMBED_BACKENDS, j.embed, j.active.embed);
    fillSel("llmBackend", LLM_BACKENDS, j.llm, j.active.llm);
    renderCfg("embed"); renderCfg("llm");
  } catch (e) { status("backend probe failed: " + e.message, true); }
}

function fillSel(id, names, avail, active) {
  $(id).innerHTML = names.map(n => {
    const a = (avail && avail[n]) || {};
    const note = n === "auto" ? "first available"
      : a.available ? "✓"
      : n === "openai" ? "needs API key"
      : n === "local" ? "needs sentence-transformers"
      : "not found";
    return `<option value="${n}"${n === active ? " selected" : ""}>${n} — ${note}</option>`;
  }).join("");
}

function renderCfg(kind) {
  const fields = BACKEND_FIELDS[$(kind + "Backend").value] || [];
  $(kind + "Cfg").innerHTML = fields.map(([f, ph, val]) =>
    `<input id="${kind}_${f}"${f === "key" ? ' type="password"' : ""} placeholder="${ph}" value="${val}">`
  ).join("");
}

async function applyBackends() {
  const payload = {};
  for (const kind of ["embed", "llm"]) {
    const name = $(kind + "Backend").value;
    payload[kind] = name;
    for (const [f] of BACKEND_FIELDS[name] || []) {
      const v = $(`${kind}_${f}`).value.trim();
      if (v) payload[`${kind}_${f}`] = v;
    }
  }
  if (payload.embed !== "auto" && payload.embed !== currentEmbed &&
      !confirm("Switching the embedder resets the graph and lenses " +
               "(different vector space). Continue?")) return;
  status("switching backends…");
  try {
    const j = await api("/api/backend", payload);
    currentEmbed = j.embedder;
    refreshBadges(j);
    if (j.reset_graph) {
      selection = []; activeLens = null;
      $("graph2d").innerHTML = ""; $("plot3d").innerHTML = "";
      $("lensList").innerHTML = ""; $("pathOut").innerHTML = "";
    }
    status(`backends: embed ${j.embedder}·${j.embed_model}, llm ${j.llm}` +
           (j.reset_graph ? " (graph reset)" : ""));
    loadBackends();
  } catch (e) { status(e.message, true); }
}

/* ---------- runpod ---------- */

let rpPoll = null;

async function runpodOp(action) {
  try {
    await api("/api/runpod", {
      action,
      key: $("rpKey").value.trim() || undefined,
      gpu: $("rpGpu").value.trim() || undefined,
      pod_id: $("rpPodId").value.trim() || undefined,
    });
    $("rpStatus").textContent = "starting…";
    if (!rpPoll) rpPoll = setInterval(pollRunpod, 4000);
  } catch (e) { $("rpStatus").textContent = e.message; }
}

async function pollRunpod() {
  try {
    const j = await getJSON("/api/runpod");
    $("rpStatus").textContent =
      j.stage === "ready" ? `ready · ${j.url}`
      : j.stage === "error" ? `error: ${j.error}`
      : `${j.stage}${j.detail ? " — " + j.detail : ""}`;
    if (j.stage === "ready") {
      clearInterval(rpPoll); rpPoll = null;
      $("embedBackend").value = "ollama"; $("llmBackend").value = "ollama";
      renderCfg("embed"); renderCfg("llm");
      if ($("embed_url")) $("embed_url").value = j.url;
      if ($("llm_url")) $("llm_url").value = j.url;
      status("pod ready — Apply backends to use it");
      loadBackends();
    } else if (["error", "stopped", "idle"].includes(j.stage)) {
      clearInterval(rpPoll); rpPoll = null;
    }
  } catch (e) { /* transient poll failure */ }
}

/* ---------- boot ---------- */

function refreshBadges(j) {
  const warn = (n) => (n === "hash" || n === "mock") ? " warn" : "";
  $("badges").innerHTML =
    `<span class="badge${warn(j.embedder)}">embed: ${j.embedder} · ${j.embed_model}</span>` +
    `<span class="badge${warn(j.llm)}">llm: ${j.llm}</span>`;
}

async function boot() {
  const j = await getJSON("/api/state");
  refreshBadges(j);
  currentEmbed = j.embedder;
  if (j.graph.nodes.length) drawGraph(j.graph);
  try {
    const l = await getJSON("/api/lenses");
    (l.lenses || []).forEach(addLensItem);
  } catch (e) { /* lens listing unsupported */ }
  loadBackends();
}

$("buildBtn").onclick = build;
$("resetBtn").onclick = async () => { await api("/api/reset"); selection = [];
  $("graph2d").innerHTML = ""; $("plot3d").innerHTML = ""; $("lensList").innerHTML = "";
  $("pathOut").innerHTML = ""; activeLens = null; status("reset"); };
$("interpBtn").onclick = interpolate;
$("extendBtn").onclick = extendPole;
$("lensBtn").onclick = createLens;
$("embedBackend").onchange = () => renderCfg("embed");
$("llmBackend").onchange = () => renderCfg("llm");
$("backendApply").onclick = applyBackends;
$("saveBtn").onclick = saveSession;
$("loadBtn").onclick = loadSession;
$("rpDeploy").onclick = () => runpodOp("deploy");
$("rpResume").onclick = () => runpodOp("resume");
$("rpStop").onclick = () => runpodOp("stop");
$("shutdownBtn").onclick = async () => {
  if (!confirm("Stop the RunPod pod and shut down this server?")) return;
  try {
    const j = await api("/api/shutdown", { pod: "stop" });
    status(j.pod_error
      ? `pod stop failed (${j.pod_error}) — server still exiting`
      : "pod stopped · server exiting — you can close this tab");
  } catch (e) {
    status("server is exiting — you can close this tab");
  }
};

boot();
