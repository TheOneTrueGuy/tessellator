"""Concept vocabulary for reverse token lookup.

The geometry produces points in embedding space; to turn a point back into a
concept we need a vocabulary of candidate terms to search. Sources, in order:
  1. graph nodes (always available once a graph exists)
  2. a user-supplied vocab file (vocab.txt, one term per line)
  3. a small built-in starter vocabulary for demos
  4. LLM-proposed candidates (added dynamically during expansion)
"""

import os

VOCAB_PATH = os.environ.get(
    "TESSELLATOR_VOCAB",
    os.path.join(os.path.dirname(__file__), "..", "vocab.txt"),
)

STARTER_VOCAB = [
    # Animals / nature
    "cat", "dog", "bird", "fish", "tree", "forest", "ocean", "mountain",
    "river", "insect", "reptile", "mammal", "ecosystem", "evolution",
    # Technology
    "artificial intelligence", "computer", "internet", "robot", "algorithm",
    "database", "software", "hardware", "network", "cybersecurity",
    "machine learning", "virtual reality", "blockchain", "quantum computing",
    # Society / humanities
    "democracy", "capitalism", "socialism", "religion", "philosophy", "ethics",
    "law", "education", "economy", "politics", "culture", "language",
    "history", "art", "music", "literature", "science", "mathematics",
    "psychology", "sociology", "anthropology", "medicine", "war", "peace",
    # Emotions / abstract
    "love", "fear", "joy", "anger", "sadness", "hope", "freedom", "justice",
    "truth", "beauty", "chaos", "order", "time", "space", "death", "life",
    "consciousness", "memory", "dream", "identity", "power", "wealth",
    # Physical / material
    "energy", "matter", "gravity", "light", "sound", "heat", "electricity",
    "magnetism", "atom", "molecule", "cell", "organism", "planet", "star",
    "galaxy", "universe",
    # Human constructs
    "city", "village", "house", "machine", "tool", "vehicle", "road",
    "bridge", "factory", "farm", "market", "money", "trade", "work",
    "play", "sport", "game", "family", "friendship", "community", "nation",
    "empire", "revolution", "tradition", "innovation", "ritual", "myth",
    # Disciplines / methods
    "engineering", "architecture", "design", "agriculture", "cooking",
    "medicine", "surgery", "pharmacology", "physics", "chemistry", "biology",
    "geology", "astronomy", "linguistics", "logic", "statistics",
    # Qualities / poles commonly used as axes
    "natural", "artificial", "organic", "synthetic", "simple", "complex",
    "individual", "collective", "local", "global", "ancient", "modern",
    "static", "dynamic", "concrete", "abstract", "emotional", "rational",
    "physical", "digital", "human", "machine", "centralized", "distributed",
    "cooperation", "competition", "growth", "decay", "creation", "destruction",
]


def load_vocab(extra_terms=()):
    """Return a deduped list of vocabulary terms."""
    terms = list(STARTER_VOCAB)
    if os.path.exists(VOCAB_PATH):
        with open(VOCAB_PATH, "r", encoding="utf-8") as f:
            terms += [line.strip() for line in f if line.strip()]
    terms += [t for t in extra_terms if t]
    seen, out = set(), []
    for t in terms:
        tl = t.lower()
        if tl not in seen:
            seen.add(tl)
            out.append(t)
    return out
