"""Shared SentenceTransformer singleton.

Prevents multiple copies of the ~400 MB PyTorch model in memory.
All embedding consumers should use get_model() instead of creating
their own SentenceTransformer instance.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# Disable tokenizers parallelism to prevent forked subprocess leaks
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

_model = None


def get_model():
    """Return the shared SentenceTransformer model (lazy singleton)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        from config.settings import get_settings
        settings = get_settings()
        logger.info(f"Loading embedding model: {settings.embedding_model}")
        _model = SentenceTransformer(settings.embedding_model)
        logger.info("Embedding model loaded")
    return _model


def release_model() -> None:
    """Release the model to free ~400 MB. Call after analysis completes."""
    global _model
    if _model is not None:
        logger.info("Releasing embedding model")
        del _model
        _model = None
