# Tessellator — dev notes & backlog

## Where things stand (2026-10-26)

Working end-to-end: local Flask UI + RunPod pod doing all model work.

- **Pod**: `cg3rnjuzxrcam6`, RTX 2000 Ada 16GB, secure cloud, ~$0.24/hr.
  (redeployed 2026-10-27 via `pod_ctl.py deploy` after the original pod's host
  ran out of GPU capacity; fresh disk → models had to be re-pulled)
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
- RunPod proxy URLs are unauthenticated — anyone with the URL can use the pod. Stop it when idle.
- `TESSELLATOR_*_BACKEND` env vars only take effect when the passed backend is `auto`/unset (fixed).
- Frontend libs are vendored in `static/vendor/` (CDN 404 + offline robustness). Don't re-add CDN links.

## Backlog / ideas

### Next session
- [ ] Try the concept-lens 3D view: create a lens (name + concept, e.g. "formality"), hit "3D view" to project the graph into the PCA subspace.
- [x] Commit everything — done 2026-10-27 (`75c97b5`). NOTE: this file contains the pod ID, which is enough to reconstruct the unauthenticated proxy URL — redact before pushing if the repo is public.

### Features
- [ ] **Save/load state**: `Tessellator.from_json()` exists (builder.py) but has no API endpoints or UI. Add `/api/save`, `/api/load`, buttons; persist graph + lenses + `_vecs`.
- [ ] **Lens persistence**: lenses currently live in memory only; rebuild on restart needs LLM + embed calls again.
- [ ] **Restore lenses in UI on boot**: server keeps `t.lenses` across page reloads but `boot()` doesn't re-render lens items, and `/api/state` returns only names. Add `GET /api/lenses` (name, k, variance, prompts — so items render without re-embedding or re-generating) and populate `lensList` in `boot()`.
- [ ] Session autosave to `.cache/graph.json`.
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
