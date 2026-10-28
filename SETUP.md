# Tessellator — setup & usage

Flask UI + `tessellator` package for exploring concept space with embedding
geometry: seed an axis between two concepts, expand perpendicular concepts
around it into a graph, project the graph through "concept lenses" (PCA
subspaces built from prompt sets), and interpolate between nodes with
reverse-token lookup.

All model work (chat + embeddings) is delegated to pluggable backends: a
RunPod Ollama pod, local Ollama, LM Studio, OpenAI-compatible endpoints, or
dependency-free hash/mock fallbacks for dev.

## Requirements

- Python 3.10+ (developed on 3.14)
- `pip install -r requirements.txt`
- Optional in-process embedder: `pip install sentence-transformers`
  (pulls torch — only needed for `TESSELLATOR_EMBED_BACKEND=local`)

## Backends

Selected three ways, in order of precedence:

1. **In the UI** — the *Backends* section (sidebar, bottom) probes what's
   reachable, marks detected backends with ✓, and lets you switch live.
   Paste an endpoint URL (e.g. a RunPod proxy URL for `ollama`) or an
   OpenAI API key right there. Switching the **embedder resets the graph**
   (new vector space); the llm swaps freely. `hash`/`mock` need no models
   at all — that's demo mode. The **RunPod** expander can also deploy /
   resume / stop a pod for you: paste your API key (kept in server memory
   only, never written to disk or committed), and it deploys the pod, waits
   for Ollama, pulls the models, and pre-fills the ollama URL.
2. **CLI flags** — `python app.py --embed-backend ollama --llm-backend openai \
   --ollama-url https://<id>-11434.proxy.runpod.net [--port 5000]`
   (`run_app.sh` forwards args, e.g. `./run_app.sh --llm-backend mock`).
3. **Env vars** — `TESSELLATOR_EMBED_BACKEND` / `TESSELLATOR_LLM_BACKEND`
   (`auto` by default: embedder probes lmstudio → ollama → local → hash;
   llm probes lmstudio → ollama → openai → mock).

| Backend | Embed env vars | LLM env vars | Notes |
|---|---|---|---|
| `ollama` | `OLLAMA_BASE_URL` (default `http://localhost:11434`), `OLLAMA_EMBED_MODEL` | `OLLAMA_BASE_URL`, `OLLAMA_CHAT_MODEL` | pod or local install; embed model auto-pulls on first use, chat model must exist |
| `lmstudio` | `LMSTUDIO_BASE_URL` (default `http://localhost:1234/v1`), `LMSTUDIO_EMBED_MODEL` | `LMSTUDIO_CHAT_MODEL` | auto-detects the first loaded model |
| `openai` | `OPENAI_BASE_URL` / `OPENAI_EMBED_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_EMBED_MODEL` | `OPENAI_CHAT_BASE_URL`, `OPENAI_CHAT_MODEL` | any OpenAI-compatible endpoint (RunPod vLLM/TEI, SSH tunnel, …) |
| `local` | `ST_MODEL` (default `all-MiniLM-L6-v2`) | — | needs `sentence-transformers` |
| `hash` / `mock` | — | — | no models, deterministic, weak semantics; dev only |

## Path A — RunPod pod (the setup this repo was developed with)

Pod lifecycle lives in `pod_ctl.py`; secrets in gitignored files:

    .venv/runpod_key.txt   RunPod API key
    .venv/pod_id.txt       pod id (written by `deploy`)

Commands (from repo root, Windows Git Bash):

    .venv/Scripts/python pod_ctl.py deploy      # create pod (RTX 2000 Ada;
                                                # `deploy "4000 Ada"` etc. for other GPUs)
    .venv/Scripts/python pod_ctl.py status | start | stop | terminate | spec | url

`stop` keeps the disk (models stay cached, ~pennies/day). `terminate` deletes
pod + disk — a fresh deploy then needs the models re-pulled over HTTP (fast
on datacenter bandwidth):

    curl https://<pod-id>-11434.proxy.runpod.net/api/pull -d '{"name":"qwen2.5:7b"}'
    curl https://<pod-id>-11434.proxy.runpod.net/api/pull -d '{"name":"nomic-embed-text"}'

