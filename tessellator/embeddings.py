"""Pluggable embedding backends with an on-disk cache.

Backend selection (env var TESSELLATOR_EMBED_BACKEND or explicit arg):
    "lmstudio"   -> OpenAI-compatible /v1/embeddings at LMSTUDIO_BASE_URL
    "ollama"     -> Ollama native API at OLLAMA_BASE_URL (auto-starts server)
    "openai"     -> OpenAI API (or any OpenAI-compatible endpoint, e.g. a
                    RunPod pod running vLLM/TEI reached via its proxy URL or
                    an SSH tunnel; set OPENAI_BASE_URL + OPENAI_API_KEY)
    "local"      -> sentence-transformers running in-process
    "hash"       -> deterministic character-n-gram hashing (no deps, weak
                    semantics; fine for dev/testing the math pipeline)
    "auto"       -> first available of: lmstudio, ollama, local, hash
"""

import hashlib
import json
import os
import subprocess
import time
import urllib.request
import urllib.error

import numpy as np

# RunPod's Cloudflare proxy 403s the default python-urllib UA (error 1010).
_HEADERS = {"User-Agent": "curl/8.6.0"}

CACHE_PATH = os.environ.get(
    "TESSELLATOR_CACHE",
    os.path.join(os.path.dirname(__file__), "..", ".cache", "embeddings.json"),
)


def _normalize(v):
    v = np.asarray(v, dtype=np.float64)
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


class _DiskCache:
    def __init__(self, path):
        self.path = path
        self._data = {}
        self._dirty = False
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def key(self, backend, model, text):
        return f"{backend}|{model}|{text}"

    def get(self, key):
        v = self._data.get(key)
        return np.asarray(v, dtype=np.float64) if v is not None else None

    def put(self, key, vec):
        self._data[key] = np.asarray(vec, dtype=np.float64).tolist()
        self._dirty = True

    def flush(self):
        if not self._dirty:
            return
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f)
        self._dirty = False


class BaseEmbedder:
    name = "base"
    model = "unknown"
    dim = None

    def embed_one(self, text):
        raise NotImplementedError

    def embed(self, texts):
        """Embed a string or list of strings -> (n, dim) array, L2-normalized."""
        single = isinstance(texts, str)
        if single:
            texts = [texts]
        out = np.vstack([self.embed_one(t) for t in texts]) if texts else np.zeros((0, 0))
        return out[0] if single else out

    def embed_cached(self, texts, cache):
        single = isinstance(texts, str)
        if single:
            texts = [texts]
        vecs, missing_idx, missing_txt = [], [], []
        for i, t in enumerate(texts):
            v = cache.get(cache.key(self.name, self.model, t))
            if v is None:
                missing_idx.append(i)
                missing_txt.append(t)
                vecs.append(None)
            else:
                vecs.append(v)
        if missing_txt:
            fresh = self.embed(missing_txt)
            for i, t, v in zip(missing_idx, missing_txt, fresh):
                vecs[i] = v
                cache.put(cache.key(self.name, self.model, t), v)
            cache.flush()
        out = np.vstack(vecs)
        return out[0] if single else out


class OpenAICompatEmbedder(BaseEmbedder):
    """Works for LM Studio, OpenAI, and OpenAI-compatible servers (RunPod/vLLM/TEI)."""

    def __init__(self, base_url, api_key, model, name="openai-compat"):
        from openai import OpenAI

        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.name = name

    def embed_one(self, text):
        resp = self.client.embeddings.create(model=self.model, input=text)
        return _normalize(resp.data[0].embedding)

    def embed(self, texts):
        single = isinstance(texts, str)
        if single:
            texts = [texts]
        resp = self.client.embeddings.create(model=self.model, input=texts)
        out = np.vstack([_normalize(d.embedding) for d in resp.data])
        return out[0] if single else out


