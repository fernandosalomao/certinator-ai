"""
Certinator AI — Groundedness Evaluator

Deterministic evaluator that checks whether agent responses are
grounded in the provided context (MCP search results) rather than
hallucinated.  Measures factual overlap between the grounding
documents and the agent output using multiple signals:

    1. **URL overlap** — Microsoft Learn URLs present in context that
       also appear in the response.
    2. **Percentage/number overlap** — numeric facts (exam weights,
       durations, passing scores) cited in context that appear in the
       response.
    3. **Key phrase overlap** — multi-word noun phrases from the context
       found verbatim in the response (case-insensitive).
    4. **Named entity overlap** — certification codes, Azure service
       names, and technology terms from the context found in the
       response.

Scoring (1-5 scale):
    5 — Excellent grounding: ≥80 % of context signals present in
        the response.
    4 — Good grounding: 60 – 79 %.
    3 — Partial grounding: 40 – 59 %.
    2 — Weak grounding: 20 – 39 %.
    1 — Ungrounded: < 20 % of context signals found in the response.

When *no* context is provided the evaluator returns score 3 with a
note that groundedness cannot be assessed.

Dataset columns required:
    - ``response``: Agent output text.
    - ``context``: Grounding context (MCP search results / source docs).
"""

from __future__ import annotations

import re
from typing import List, Set

# ─── Signal extractors ───────────────────────────────────────────────────


def _extract_urls(text: str) -> Set[str]:
    """Extract HTTP(S) URLs from text.

    Parameters:
        text (str): Source text.

    Returns:
        Set[str]: Unique URLs found (lowercased for comparison).
    """
    return set(
        url.lower().rstrip(".,;:)>]")
        for url in re.findall(r"https?://[^\s\)\]\"'>]+", text)
    )


def _extract_numbers(text: str) -> Set[str]:
    """Extract numeric facts (percentages, durations, scores).

    Captures patterns like ``20-25%``, ``120 minutes``, ``700``,
    ``4.5 hours``, etc.

    Parameters:
        text (str): Source text.

    Returns:
        Set[str]: Normalised numeric strings.
    """
    # Percentage ranges: "20-25%", "15–20 %"
    pct_ranges = re.findall(r"\d+\s*[-–]\s*\d+\s*%", text)
    # Standalone percentages: "25%"
    pct_single = re.findall(r"\d+\s*%", text)
    # Numbers followed by units: "120 minutes", "4.5 hours"
    num_units = re.findall(r"\d+(?:\.\d+)?\s*(?:minutes?|hours?|days?|weeks?)", text)
    # Standalone significant numbers (≥3 digits, e.g. scores)
    big_nums = re.findall(r"\b\d{3,}\b", text)

    normalised: Set[str] = set()
    for item in pct_ranges + pct_single + num_units + big_nums:
        normalised.add(re.sub(r"\s+", "", item.lower()))
    return normalised


def _extract_key_phrases(text: str, min_words: int = 2) -> Set[str]:
    """Extract multi-word capitalised phrases likely to be key concepts.

    Matches sequences of 2+ capitalised words (e.g. "Azure Virtual
    Machines", "Skills Measured").  Also matches phrases inside
    heading markers (``##``, ``**``).

    Parameters:
        text (str): Source text.
        min_words (int): Minimum word count per phrase.

    Returns:
        Set[str]: Lowercased key phrases.
    """
    # Heading-style phrases: "## Exam Format", "### Skills Measured"
    heading_phrases = re.findall(r"#{1,4}\s+(.+?)$", text, re.MULTILINE)
    # Bold-style phrases: "**Skills Measured**"
    bold_phrases = re.findall(r"\*\*(.+?)\*\*", text)
    # Title-cased noun phrases (2+ words starting with uppercase)
    title_phrases = re.findall(
        r"\b(?:[A-Z][a-z]+(?:\s+(?:and|or|for|of|the|in|to|on|with)"
        r")?(?:\s+[A-Z][a-z]+)+)\b",
        text,
    )

    phrases: Set[str] = set()
    for raw in heading_phrases + bold_phrases + title_phrases:
        cleaned = raw.strip().lower()
        words = cleaned.split()
        if len(words) >= min_words:
            phrases.add(cleaned)
    return phrases