`runpod.env` (gitignored) holds the env vars, `run_app.sh` sources it and
launches the server:

    OLLAMA_BASE_URL=https://<pod-id>-11434.proxy.runpod.net
    OLLAMA_CHAT_MODEL=qwen2.5:7b
    OLLAMA_EMBED_MODEL=nomic-embed-text
    TESSELLATOR_EMBED_BACKEND=ollama
    TESSELLATOR_LLM_BACKEND=ollama

    ./run_app.sh        # → http://localhost:5000

**Security:** RunPod proxy URLs are unauthenticated — anyone with the URL can
use (and administer) the pod, and the pod id alone is enough to construct it.
Keep ids out of tracked files (gitignore covers `runpod.env` and `.venv/`);
stop the pod when idle.

## Path B — no pod

- **Local Ollama**: install ollama; the app auto-starts `ollama serve` and
  auto-pulls the embed model on first use. Point `OLLAMA_BASE_URL` at
  `http://localhost:11434` or leave it unset and let `auto` find it.
- **LM Studio**: start its server, load an embed + a chat model. `auto`
  finds it at `http://localhost:1234/v1`.
- **Pure dev** (no models at all):

      TESSELLATOR_EMBED_BACKEND=hash TESSELLATOR_LLM_BACKEND=mock .venv/Scripts/python app.py

## Using the UI

1. **Seed axis**: pole A / pole B, depth, breadth, mode.
   - `hybrid` (default): LLM proposes candidates, embedding geometry ranks
     and dedupes them by orthogonality to the axis.
   - `llm`: raw LLM suggestions, unfiltered.
   - `geometric`: sample directions orthogonal to the axis in embedding
     space, reverse-lookup nearest vocab concepts (no LLM).
2. **Build graph**. Double-click a node to expand it; click nodes to select
   up to 2.
3. **Interpolate**: slerp between the two selected embeddings, reverse-token
   lookup at each step (results in the left panel, polyline in the 3D view
   if a lens is active).
4. **Extend**: step past the selected pole along the axis, add the nearest
   concept as a `beyond-pole` node.
5. **Concept lenses**: name + concept (LLM generates a ~24-term coverage
   prompt set) **or** paste prompts one per line — a shared template with
   one varying slot gives the cleanest subspace. `k` blank = auto (smallest
   k keeping `var` fraction of variance). "3D view" projects all graph
   nodes into the lens; expand **prompts** on the lens item to inspect the
   generated set.
6. **Session save/load** (top of the sidebar): Save writes graph + lenses to
   `.cache/session.json` (or a name you give). Load restores them — lenses
   come back with no embedding calls (their basis/mean serialize), node
   vectors re-embed through the disk cache. Loading refuses if the active
   embedder differs from the session's (different vector space) — switch
   backends first. The Shutdown button also autosaves to
   `session-autosave.json`.
7. **Shutdown** button: stops the pod (disk kept, resumable) then exits the
   server. `POST /api/shutdown` accepts `{"pod": "stop"|"terminate"|"none"}`.

## Repo layout

    app.py                  Flask server + REST API
    pod_ctl.py              RunPod lifecycle (deploy/start/stop/terminate/spec)
    run_app.sh              source runpod.env + launch app.py
    tessellator/            package: builder (graph), geometry, lens,
                            embeddings, llm, vocab
    templates/, static/     UI (vis-network + plotly vendored, no CDN)
    .cache/embeddings.json  disk embedding cache (keys: backend|model|text)
    Lenses/                 reference article on prompted subspaces
    DEV.md                  dev notes + backlog
    tessel*.py, index.html, web_interface2_app.py   earlier prototypes

## Gotchas

- RunPod's Cloudflare proxy 403s the default `python-urllib` user agent —
  all urllib calls send `User-Agent: curl/8.6.0`
  (`_HEADERS` in `tessellator/embeddings.py` / `llm.py`). The `openai`
  client paths do not do this yet.
- The `vllm/vllm-openai` pod image has no sshd — that's why the pod runs
  `ollama/ollama` (chat + embeddings on one port, models pulled via
  `/api/pull` over HTTP).
- Embedding cache keys are model-scoped — swapping models needs no
  invalidation, old entries are simply unused.
