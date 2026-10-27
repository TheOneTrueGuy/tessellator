"""Tessellator Flask server.

Run:  .venv/Scripts/python app.py           (Windows)
      .venv/bin/python app.py               (posix)
Then open http://localhost:5000

Config via env vars (see tessellator/embeddings.py and tessellator/llm.py):
  TESSELLATOR_EMBED_BACKEND  auto|lmstudio|ollama|openai|local|hash
  TESSELLATOR_LLM_BACKEND    auto|lmstudio|ollama|openai|mock
"""

import importlib.util
import os
import threading
import time
import traceback
import urllib.request

import numpy as np
from flask import Flask, jsonify, render_template, request

from tessellator.builder import Tessellator
from tessellator.embeddings import _HEADERS, make_embedder
from tessellator.llm import make_llm
from tessellator.vocab import load_vocab

app = Flask(__name__)

_T = None          # Tessellator instance (lazy)
_EMB = None        # embedder
_LLM = None        # llm


def tessellator():
    global _T, _EMB, _LLM
    if _T is None:
        _EMB, cache = make_embedder("auto")
        _LLM = make_llm("auto", vocab_terms=load_vocab())
        _T = Tessellator(_EMB, cache, _LLM)
    return _T


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state")
def state():
    t = tessellator()
    return jsonify({
        "embedder": _EMB.name, "embed_model": _EMB.model,
        "llm": _LLM.name, "llm_model": getattr(_LLM, "model", "-"),
        "graph": t.to_json(),
    })


def _err(fn):
    try:
        return fn()
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"{type(e).__name__}: {e}"}), 400


@app.route("/api/build", methods=["POST"])
def build():
    def go():
        d = request.json
        t = tessellator()
        t.build(d["a"], d["b"],
                max_depth=int(d.get("depth", 2)),
                breadth=int(d.get("breadth", 4)),
                mode=d.get("mode", "hybrid"),
                max_nodes=int(d.get("max_nodes", 150)))
        return jsonify(t.to_json())
    return _err(go)


@app.route("/api/expand", methods=["POST"])
def expand():
    def go():
        d = request.json
        t = tessellator()
        added = t.expand_node(d["node"], breadth=int(d.get("breadth", 4)),
                              mode=d.get("mode", "hybrid"))
        return jsonify({"added": added, "graph": t.to_json()})
    return _err(go)


@app.route("/api/extend", methods=["POST"])
def extend():
    def go():
        d = request.json
        t = tessellator()
        node, hits = t.extend_pole(d["pole"], d["partner"], t=float(d.get("t", 0.6)))
        return jsonify({"node": node, "hits": hits, "graph": t.to_json()})
    return _err(go)


@app.route("/api/lens", methods=["POST"])
def lens():
    def go():
        d = request.json
        t = tessellator()
        prompts = d.get("prompts")
        if isinstance(prompts, str):
            prompts = [p.strip() for p in prompts.splitlines() if p.strip()]
        l = t.make_lens(d["name"], prompts=prompts or None,
                        concept=d.get("concept"),
                        k=int(d["k"]) if d.get("k") else None,
                        variance_keep=float(d.get("variance_keep", 0.80)))
        return jsonify({"name": l.name, "k": l.k, "prompts": l.prompts,
                        "variance_kept": l.variance_kept,
                        "components": l.top_components()})
    return _err(go)


@app.route("/api/project", methods=["POST"])
def project():
    def go():
        t = tessellator()
        lname = request.json["lens"]
        lens = t.lenses[lname]
        coords = t.project_graph(lname)
        return jsonify({"lens": lname, "k": lens.k,
                        "variance_kept": lens.variance_kept,
                        "coords": coords})
    return _err(go)


@app.route("/api/interpolate", methods=["POST"])
def interpolate():
    def go():
        d = request.json
        t = tessellator()
        path = t.interpolate(d["a"], d["b"], steps=int(d.get("steps", 7)),
                             top_n=int(d.get("top_n", 3)))
        out = {"path": path}
        if d.get("lens") and d["lens"] in t.lenses:
            from tessellator import geometry as G
            va, vb = t._embed_term(d["a"]), t._embed_term(d["b"])
            pts = G.slerp(va, vb, steps=int(d.get("steps", 7)))
            lens = t.lenses[d["lens"]]
            out["coords"] = lens.project(pts).tolist()
        return jsonify(out)
    return _err(go)


@app.route("/api/candidates", methods=["POST"])
def candidates():
    """Preview perpendicular candidates for an axis without mutating the graph."""
    def go():
        d = request.json
        t = tessellator()
        mode = d.get("mode", "geometric")
        n = int(d.get("n", 8))
        if mode == "geometric":
            cands = t.geometric_candidates(d["a"], d["b"], n=n)
        else:
            cands = t.llm_candidates(d["a"], d["b"], n=n)
        return jsonify({"candidates": cands})
    return _err(go)


@app.route("/api/reset", methods=["POST"])
def reset():
    def go():
        t = tessellator()
        t.graph.clear()
        t.lenses.clear()
        return jsonify({"ok": True})
    return _err(go)


def _reachable(url, path):
    try:
        req = urllib.request.Request(url.rstrip("/") + path, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=2):
            return True
    except Exception:
        return False


