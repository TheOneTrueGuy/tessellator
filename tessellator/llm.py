"""LLM backends for proposing candidate concepts.

Role in the pipeline: the LLM does breadth (propose candidate concepts /
prompt sets), the embedding geometry does orthogonality (filter/rank).
Backend via TESSELLATOR_LLM_BACKEND: lmstudio | ollama | openai | mock | auto
"""

import json
import os
import re
import urllib.request
import urllib.error

# RunPod's Cloudflare proxy 403s the default python-urllib UA (error 1010).
_HEADERS = {"User-Agent": "curl/8.6.0"}

SYSTEM_PROMPT = (
    "You help explore concept spaces. Concepts are treated as poles on axes; "
    "your job is to name concepts perpendicular to a given axis, or concepts "
    "covering a conceptual domain. Reply ONLY with a JSON list of short "
    "concept names (2-5 words each), no commentary."
)


def _parse_list(text):
    """Extract a list of short strings from an LLM reply (JSON or lines)."""
    text = text.strip()
    m = re.search(r"\[.*\]", text, re.S)
    if m:
        try:
            items = json.loads(m.group(0))
            if isinstance(items, list):
                return [str(x).strip() for x in items if str(x).strip()]
        except json.JSONDecodeError:
            pass
    lines = [re.sub(r"^[\-\*\d\.\)\s]+", "", ln).strip() for ln in text.splitlines()]
    return [ln for ln in lines if ln and len(ln) < 80]


class BaseLLM:
    name = "base"

    def chat(self, prompt, temperature=0.3):
        raise NotImplementedError

    def propose_perpendicular(self, concept_a, concept_b, n=8):
        return _parse_list(self.chat(
            f'Considering "{concept_a}" and "{concept_b}" as two points on a line, '
            f"name {n} concepts that are most perpendicular to this line — "
            f"substantially different from both, and from each other.",
            temperature=0.4,
        ))

    def propose_opposite(self, concept):
        r = _parse_list(self.chat(
            f'Name the single concept that most strongly contrasts with or '
            f'opposes "{concept}". Reply with a JSON list containing just that one.',
            temperature=0.2,
        ))
        return r[0] if r else None

    def propose_prompt_set(self, concept, n=24):
        """Coverage prompt set for building a ConceptLens on `concept`."""
        return _parse_list(self.chat(
            f'List {n} distinct values or types of "{concept}" that together '
            f"cover the concept broadly (like a taxonomy).",
            temperature=0.4,
        ))

    def name_region(self, near_terms):
        r = _parse_list(self.chat(
            f"What single short concept name best captures the region described "
            f"by these nearby concepts: {', '.join(near_terms)}? JSON list of one.",
            temperature=0.3,
        ))
        return r[0] if r else None


class OpenAICompatLLM(BaseLLM):
    def __init__(self, base_url, api_key, model, name="openai-compat"):
        from openai import OpenAI

        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.name = name

    def chat(self, prompt, temperature=0.3):
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
        )
        return resp.choices[0].message.content


class OllamaLLM(BaseLLM):
    name = "ollama"

    def __init__(self, base_url=None, model=None):
        self.base_url = (base_url or os.environ.get("OLLAMA_BASE_URL")
                         or "http://localhost:11434").rstrip("/")
        self.model = model or os.environ.get("OLLAMA_CHAT_MODEL") or "llama3.2"

    def chat(self, prompt, temperature=0.3):
        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps({
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "options": {"temperature": temperature},
            }).encode("utf-8"),
            headers={"Content-Type": "application/json", **_HEADERS},
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode("utf-8"))["message"]["content"]


class MockLLM(BaseLLM):
    """Deterministic stand-in: proposes candidates from the starter vocab
    plus generic fillers. Lets the whole pipeline run with no LLM at all."""
    name = "mock"

    def __init__(self, vocab_terms=()):
        self._terms = list(vocab_terms)

    def chat(self, prompt, temperature=0.3):
        return json.dumps(self._terms[:10])

    def propose_perpendicular(self, concept_a, concept_b, n=8):
        a, b = concept_a.lower(), concept_b.lower()
        picks = [t for t in self._terms
                 if a not in t.lower() and b not in t.lower()
                 and t.lower() not in (a, b)]
        return picks[:n]

    def propose_opposite(self, concept):
        return f"not-{concept}"

    def propose_prompt_set(self, concept, n=24):
        return [t for t in self._terms if t.lower() != concept.lower()][:n]


def make_llm(backend="auto", vocab_terms=(), **kwargs):
    if not backend or backend == "auto":
        backend = os.environ.get("TESSELLATOR_LLM_BACKEND") or "auto"
    backend = backend.lower()

    def lmstudio():
        url = os.environ.get("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
        try:
            with urllib.request.urlopen(f"{url.rstrip('/')}/models", timeout=2):
                pass
        except (urllib.error.URLError, OSError):
            return None
        from openai import OpenAI

        model = os.environ.get("LMSTUDIO_CHAT_MODEL")
        if not model:
            models = OpenAI(base_url=url, api_key="lm-studio").models.list()
            model = models.data[0].id if models.data else "local_model"
        return OpenAICompatLLM(url, "lm-studio", model, name="lmstudio")

    def ollama():
        url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        try:
            req = urllib.request.Request(f"{url.rstrip('/')}/api/tags", headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=2):
                pass
        except (urllib.error.URLError, OSError):
            return None
        return OllamaLLM(base_url=url, model=kwargs.get("model"))

    def openai_():
        if not os.environ.get("OPENAI_API_KEY"):
            return None
        return OpenAICompatLLM(
            os.environ.get("OPENAI_CHAT_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or None,
            os.environ["OPENAI_API_KEY"],
            kwargs.get("model") or os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
            name="openai",
        )

    if backend == "auto":
        for attempt in (lmstudio, ollama, openai_):
            llm = attempt()
            if llm is not None:
                return llm
        return MockLLM(vocab_terms)

    explicit = {
        "lmstudio": lmstudio, "ollama": ollama, "openai": openai_,
        "mock": lambda: MockLLM(vocab_terms),
    }
    if backend not in explicit:
        raise ValueError(f"Unknown LLM backend '{backend}'")
    llm = explicit[backend]()
    if llm is None:
        raise ConnectionError(f"LLM backend '{backend}' requested but not available")
    return llm
