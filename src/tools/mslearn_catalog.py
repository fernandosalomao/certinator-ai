"""
Certinator AI — Microsoft Learn Catalog API Tool

Deterministic tool that resolves learning path URLs to structured
data (title, duration, modules) using the Microsoft Learn Platform
API.  The LLM calls this tool with learning path URLs it already
extracted from search results or documentation pages; the Python
function does the API work and returns exact data so the model
never has to parse HTML.

Architecture
------------
- **Learning paths cache**: All learning paths are fetched once via
  paginated ``GET /learning-paths`` and cached to disk as a flat list
  (``cache/learning_paths.json``).  A title-keyed index is built in
  memory for fast lookup.  The cache has a 24-hour TTL.

- **Modules**: Fetched on-demand via ``GET /modules/{id}`` using the
  module IDs embedded in each learning path record.  No module cache
  is needed since the API supports direct lookup by ID.

API Reference
-------------
https://learn.microsoft.com/en-us/training/support/integrations-learn-platform-api-catalog-endpoints-developer-reference

Authentication: OAuth2 with scope ``https://learn.microsoft.com/.default``
Base URL: ``https://learn.microsoft.com/api/v1``
API Version: ``2023-11-01-preview``
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Annotated, Any, Optional

import requests
from agent_framework import ai_function
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)

# ── API constants ─────────────────────────────────────────────────────────

_API_BASE_URL = "https://learn.microsoft.com/api/v1"
_API_VERSION = "2023-11-01-preview"

# Cache lives in ``<project_root>/cache/``
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_CACHE_DIR = os.path.join(_PROJECT_ROOT, "cache")
_LP_CACHE_FILE = os.path.join(_CACHE_DIR, "learning_paths.json")

# Cache TTL: 24 hours in seconds
_CACHE_TTL_SECONDS = 24 * 60 * 60

# Maximum page size for the list endpoints (API limit is 100)
_MAX_PAGE_SIZE = 100


# ── Authentication ────────────────────────────────────────────────────────


def _get_access_token() -> str:
    """
    Obtain an OAuth2 access token for the Learn Platform API.

    Uses ``DefaultAzureCredential`` which supports Azure CLI,
    managed identity, and other credential chains.

    Returns:
        str: A Bearer access token.
    """
    credential = DefaultAzureCredential()
    token = credential.get_token("https://learn.microsoft.com/.default")
    return token.token


# ── Pagination helper ─────────────────────────────────────────────────────


def _fetch_all_pages(initial_url: str, token: str) -> list[dict[str, Any]]:
    """
    Fetch all pages from a paginated Learn Platform API response.

    Follows ``nextLink`` until exhausted.

    Parameters:
        initial_url (str): First page URL including query params.
        token (str): Bearer access token.

    Returns:
        list[dict[str, Any]]: Aggregated items from all pages.
    """
    all_items: list[dict[str, Any]] = []
    next_link: Optional[str] = initial_url
    page = 0

    while next_link:
        page += 1
        logger.debug("Fetching page %d: %s", page, next_link[:120])
        response = requests.get(
            next_link,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        items = data.get("value", [])
        all_items.extend(items)
        next_link = data.get("nextLink")

    logger.info("Fetched %d items across %d pages", len(all_items), page)
    return all_items


# ── Learning Paths cache ─────────────────────────────────────────────────


def _is_cache_valid() -> bool:
    """
    Check whether the LP cache file exists and is within TTL.

    Returns:
        bool: True if cache is fresh (< 24 hours old).
    """
    if not os.path.exists(_LP_CACHE_FILE):
        return False
    try:
        with open(_LP_CACHE_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        created_at = data.get("createdAt", 0)
        return (time.time() - created_at) < _CACHE_TTL_SECONDS
    except (json.JSONDecodeError, OSError):
        return False


def _load_cache() -> dict[str, Any]:
    """
    Load the LP cache from disk.

    Returns:
        dict[str, Any]: Cache data with ``createdAt`` and
            ``learningPaths`` (URL-keyed dict).

    Raises:
        FileNotFoundError: If cache file does not exist.
    """
    with open(_LP_CACHE_FILE, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _save_cache(lp_list: list[dict[str, Any]]) -> None:
    """
    Persist the LP cache to disk as a flat list.

    Parameters:
        lp_list (list[dict]): List of learning path records
            (id, url, title, durationInMinutes, modules).
    """
    os.makedirs(_CACHE_DIR, exist_ok=True)
    payload = {
        "createdAt": time.time(),
        "learningPaths": lp_list,
    }
    with open(_LP_CACHE_FILE, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    logger.info(
        "LP cache saved: %d entries → %s",
        len(lp_list),
        _LP_CACHE_FILE,
    )


def _build_lp_cache() -> list[dict[str, Any]]:
    """
    Fetch ALL learning paths from the API and cache them.

    Paginates through ``GET /learning-paths?maxpagesize=100`` and
    transforms each record into a lightweight cache entry.

    Returns:
        list[dict]: List of learning path records.
    """
    logger.info("Building LP cache from API (this may take a minute)...")
    token = _get_access_token()
    initial_url = (
        f"{_API_BASE_URL}/learning-paths"
        f"?api-version={_API_VERSION}"
        f"&maxpagesize={_MAX_PAGE_SIZE}"
    )
    raw_lps = _fetch_all_pages(initial_url, token)

    lp_list: list[dict[str, Any]] = []
    for lp in raw_lps:
        title = lp.get("title", "")
        if not title:
            continue
        lp_list.append(
            {
                "id": lp.get("id", ""),
                "url": lp.get("url", ""),
                "title": title,
                "durationInMinutes": lp.get("durationInMinutes", 0),
                "modules": lp.get("modules", []),
            }
        )

    _save_cache(lp_list)
    return lp_list


def _get_lp_list() -> list[dict[str, Any]]:
    """
    Return the full LP list, building/refreshing cache as needed.

    Returns:
        list[dict]: List of learning path records from cache.
    """
    if _is_cache_valid():
        logger.debug("LP cache is fresh, loading from disk")
        cache = _load_cache()
        return cache.get("learningPaths", [])
    return _build_lp_cache()


def _build_id_index(
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


# ── Exam → LP discovery ───────────────────────────────────────────────────

_COURSE_PAGE_URL = "https://learn.microsoft.com/en-us/training/courses/{course_id}/"


def _extract_lp_uids_from_course_page(exam_code: str) -> list[str]:
    """
    Discover learning path UIDs for an exam from the course page HTML.

    Microsoft exam course pages embed LP UIDs in ``data-learn-uid``
    attributes.  This function fetches the course page and extracts
    those UIDs.

    Parameters:
        exam_code (str): Exam code, e.g. ``AI-900``.

    Returns:
        list[str]: LP UIDs found in the page (may be empty).
    """
    course_id = f"{exam_code.lower()}t00"
    page_url = _COURSE_PAGE_URL.format(course_id=course_id)
    logger.info("Fetching course page for LP discovery: %s", page_url)

    try:
        resp = requests.get(
            page_url,
            headers={"User-Agent": "Certinator-AI/1.0"},
            timeout=20,
        )
        if not resp.ok:
            logger.warning(
                "Course page fetch failed (%d): %s", resp.status_code, page_url
            )
            return []
    except requests.RequestException as exc:
        logger.warning("Course page fetch error: %s", exc)
        return []

    # The page contains:
    #   Parent element: data-learn-type="path"
    #   Child elements: data-learn-uid="learn.xxx"
    # These are on DIFFERENT elements, so we extract all
    # data-learn-uid values and filter out course UIDs.
    uids: list[str] = re.findall(
        r'data-learn-uid="([^"]+)"',
        resp.text,
    )

    # Filter out course UIDs (they start with "course.")
    lp_uids = [uid for uid in uids if not uid.startswith("course.")]
    logger.info("Discovered %d LP UID(s) for %s: %s", len(lp_uids), exam_code, lp_uids)
    return lp_uids


# ── Module fetcher (on-demand, no cache) ──────────────────────────────────


def _fetch_module(module_id: str, token: str) -> Optional[dict[str, Any]]:
    """
    Fetch a single module by ID from the Learn Platform API.

    Parameters:
        module_id (str): The module identifier (e.g.
            ``learn.wwl.understand-unity-catalog``).
        token (str): Bearer access token.

    Returns:
        Optional[dict[str, Any]]: Module data or None on error.
    """
    url = f"{_API_BASE_URL}/modules/{module_id}?api-version={_API_VERSION}"
    try:
        response = requests.get(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
            timeout=15,
        )
        if not response.ok:
            logger.warning(
                "Module %s fetch failed: %d %s",
                module_id,
                response.status_code,
                response.reason,
            )
            return None
        return response.json()
    except requests.RequestException as exc:
        logger.warning("Module %s fetch error: %s", module_id, exc)
        return None


def _resolve_modules(
    module_refs: list[dict[str, Any]],
    token: str,
) -> list[dict[str, Any]]:
    """
    Resolve a list of module ID references to full module records.

    Parameters:
        module_refs (list[dict]): Module references from an LP record,
            each with at least an ``id`` key.
        token (str): Bearer access token.

    Returns:
        list[dict[str, Any]]: Resolved modules with title, url,
            durationInMinutes, and unitCount.
    """
    resolved: list[dict[str, Any]] = []
    for ref in module_refs:
        mod_id = ref.get("id", "")
        if not mod_id:
            continue
        mod_data = _fetch_module(mod_id, token)
        if mod_data is None:
            logger.warning("Skipping unresolvable module: %s", mod_id)
            continue
        resolved.append(
            {
                "id": mod_data.get("id", mod_id),
                "url": mod_data.get("url", ""),
                "title": mod_data.get("title", ""),
                "durationInMinutes": mod_data.get("durationInMinutes", 0),
                "unitCount": len(mod_data.get("units", [])),
            }
        )
    return resolved


# ── AI function tool ──────────────────────────────────────────────────────


@ai_function(
    name="fetch_exam_learning_paths",
    description=(
        "Given a Microsoft certification exam code (e.g. 'AI-900'), "
        "discover and return all learning paths for that exam with "
        "full details: titles, URLs, durations, and modules (with "
        "their titles, durations, and unit counts). This is the "
        "single source of truth for exam training content."
    ),
)
def fetch_exam_learning_paths(
    exam_code: Annotated[
        str,
        (
            "The Microsoft certification exam code, e.g. 'AI-900', "
            "'AZ-900', 'DP-900', 'SC-900'. Case-insensitive."
        ),
    ],
) -> str:
    """
    Discover and return learning paths for a certification exam.

    Workflow:
    1. Derive the course page URL from the exam code.
    2. Fetch the course page HTML and extract LP UIDs from
       ``data-learn-uid`` attributes.
    3. Load/build the learning paths cache.
    4. Match each LP UID to the cache by ID.
    5. Fetch each module by ID via ``GET /modules/{id}``.
    6. Return a JSON object with fully resolved learning paths.

    Parameters:
        exam_code (str): Exam code, e.g. ``AI-900``.

    Returns:
        str: JSON object with ``examCode``, ``learningPaths`` array,
            and optionally ``notFound`` for unresolved UIDs.
    """
    exam_code = exam_code.strip().upper()
    if not exam_code:
        return json.dumps({"error": "exam_code must be a non-empty string."})

    # ── Discover LP UIDs from the course page HTML ─────────────────
    lp_uids = _extract_lp_uids_from_course_page(exam_code)
    if not lp_uids:
        return json.dumps(
            {
                "examCode": exam_code,
                "error": (
                    f"No learning paths found for exam {exam_code}. "
                    "The course page may not exist or may not contain "
                    "learning path references."
                ),
                "learningPaths": [],
            }
        )

    # ── Load LP cache and build ID index ────────────────────────────
    try:
        lp_list = _get_lp_list()
        id_index = _build_id_index(lp_list)
    except Exception as exc:
        logger.error("Failed to load LP cache: %s", exc, exc_info=True)
        return json.dumps({"error": f"Failed to load learning paths cache: {exc}"})

    # ── Resolve each LP UID ───────────────────────────────────────────
    token = _get_access_token()
    result_lps: list[dict[str, Any]] = []
    not_found: list[str] = []

    for uid in lp_uids:
        lp_data = id_index.get(uid)

        if lp_data is None:
            not_found.append(uid)
            logger.warning("LP UID not found in cache: %s", uid)
            continue

        # Resolve module details via individual API calls
        module_refs = lp_data.get("modules", [])
        modules = _resolve_modules(module_refs, token)

        result_lps.append(
            {
                "id": lp_data.get("id", ""),
                "url": lp_data.get("url", ""),
                "title": lp_data.get("title", ""),
                "durationInMinutes": lp_data.get("durationInMinutes", 0),
                "moduleCount": len(modules),
                "modules": modules,
            }
        )

    result: dict[str, Any] = {
        "examCode": exam_code,
        "learningPaths": result_lps,
    }
    if not_found:
        result["notFound"] = not_found

    return json.dumps(result, ensure_ascii=False)
