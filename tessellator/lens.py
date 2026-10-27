"""Concept Lenses: PCA subspaces built from sets of prompts.

Following Jasper Lu's "Exploring Similarity Search with Prompted Subspaces":
embed a set of prompts describing a concept, center them, eigendecompose the
covariance, keep the top-k eigenvectors as an orthonormal basis B. Projecting
an embedding x into the lens: z(x) = B x / ||B x||. Cosine similarity in that
subspace then measures distance *along that concept only*.
"""

import numpy as np


def _normalize(v, eps=1e-12):
    v = np.asarray(v, dtype=np.float64)
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, eps)


class ConceptLens:
    """A prompted subspace. Build from a set of prompts covering a concept."""

    def __init__(self, name, prompts, basis, eigenvalues, mean, embedder_name,
                 total_variance=None):
        self.name = name
        self.prompts = list(prompts)
        self.basis = basis              # (k, d) orthonormal rows
        self.eigenvalues = eigenvalues  # (k,) top-k eigenvalues
        self.mean = mean                # (d,) mean of prompt embeddings
        self.embedder_name = embedder_name
        self.total_variance = float(total_variance if total_variance is not None
                                    else eigenvalues.sum())

    @property
    def k(self):
        return self.basis.shape[0]

    @classmethod
    def from_prompts(cls, name, prompts, embedder, cache, k=None,
                     variance_keep=0.80):
        """Embed prompts, center, eigendecompose, keep top-k eigenvectors.

        k=None -> smallest k capturing >= variance_keep of total variance.
        """
        if len(prompts) < 2:
            raise ValueError("A lens needs at least 2 prompts.")
        T = embedder.embed_cached(list(prompts), cache)   # (m, d)
        mean = T.mean(axis=0)
        Tc = T - mean
        cov = (Tc.T @ Tc) / max(Tc.shape[0] - 1, 1)
        evals, evecs = np.linalg.eigh(cov)
        order = np.argsort(evals)[::-1]
        evals, evecs = evals[order], evecs[:, order]

        if k is None:
            total = evals.sum()
            cum = np.cumsum(evals) / total if total > 0 else np.ones_like(evals)
            k = int(np.searchsorted(cum, variance_keep) + 1)
        k = max(1, min(k, len(prompts) - 1))
        basis = evecs[:, :k].T          # (k, d), rows orthonormal
        return cls(name, prompts, basis, evals[:k], mean, embedder.name,
                   total_variance=evals.sum())

    @classmethod
    def from_axis(cls, name, concept_a, concept_b, embedder, cache):
        """Degenerate 2-prompt lens: a single axis from A to B."""
        return cls.from_prompts(name, [concept_a, concept_b], embedder, cache, k=1)

    @property
    def variance_kept(self):
        return float(self.eigenvalues.sum() / self.total_variance) if self.total_variance else 1.0

    def project(self, x, renormalize=True):
        """Project embedding vector(s) (..., d) -> lens coords (..., k)."""
        x = np.asarray(x, dtype=np.float64)
        centered = x - self.mean
        z = centered @ self.basis.T
        return _normalize(z) if renormalize else z

    def similarity(self, x, y):
        """Cosine similarity of x, y inside this lens's subspace."""
        zx, zy = self.project(x), self.project(y)
        return float(np.dot(zx, zy))

    def coords_for_texts(self, texts, embedder, cache):
        """Embed texts and return their projected lens coordinates."""
        return self.project(embedder.embed_cached(list(texts), cache))

    def top_components(self):
        """(index, eigenvalue, share-of-total) for each kept axis."""
        return [(i, float(ev), float(ev / self.total_variance))
                for i, ev in enumerate(self.eigenvalues)]

    def to_dict(self):
        return {
            "name": self.name,
            "prompts": self.prompts,
            "k": int(self.k),
            "eigenvalues": [float(e) for e in self.eigenvalues],
            "total_variance": self.total_variance,
            "basis": self.basis.tolist(),
            "mean": self.mean.tolist(),
            "embedder": self.embedder_name,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            name=d["name"],
            prompts=d["prompts"],
            basis=np.asarray(d["basis"], dtype=np.float64),
            eigenvalues=np.asarray(d["eigenvalues"], dtype=np.float64),
            mean=np.asarray(d["mean"], dtype=np.float64),
            embedder_name=d.get("embedder", "unknown"),
            total_variance=d.get("total_variance"),
        )
