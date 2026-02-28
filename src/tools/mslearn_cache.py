"""
Certinator AI — Microsoft Learn Catalog Disk Cache

Manages the on-disk JSON cache for learning paths fetched from the
Microsoft Learn Platform API.  Provides read / write / validation
helpers with a configurable TTL (default 24 hours).

The cache file lives at ``<project_root>/cache/learning_paths.json``
with the structure::

    {
        "createdAt": <unix-timestamp>,
        "learningPaths": [ { id, url, title, durationInMinutes, modules }, … ]
    }
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

# ── Paths & TTL ───────────────────────────────────────────────────────────

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
CACHE_DIR = os.path.join(_PROJECT_ROOT, "cache")
LP_CACHE_FILE = os.path.join(CACHE_DIR, "learning_paths.json")

# Cache TTL: 24 hours in seconds
CACHE_TTL_SECONDS = 24 * 60 * 60


# ── Cache helpers ─────────────────────────────────────────────────────────


def is_cache_valid() -> bool:
    """Return ``True`` if the LP cache file exists and is within TTL."""
    if not os.path.exists(LP_CACHE_FILE):
        return False
    try:
        with open(LP_CACHE_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        created_at = data.get("createdAt", 0)
        return (time.time() - created_at) < CACHE_TTL_SECONDS
    except (json.JSONDecodeError, OSError):
        return False


def load_cache() -> dict[str, Any]:
    """
    Load the LP cache from disk.

    Returns:
        dict[str, Any]: Cache data with ``createdAt`` and
            ``learningPaths`` (list of LP records).

    Raises:
        FileNotFoundError: If cache file does not exist.
    """
    with open(LP_CACHE_FILE, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_cache(lp_list: list[dict[str, Any]]) -> None:
    """
    Persist the LP cache to disk.

    Parameters:
        lp_list (list[dict]): List of learning path records.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    payload = {
        "createdAt": time.time(),
        "learningPaths": lp_list,
    }
    with open(LP_CACHE_FILE, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    logger.info(
        "LP cache saved: %d entries → %s",
        len(lp_list),
        LP_CACHE_FILE,
    )


def build_id_index(
    lp_list: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """
    Build an in-memory ID-keyed index from the LP list.

    Parameters:
        lp_list (list[dict]): List of LP records.

    Returns:
        dict[str, dict]: LP-id → LP record mapping.
    """
    index: dict[str, dict[str, Any]] = {}
    for lp in lp_list:
        lp_id = lp.get("id", "")
        if lp_id:
            index[lp_id] = lp
    return index
