"""Tessellator: exploring concept space with embedding geometry.

Core pieces:
- embeddings: pluggable embedding backends (LM Studio, Ollama, OpenAI-compatible
  including RunPod pods, sentence-transformers, hash fallback)
- lens: ConceptLens - PCA subspaces built from sets of prompts
- geometry: axis / perpendicular / pole-extension / interpolation operations
- builder: hybrid graph builder (LLM proposes candidates, geometry filters)
"""

__version__ = "0.1.0"
