"""Embedding-space geometry for the tessellator.

Implements the operations from the original sketch:
- axis between two poles:            v = normalize(emb(A) - emb(B))
- "perpendicular to the midpoint":   concepts near m=(A+B)/2 whose offset from
                                     m is orthogonal to v
- "super" regions beyond poles:      A + t*v  (t>0), B - t*v
- interpolation between two nodes:   slerp along the arc, reverse-lookup
                                     nearest vocabulary concepts at each step
"""

import numpy as np


def normalize(v, eps=1e-12):
    v = np.asarray(v, dtype=np.float64)
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, eps)


def axis_vector(a, b):
    """Unit direction from b to a (pole b -> pole a)."""
    return normalize(np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64))


def midpoint(a, b):
    return normalize((np.asarray(a, dtype=np.float64) + np.asarray(b, dtype=np.float64)) / 2.0)


def perpendicular_scores(candidate_vecs, a, b):
    """For each candidate vector c: how perpendicular is (c - midpoint) to the
    axis a<->b?

    Returns (scores, residual_vecs):
      scores in [0,1]: fraction of the candidate's offset-from-midpoint that is
          orthogonal to the axis. 1.0 = purely perpendicular.
      residual_vecs: the axis-orthogonal component of each offset (useful for
          clustering candidates into distinct perpendicular directions).
    """
    C = np.atleast_2d(np.asarray(candidate_vecs, dtype=np.float64))
    m = midpoint(a, b)
    v = axis_vector(a, b)                      # (d,)
    offsets = C - m                            # (n, d)
    axial = offsets @ v                        # (n,)
    residual = offsets - np.outer(axial, v)    # (n, d)
    off_n = np.linalg.norm(offsets, axis=1)
    res_n = np.linalg.norm(residual, axis=1)
    scores = np.clip(res_n / np.maximum(off_n, 1e-12), 0.0, 1.0)
    return scores, residual


def dedupe_directions(vecs, cos_thresh=0.75):
    """Greedy: keep items whose residual direction isn't ~parallel to an
    already-kept one. Returns kept indices (in original order)."""
    V = normalize(np.asarray(vecs, dtype=np.float64))
    keep = []
    for i in range(len(V)):
        if all(float(V[i] @ V[j]) < cos_thresh for j in keep):
            keep.append(i)
    return keep


def beyond_pole(pole_vec, other_vec, t=0.5):
    """Point 'beyond' pole, continuing the axis away from other_vec.
    t ~ fraction of the pole-to-pole distance to overshoot by."""
    pole_vec = np.asarray(pole_vec, dtype=np.float64)
    v = axis_vector(pole_vec, other_vec)       # points other -> pole
    return normalize(pole_vec + t * v)


def slerp(a, b, steps):
    """Spherical interpolation between unit vectors a->b. Returns (steps+1, d)
    points including endpoints."""
    a, b = normalize(np.asarray(a, dtype=np.float64)), normalize(np.asarray(b, dtype=np.float64))
    dot = float(np.clip(a @ b, -1.0, 1.0))
    omega = np.arccos(dot)
    if omega < 1e-6:
        return np.tile(a, (steps + 1, 1))
    so = np.sin(omega)
    ts = np.linspace(0.0, 1.0, steps + 1)
    w1 = np.sin((1 - ts) * omega) / so
    w2 = np.sin(ts * omega) / so
    return w1[:, None] * a + w2[:, None] * b


def nearest_concepts(point_vecs, vocab_vecs, vocab_terms, top_n=3, exclude=()):
    """Reverse token lookup: for each query point, the top_n nearest vocab terms
    by cosine similarity. Returns list (per point) of (term, score)."""
    Q = normalize(np.atleast_2d(np.asarray(point_vecs, dtype=np.float64)))
    V = normalize(np.asarray(vocab_vecs, dtype=np.float64))
    sims = Q @ V.T                                            # (n, m)
    excl = {e.lower() for e in exclude}
    out = []
    for row in sims:
        order = np.argsort(row)[::-1]
        hits = []
        for j in order:
            term = vocab_terms[j]
            if term.lower() in excl:
                continue
            hits.append((term, float(row[j])))
            if len(hits) >= top_n:
                break
        out.append(hits)
    return out
