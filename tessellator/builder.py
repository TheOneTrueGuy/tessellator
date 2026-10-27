"""Hybrid tessellator graph builder.

Expansion strategies for the axis a<->b:
  "llm"       - raw LLM perpendicular suggestions (the original approach)
  "geometric" - sample directions orthogonal to the axis in embedding space,
                reverse-lookup nearest vocabulary concepts (no LLM)
  "hybrid"    - LLM proposes candidates, geometry ranks + dedupes them
                (breadth from the model, orthogonality from the math)
"""

import numpy as np
import networkx as nx

from . import geometry
from .lens import ConceptLens
from .vocab import load_vocab


class Tessellator:
    def __init__(self, embedder, cache, llm=None, extra_vocab=()):
        self.embedder = embedder
        self.cache = cache
        self.llm = llm
        self.graph = nx.Graph()
        self._vecs = {}                    # node -> embedding
        self._vocab_terms = []
        self._vocab_vecs = None
        self._extra_vocab = list(extra_vocab)
        self.lenses = {}

    # ---------- internals ----------

    def _embed_term(self, term):
        term = term.strip()
        if term not in self._vecs:
            self._vecs[term] = self.embedder.embed_cached(term, self.cache)
        return self._vecs[term]

    def _add_node(self, term, **attrs):
        self._embed_term(term)
        if term in self.graph:
            self.graph.nodes[term].update(attrs)
        else:
            self.graph.add_node(term, **attrs)
        self._vocab_dirty = True

    def _vocab(self):
        if getattr(self, "_vocab_dirty", True) or self._vocab_vecs is None:
            self._vocab_terms = load_vocab(
                extra_terms=list(self._extra_vocab) + list(self.graph.nodes)
            )
            self._vocab_vecs = self.embedder.embed_cached(self._vocab_terms, self.cache)
            self._vocab_dirty = False
        return self._vocab_terms, self._vocab_vecs

    def _reverse_lookup(self, point_vecs, top_n=3, exclude=()):
        terms, vecs = self._vocab()
        return geometry.nearest_concepts(point_vecs, vecs, terms, top_n, exclude)

    # ---------- candidate generation ----------

    def geometric_candidates(self, a, b, n=8, spread=1.0, rng=None):
        """Sample n points whose offset from the midpoint is purely orthogonal
        to the a<->b axis; reverse-lookup the nearest vocab concepts."""
        rng = rng or np.random.default_rng()
        va, vb = self._embed_term(a), self._embed_term(b)
        m, v = geometry.midpoint(va, vb), geometry.axis_vector(va, vb)
        dim = len(v)
        R = rng.normal(size=(n * 2, dim))                    # oversample
        R = R - np.outer(R @ v, v)                           # kill axial part
        R = R - np.outer(R @ m, m)                           # and radial part
        R = geometry.normalize(R)
        pts = geometry.normalize(m[None, :] + spread * R)    # around midpoint
        hits = self._reverse_lookup(pts, top_n=1, exclude=(a, b))
        cands, seen = [], set()
        for h in hits:
            if h and h[0][0].lower() not in seen:
                seen.add(h[0][0].lower())
                cands.append(h[0][0])
        return cands[:n]

    def llm_candidates(self, a, b, n=8):
        if self.llm is None:
            return []
        return [c for c in self.llm.propose_perpendicular(a, b, n=n) if c]

    # ---------- expansion ----------

    def expand_axis(self, a, b, breadth=4, mode="hybrid", depth=0):
        """Add perpendicular nodes connected to both poles of axis a<->b.
        Returns list of added node names."""
        va, vb = self._embed_term(a), self._embed_term(b)

        candidates = []
        if mode in ("hybrid", "llm"):
            candidates += self.llm_candidates(a, b, n=2 * breadth)
        if mode == "geometric" or (mode == "hybrid" and len(candidates) < breadth):
            candidates += self.geometric_candidates(a, b, n=2 * breadth)
        candidates = [c for c in dict.fromkeys(candidates)
                      if c and c.lower() not in {a.lower(), b.lower()}]
        if not candidates:
            return []

        if mode == "llm":
            chosen = candidates[:breadth]
            for i, c in enumerate(chosen):
                self._add_node(c, depth=depth + 1, perp_score=None)
                self.graph.add_edge(a, c, kind="perp")
                self.graph.add_edge(b, c, kind="perp")
            return chosen

        cvecs = self.embedder.embed_cached(candidates, self.cache)
        scores, residuals = geometry.perpendicular_scores(cvecs, va, vb)
        order = np.argsort(scores)[::-1]
        keep_dirs = set(geometry.dedupe_directions(residuals[order], cos_thresh=0.75))
        chosen_idx = [order[i] for i in range(len(order)) if i in keep_dirs][:breadth]

        added = []
        for i in chosen_idx:
            c = candidates[i]
            self._add_node(c, depth=depth + 1, perp_score=float(scores[i]))
            self.graph.add_edge(a, c, kind="perp")
            self.graph.add_edge(b, c, kind="perp")
            added.append(c)
        return added

    def build(self, concept_a, concept_b, max_depth=2, breadth=4,
              mode="hybrid", max_nodes=150):
        """Seed an axis and recursively tessellate. Each perpendicular p spawns
        child axes (a, p) and (b, p), matching the original recursive design."""
        self.graph.clear()
        self._add_node(concept_a, depth=0, role="pole")
        self._add_node(concept_b, depth=0, role="pole")
        self.graph.add_edge(concept_a, concept_b, kind="axis")
        self._vocab_dirty = True

        queue = [(concept_a, concept_b, 0)]
        seen_axes = {tuple(sorted((concept_a.lower(), concept_b.lower())))}
        while queue and self.graph.number_of_nodes() < max_nodes:
            a, b, depth = queue.pop(0)
            if depth >= max_depth:
                continue
            for p in self.expand_axis(a, b, breadth=breadth, mode=mode, depth=depth):
                for parent in (a, b):
                    key = tuple(sorted((parent.lower(), p.lower())))
                    if key not in seen_axes:
                        seen_axes.add(key)
                        queue.append((parent, p, depth + 1))
        return self.graph

    def expand_node(self, node, breadth=4, mode="hybrid"):
        """Interactive expansion of a single node (double-click in the UI):
        use its first neighbor as axis partner, or ask the LLM for an opposite."""
        if node not in self.graph:
            raise KeyError(node)
        neighbors = list(self.graph.neighbors(node))
        if neighbors:
            partner = neighbors[0]
        elif self.llm:
            partner = self.llm.propose_opposite(node) or f"not-{node}"
            self._add_node(partner)
            self.graph.add_edge(node, partner, kind="axis")
        else:
            return []
        return self.expand_axis(node, partner, breadth=breadth, mode=mode,
                                depth=self.graph.nodes[node].get("depth", 0))

    def extend_pole(self, pole, partner, t=0.6, top_n=3):
        """'Super' region beyond a pole: step t pole-distances past `pole` along
        the axis away from `partner`, reverse-lookup, add the nearest concept
        as a new node. Returns (new_node, all_hits)."""
        vp, vo = self._embed_term(pole), self._embed_term(partner)
        pt = geometry.beyond_pole(vp, vo, t=t)
        hits = self._reverse_lookup(np.atleast_2d(pt), top_n=top_n,
                                    exclude=(pole, partner))[0]
        if not hits:
            return None, []
        new_node = hits[0][0]
        self._add_node(new_node, role="beyond-pole",
                       depth=self.graph.nodes[pole].get("depth", 0))
        self.graph.add_edge(pole, new_node, kind="extension")
        return new_node, hits

    # ---------- lenses & views ----------

    def make_lens(self, name, prompts=None, concept=None, k=None,
                  variance_keep=0.80):
        """Create a ConceptLens from an explicit prompt list, or ask the LLM
        to generate a coverage prompt set for `concept`."""
        if prompts is None:
            if self.llm is None:
                raise ValueError("No prompts given and no LLM to generate them")
            prompts = self.llm.propose_prompt_set(concept or name)
        lens = ConceptLens.from_prompts(name, prompts, self.embedder, self.cache,
                                        k=k, variance_keep=variance_keep)
        self.lenses[name] = lens
        return lens

    def project_graph(self, lens_name=None, lens=None):
        """Project every graph node into a lens -> {node: [c1..ck]}."""
        lens = lens or self.lenses[lens_name]
        nodes = list(self.graph.nodes)
        V = np.vstack([self._vecs[n] for n in nodes])
        Z = lens.project(V)
        return {n: Z[i].tolist() for i, n in enumerate(nodes)}

    def lens_similarities(self, lens_name):
        """Node-pair similarities under a lens, for edge weighting."""
        lens = self.lenses[lens_name]
        nodes = list(self.graph.nodes)
        V = np.vstack([self._vecs[n] for n in nodes])
        Z = lens.project(V)
        return {(nodes[i], nodes[j]): float(Z[i] @ Z[j])
                for i in range(len(nodes)) for j in range(i + 1, len(nodes))}

    # ---------- interpolation ----------

    def interpolate(self, node_a, node_b, steps=7, top_n=3):
        """Slerp from node_a to node_b; reverse-lookup at each step.
        Returns list of {t, point_is_node, terms:[(term, score)]}."""
        va, vb = self._embed_term(node_a), self._embed_term(node_b)
        pts = geometry.slerp(va, vb, steps=steps)
        hits = self._reverse_lookup(pts, top_n=top_n, exclude=(node_a, node_b))
        path = []
        for i, h in enumerate(hits):
            t = i / steps
            term = node_a if i == 0 else node_b if i == steps else None
            path.append({"t": round(t, 3), "node": term, "terms": h})
        return path

    # ---------- serialization ----------

    def to_json(self):
        nodes = [{"id": n, **self.graph.nodes[n]} for n in self.graph.nodes]
        edges = [{"source": u, "target": v, **d}
                 for u, v, d in self.graph.edges(data=True)]
        return {"nodes": nodes, "edges": edges,
                "embedder": self.embedder.name,
                "lenses": list(self.lenses)}

    @classmethod
    def from_json(cls, data, embedder, cache, llm=None):
        t = cls(embedder, cache, llm)
        for n in data["nodes"]:
            nd = dict(n)
            t._add_node(nd.pop("id"), **nd)
        for e in data["edges"]:
            ed = dict(e)
            t.graph.add_edge(ed.pop("source"), ed.pop("target"), **ed)
        return t
