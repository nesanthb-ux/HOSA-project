"""Loads backend/config/weights.yaml. Every tunable weight/threshold in the
pipeline SHALL be read through here rather than hardcoded (CLAUDE.md)."""
from __future__ import annotations

import functools
import os

import yaml

_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "weights.yaml"
)


@functools.lru_cache(maxsize=1)
def get_weights() -> dict:
    with open(_CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def reload_weights() -> dict:
    """Clears the cache and re-reads the file. Used by tests that need to
    patch weights.yaml mid-run."""
    get_weights.cache_clear()
    return get_weights()