@app.route("/api/backends")
def backends():
    """Probe which backends are reachable right now + what's active."""
    ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    lms_url = os.environ.get("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
    ollama_up = _reachable(ollama_url, "/api/tags")
    lms_up = _reachable(lms_url, "/models")
    has_key = bool(os.environ.get("OPENAI_API_KEY"))
    has_st = importlib.util.find_spec("sentence_transformers") is not None
    remote = {
        "ollama": {"available": ollama_up, "url": ollama_url},
        "lmstudio": {"available": lms_up, "url": lms_url},
        "openai": {"available": has_key},
    }
    return jsonify({
        "active": {
            "embed": _EMB.name if _EMB else None,
            "embed_model": _EMB.model if _EMB else None,
            "llm": _LLM.name if _LLM else None,
            "llm_model": getattr(_LLM, "model", None) if _LLM else None,
        },
        "embed": {**remote, "local": {"available": has_st},
                  "hash": {"available": True}, "auto": {"available": True}},
        "llm": {**remote, "mock": {"available": True}, "auto": {"available": True}},
    })


_URL_ENV = {"ollama": "OLLAMA_BASE_URL", "lmstudio": "LMSTUDIO_BASE_URL",
            "openai": "OPENAI_BASE_URL"}
_MODEL_ENV = {
    "embed": {"ollama": "OLLAMA_EMBED_MODEL", "lmstudio": "LMSTUDIO_EMBED_MODEL",
              "openai": "OPENAI_EMBED_MODEL", "local": "ST_MODEL"},
    "llm": {"ollama": "OLLAMA_CHAT_MODEL", "lmstudio": "LMSTUDIO_CHAT_MODEL",
            "openai": "OPENAI_CHAT_MODEL"},
}


@app.route("/api/backend", methods=["POST"])
def set_backend():
    """Switch embed/llm backends at runtime. An embedder change means a new
    vector space, so it clears the graph, _vecs, and lenses."""
    def go():
        global _EMB, _LLM
        d = request.json
        t = tessellator()
        for kind in ("embed", "llm"):
            name = d.get(kind)
            if not name or name == "auto":
                continue
            if name in _URL_ENV and d.get(f"{kind}_url"):
                os.environ[_URL_ENV[name]] = d[f"{kind}_url"].strip()
            if d.get(f"{kind}_key"):
                os.environ["OPENAI_API_KEY"] = d[f"{kind}_key"].strip()
            menv = _MODEL_ENV[kind].get(name)
            if menv and d.get(f"{kind}_model"):
                os.environ[menv] = d[f"{kind}_model"].strip()

        new_emb = new_cache = new_llm = None
        if d.get("embed"):
            new_emb, new_cache = make_embedder(d["embed"],
                                               model=d.get("embed_model") or None)
        if d.get("llm"):
            new_llm = make_llm(d["llm"], vocab_terms=load_vocab(),
                               model=d.get("llm_model") or None)
        result = {"reset_graph": False}
        if new_emb and (new_emb.name != _EMB.name or new_emb.model != _EMB.model):
            _EMB = new_emb
            t.embedder, t.cache = new_emb, new_cache
            t.graph.clear()
            t._vecs.clear()
            t.lenses.clear()
            t._vocab_vecs = None
            t._vocab_dirty = True
            result["reset_graph"] = True
        if new_llm:
            _LLM = t.llm = new_llm
        result.update({
            "embedder": _EMB.name, "embed_model": _EMB.model,
            "llm": _LLM.name, "llm_model": getattr(_LLM, "model", "-"),
            "reset_graph": result["reset_graph"],
        })
        return jsonify(result)
    return _err(go)


@app.route("/api/shutdown", methods=["POST"])
def shutdown():
    """Stop the RunPod pod (disk kept for fast resume) then exit this server.
    Body: {"pod": "stop"|"terminate"|"none"} — default "stop"."""
    action = (request.json or {}).get("pod", "stop")
    result = {"pod": action}
    if action in ("stop", "terminate"):
        try:
            import pod_ctl
            (pod_ctl.stop if action == "stop" else pod_ctl.terminate)()
        except Exception as e:
            result["pod_error"] = f"{type(e).__name__}: {e}"

    def die():
        time.sleep(0.5)
        os._exit(0)

    threading.Thread(target=die, daemon=True).start()
    return jsonify(result)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Tessellator UI server")
    p.add_argument("--embed-backend", help="auto|ollama|lmstudio|openai|local|hash")
    p.add_argument("--llm-backend", help="auto|ollama|lmstudio|openai|mock")
    p.add_argument("--ollama-url", help="OLLAMA_BASE_URL, e.g. a RunPod proxy URL")
    p.add_argument("--port", type=int, default=5000)
    args = p.parse_args()
    if args.ollama_url:
        os.environ["OLLAMA_BASE_URL"] = args.ollama_url
    if args.embed_backend:
        os.environ["TESSELLATOR_EMBED_BACKEND"] = args.embed_backend
    if args.llm_backend:
        os.environ["TESSELLATOR_LLM_BACKEND"] = args.llm_backend
    app.run(debug=True, port=args.port)