class OllamaEmbedder(BaseEmbedder):
    """Ollama native API. Auto-starts `ollama serve` and pulls the model if needed."""

    name = "ollama"

    def __init__(self, base_url=None, model=None, autostart=True):
        self.base_url = (base_url or os.environ.get("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
        self.model = model or os.environ.get("OLLAMA_EMBED_MODEL") or "nomic-embed-text"
        if not self._up():
            if not autostart:
                raise ConnectionError(f"Ollama not reachable at {self.base_url}")
            self._start()
        self._ensure_model()

    def _up(self):
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags", headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=2) as r:
                return r.status == 200
        except (urllib.error.URLError, OSError):
            return False

    def _start(self):
        try:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            raise ConnectionError("Ollama not installed and not running at " + self.base_url)
        for _ in range(50):
            if self._up():
                return
            time.sleep(0.2)
        raise ConnectionError("Ollama did not come up at " + self.base_url)

    def _post(self, path, payload):
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", **_HEADERS},
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode("utf-8"))

    def _ensure_model(self):
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags", headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=5) as r:
                tags = json.loads(r.read().decode("utf-8"))
            names = {m.get("name", "").split(":")[0] for m in tags.get("models", [])}
            names |= {m.get("name", "") for m in tags.get("models", [])}
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            names = set()
        if self.model not in names and self.model.split(":")[0] not in names:
            self._post("/api/pull", {"name": self.model, "stream": False})

    def embed_one(self, text):
        return self.embed([text])[0]

    def embed(self, texts):
        single = isinstance(texts, str)
        if single:
            texts = [texts]
        resp = self._post("/api/embed", {"model": self.model, "input": texts})
        out = np.vstack([_normalize(e) for e in resp["embeddings"]])
        return out[0] if single else out


class SentenceTransformerEmbedder(BaseEmbedder):
    name = "local"

    def __init__(self, model=None):
        from sentence_transformers import SentenceTransformer

        self.model = model or os.environ.get("ST_MODEL") or "all-MiniLM-L6-v2"
        self._st = SentenceTransformer(self.model)
        try:
            self.dim = self._st.get_embedding_dimension()
        except AttributeError:
            self.dim = self._st.get_sentence_embedding_dimension()

    def embed_one(self, text):
        return self.embed([text])[0]

    def embed(self, texts):
        single = isinstance(texts, str)
        if single:
            texts = [texts]
        vecs = self._st.encode(list(texts), normalize_embeddings=True, convert_to_numpy=True)
        out = np.asarray(vecs, dtype=np.float64)
        return out[0] if single else out


class HashEmbedder(BaseEmbedder):
    """Deterministic char-n-gram hashing embedder. No model, weak semantics:
    strings sharing words/substrings land near each other. For dev/testing only."""

    name = "hash"

    def __init__(self, dim=384):
        self.dim = dim
        self.model = f"hash-ngram-{dim}"

    def _ngrams(self, text):
        t = f" {text.lower()} "
        grams = set()
        for w in t.split():
            grams.add(w)
            for n in (3, 4):
                for i in range(len(w) - n + 1):
                    grams.add(w[i : i + n])
        return grams

    def embed_one(self, text):
        v = np.zeros(self.dim, dtype=np.float64)
        for g in self._ngrams(text):
            h = int.from_bytes(hashlib.blake2b(g.encode("utf-8"), digest_size=8).digest(), "little")
            idx = h % self.dim
            sign = 1.0 if (h >> 63) == 0 else -1.0
            v[idx] += sign
        return _normalize(v)


def make_embedder(backend="auto", cache_path=None, **kwargs):
    """Return (embedder, cache). backend='auto' probes in a sensible order."""
    cache = _DiskCache(cache_path or CACHE_PATH)
    if not backend or backend == "auto":
        backend = os.environ.get("TESSELLATOR_EMBED_BACKEND") or "auto"
    backend = backend.lower()

    def try_lmstudio():
        url = os.environ.get("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
        try:
            with urllib.request.urlopen(f"{url.rstrip('/')}/models", timeout=2):
                pass
        except (urllib.error.URLError, OSError):
            return None
        model = os.environ.get("LMSTUDIO_EMBED_MODEL")
        if not model:
            from openai import OpenAI

            models = OpenAI(base_url=url, api_key="lm-studio").models.list()
            model = models.data[0].id if models.data else "local_model"
        return OpenAICompatEmbedder(url, "lm-studio", model, name="lmstudio")

    def try_ollama():
        try:
            return OllamaEmbedder(autostart=True)
        except ConnectionError:
            return None

    def try_local():
        try:
            return SentenceTransformerEmbedder(kwargs.get("model"))
        except Exception:
            return None

    builders = {
        "lmstudio": lambda: OpenAICompatEmbedder(
            os.environ.get("LMSTUDIO_BASE_URL", "http://localhost:1234/v1"),
            "lm-studio",
            kwargs.get("model") or os.environ.get("LMSTUDIO_EMBED_MODEL", "local_model"),
            name="lmstudio",
        ),
        "openai": lambda: OpenAICompatEmbedder(
            os.environ.get("OPENAI_EMBED_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or None,
            os.environ.get("OPENAI_API_KEY", ""),
            kwargs.get("model") or os.environ.get("OPENAI_EMBED_MODEL", "text-embedding-3-small"),
            name="openai",
        ),
        "ollama": lambda: OllamaEmbedder(model=kwargs.get("model")),
        "local": lambda: SentenceTransformerEmbedder(kwargs.get("model")),
        "hash": lambda: HashEmbedder(kwargs.get("dim", 384)),
    }

    if backend == "auto":
        for attempt in (try_lmstudio, try_ollama, try_local):
            e = attempt()
            if e is not None:
                return e, cache
        return HashEmbedder(kwargs.get("dim", 384)), cache

    if backend not in builders:
        raise ValueError(f"Unknown embedding backend '{backend}'. Choices: auto, {sorted(builders)}")
    return builders[backend](), cache
