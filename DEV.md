# Tessellator — dev notes & backlog

## Where things stand (2026-10-27)

Working end-to-end: local Flask UI + pluggable model backends (RunPod Ollama
pod, local Ollama, LM Studio, OpenAI-compatible, hash/mock demo mode) — picked
via env vars, CLI flags, or the live-probing *Backends* section in the UI.
Setup docs in SETUP.md.

- **Pod**: none running (last one terminated 2026-10-27 after its id was
  pushed to a public repo — the proxy URL is unauthenticated). Recreate via
  `pod_ctl.py deploy` (see spec below), update `runpod.env` +
  `.venv/pod_id.txt`. **Never put a pod id in tracked files.**
  Ollama serving `qwen2.5:7b` (chat) + `nomic-embed-text` (embeddings).
  Control: `.venv/Scripts/python pod_ctl.py status|stop|start|terminate`
  `stop` keeps the disk (models stay cached, ~pennies/day); `terminate` deletes everything.
- **Run locally**: `./run_app.sh` (sources `runpod.env`, launches `app.py` → http://localhost:5000)
- **Shutdown**: the "Shutdown" button (header, top-right) stops the pod (resumable) then exits the server. `/api/shutdown` accepts `{"pod": "stop"|"terminate"|"none"}`.
- **Secrets**: RunPod API key in `.venv/runpod_key.txt`, pod token/id in `.venv/*.txt` — all gitignored along with `runpod.env`.
- **Embedding cache**: `.cache/embeddings.json`, keyed `backend|model|text` — persists across backend swaps.

### Pod spec (captured 2026-10-27 via `pod_ctl.py spec`)
Recreate on RunPod secure cloud: image `ollama/ollama:latest`, port `11434/http`,
env `OLLAMA_HOST=0.0.0.0`, 1x RTX 2000 Ada, 6 vCPU / 31GB RAM, **40GB container
disk, no volume** — models die with `terminate`. After creating a new pod:
1. `.venv/pod_id.txt` ← new pod id; `runpod.env` `OLLAMA_BASE_URL` ← `https://<id>-11434.proxy.runpod.net`
2. Wait for ollama up, then pull models over HTTP:
   `curl <base>/api/pull -d '{"name":"qwen2.5:7b"}'` and `{"name":"nomic-embed-text"}`

### Gotchas discovered
- `vllm/vllm-openai` pod image has **no sshd** — can't exec into it. That's why we're on Ollama (serves chat + embeddings on one port, models pulled via `/api/pull` over HTTP).
- RunPod's Cloudflare proxy **403s `python-urllib`** UA — all urllib calls send `User-Agent: curl/8.6.0`.
- RunPod proxy URLs are unauthenticated — anyone with the URL can use the pod.
  The pod id alone is enough to build the URL, so it must stay out of tracked
  files (learned the hard way 2026-10-27: id sat in DEV.md on a public repo,
  pod had to be terminated). Stop pods when idle.
- `TESSELLATOR_*_BACKEND` env vars only take effect when the passed backend is `auto`/unset (fixed).
- Frontend libs are vendored in `static/vendor/` (CDN 404 + offline robustness). Don't re-add CDN links.

## Backlog / ideas

### Next session
- [x] Try the concept-lens 3D view — works; tested with auto-generated "practical applications" prompt set.
- [x] Commit everything — pushed to origin/main 2026-10-27.

### Features
- [x] **Save/load state**: `/api/save`, `/api/load` + UI buttons (2026-10-27). Saves graph + lenses to `.cache/session.json`; lenses restore with no embed calls (basis/mean serialized), node vecs re-embed via disk cache. Refuses on embedder mismatch.
- [x] **Lens persistence**: serialized in the session file via `ConceptLens.to_dict`/`from_dict`.
- [x] **Restore lenses in UI on boot**: `GET /api/lenses` exists; `boot()` re-renders lens items.
- [x] Session autosave → `.cache/session-autosave.json` on shutdown.
- [x] RunPod in UI: deploy/resume/stop via `POST /api/runpod` with user-supplied key (memory only).
- [ ] Export: graph GEXF/GraphML for Gephi (`.gexf` already gitignored — suggests this was intended).
- [ ] Lens-aware edge weighting — `lens_similarities()` exists, unused by UI.
- [ ] Interpolation path visualization already works in 3D; consider nearest-node snapping display.

### Infra / models
- [ ] Bigger embedding model on the pod (e.g. `bge-m3`, `mxbai-embed-large`) — pull via `POST /api/pull`, set `OLLAMA_EMBED_MODEL`. Cache keys are model-scoped so no invalidation needed.
- [ ] Bigger/better chat model if proposals feel thin (`qwen2.5:14b` fits 16GB quantized; or bump GPU).
- [ ] Consider RunPod network volume to make model cache survive `terminate`.
- [ ] Optional: auth in front of the ollama endpoint (nginx + token) if pod lives long.
- [ ] Auth-free alternative for embeddings if pod is down: `local` backend works but loads torch on the laptop (the thing that crashed it — prefer the pod).

### Code quality
- [ ] `OpenAICompat` paths still send default httpx UA — may hit the same Cloudflare 1010 block if pointed at a RunPod proxy. Untested.
- [ ] `_DiskCache` holds everything in memory; fine now, watch for bloat.
- [ ] No tests at all.
