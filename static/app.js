/* Tessellator frontend */
const $ = (id) => document.getElementById(id);

let network = null, nodesDS = null, edgesDS = null;
let selection = [];            // ordered, max 2
let activeLens = null;
let pathTrace = null;          // interpolation polyline in the 3D view

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
  div.innerHTML =
    `<b>${j.name}</b><span class="meta">k=${j.k} · ${(100 * j.variance_kept).toFixed(0)}% var · ${j.prompts.length} prompts</span>`;
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

/* ---------- boot ---------- */

async function boot() {
  const j = await getJSON("/api/state");
  const warn = (n) => (n === "hash" || n === "mock") ? " warn" : "";
  $("badges").innerHTML =
    `<span class="badge${warn(j.embedder)}">embed: ${j.embedder} · ${j.embed_model}</span>` +
    `<span class="badge${warn(j.llm)}">llm: ${j.llm}</span>`;
  if (j.graph.nodes.length) drawGraph(j.graph);
}

$("buildBtn").onclick = build;
$("resetBtn").onclick = async () => { await api("/api/reset"); selection = [];
  $("graph2d").innerHTML = ""; $("plot3d").innerHTML = ""; $("lensList").innerHTML = "";
  $("pathOut").innerHTML = ""; activeLens = null; status("reset"); };
$("interpBtn").onclick = interpolate;
$("extendBtn").onclick = extendPole;
$("lensBtn").onclick = createLens;
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