def _extract_entities(text: str) -> Set[str]:
    """Extract certification codes and Azure/tech named entities.

    Parameters:
        text (str): Source text.

    Returns:
        Set[str]: Lowercased entity strings.
    """
    # Certification codes: AZ-104, AI-900, DP-100, MS-900, etc.
    cert_codes = re.findall(r"\b[A-Z]{2,3}-\d{3,4}\b", text)
    # Azure service names: "Azure Kubernetes Service", etc.
    azure_services = re.findall(
        r"\bAzure\s+[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\b",
        text,
    )
    # Microsoft product names
    ms_products = re.findall(
        r"\bMicrosoft\s+[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\b",
        text,
    )

    entities: Set[str] = set()
    for item in cert_codes + azure_services + ms_products:
        entities.add(item.strip().lower())
    return entities


# ─── Overlap computation ────────────────────────────────────────────────


def _compute_overlap(
    context_signals: Set[str],
    response_text_lower: str,
) -> tuple[int, int, List[str], List[str]]:
    """Count how many context signals appear in the response.

    Parameters:
        context_signals (Set[str]): Signals extracted from context.
        response_text_lower (str): Lowercased response text.

    Returns:
        tuple: (found_count, total_count, found_list, missing_list).
    """
    found: List[str] = []
    missing: List[str] = []
    for signal in sorted(context_signals):
        if signal in response_text_lower:
            found.append(signal)
        else:
            missing.append(signal)
    return len(found), len(context_signals), found, missing


# ─── Evaluator class ────────────────────────────────────────────────────


class GroundednessEvaluator:
    """Check whether agent output is grounded in MCP context.

    Uses deterministic token/phrase overlap to measure how many
    factual signals from the grounding context (MCP search results)
    are present in the agent response.

    Dataset columns required:
        - ``response``: Agent output text.
        - ``context``: Grounding context (MCP search results).
    """

    def __call__(
        self,
        *,
        response: str,
        context: str = "",
        **kwargs: object,
    ) -> dict:
        """Evaluate groundedness of an agent response.

        Parameters:
            response (str): Agent-generated text.
            context (str): Grounding context (MCP search results).

        Returns:
            dict: Score, overlap ratio, found/missing signals,
                and explanation.
        """
        if not context or not context.strip():
            return {
                "groundedness_score": 3,
                "groundedness_ratio": None,
                "groundedness_signals_found": [],
                "groundedness_signals_missing": [],
                "groundedness_reason": (
                    "No grounding context provided. Groundedness cannot be assessed."
                ),
            }

        if not response or not response.strip():
            return {
                "groundedness_score": 1,
                "groundedness_ratio": 0.0,
                "groundedness_signals_found": [],
                "groundedness_signals_missing": [],
                "groundedness_reason": ("Empty response cannot be grounded."),
            }

        # ── Extract signals from context ────────────────────────
        ctx_urls = _extract_urls(context)
        ctx_numbers = _extract_numbers(context)
        ctx_phrases = _extract_key_phrases(context)
        ctx_entities = _extract_entities(context)

        all_signals = ctx_urls | ctx_numbers | ctx_phrases | ctx_entities

        if not all_signals:
            return {
                "groundedness_score": 3,
                "groundedness_ratio": None,
                "groundedness_signals_found": [],
                "groundedness_signals_missing": [],
                "groundedness_reason": (
                    "No extractable signals found in context. "
                    "Groundedness cannot be assessed."
                ),
            }

        # ── Check overlap in response ───────────────────────────
        response_lower = response.lower()
        found_count, total, found, missing = _compute_overlap(
            all_signals, response_lower
        )

        ratio = found_count / total if total > 0 else 0.0

        # ── Map ratio → score ───────────────────────────────────
        if ratio >= 0.80:
            score = 5
        elif ratio >= 0.60:
            score = 4
        elif ratio >= 0.40:
            score = 3
        elif ratio >= 0.20:
            score = 2
        else:
            score = 1

        return {
            "groundedness_score": score,
            "groundedness_ratio": round(ratio, 4),
            "groundedness_signals_found": found[:50],
            "groundedness_signals_missing": missing[:50],
            "groundedness_reason": (
                f"Grounding overlap: {found_count}/{total} signals "
                f"({ratio:.0%}). "
                + (
                    f"Found: {', '.join(found[:10])}."
                    if found
                    else "No signals matched."
                )
                + (f" Missing: {', '.join(missing[:10])}." if missing else "")
            ),
        }
