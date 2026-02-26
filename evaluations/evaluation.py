"""
Certinator AI — Evaluation Orchestrator

Runs all evaluation suites — custom domain-specific evaluators and
Azure AI Evaluation SDK built-in evaluators — against labelled
JSONL datasets.

Architecture:
    1. Custom evaluators (always available, no LLM dependency):
       - RoutingAccuracyEvaluator  → routing_queries.jsonl
       - ExamContentAccuracyEvaluator → cert_info_golden.jsonl
       - StudyPlanFeasibilityEvaluator → study_plan_scenarios.jsonl
       - QuizQualityEvaluator → quiz_quality.jsonl
       - ContentSafetyEvaluator → (applied to all datasets)

    2. SDK built-in evaluators (require Azure OpenAI endpoint):
       - RelevanceEvaluator → cert_info_golden.jsonl
       - CoherenceEvaluator → cert_info_golden.jsonl
       - GroundednessEvaluator → cert_info_golden.jsonl

    3. Inline evaluation helper (evaluate_single_response)

Usage:
    python -m evaluations --run
    python -m evaluations --run --no-builtin
    python -m evaluations --generate-dataset
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv(override=True)

logger = logging.getLogger(__name__)

# ─── Paths ───────────────────────────────────────────────────────────────
EVAL_DIR = Path(__file__).parent
DATASETS_DIR = EVAL_DIR / "datasets"
RESULTS_DIR = EVAL_DIR / "results"

# ─── Custom evaluator singletons ────────────────────────────────────────
from evaluations.evaluators import (
    ContentSafetyEvaluator,
    ExamContentAccuracyEvaluator,
    QuizQualityEvaluator,
    RoutingAccuracyEvaluator,
    StudyPlanFeasibilityEvaluator,
)

_routing_evaluator = RoutingAccuracyEvaluator()
_exam_content_evaluator = ExamContentAccuracyEvaluator()
_study_plan_evaluator = StudyPlanFeasibilityEvaluator()
_quiz_quality_evaluator = QuizQualityEvaluator()
_content_safety_evaluator = ContentSafetyEvaluator()


# ─── Helpers ─────────────────────────────────────────────────────────────


def _load_jsonl(path: Path) -> list[dict]:
    """Load a JSONL file into a list of dicts.

    Parameters:
        path (Path): Path to a ``.jsonl`` file.

    Returns:
        list[dict]: Parsed records.
    """
    records: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _get_model_config():
    """Build Azure OpenAI model configuration for SDK evaluators.

    Returns:
        AzureOpenAIModelConfiguration or None if unavailable.
    """
    try:
        from azure.ai.evaluation import (
            AzureOpenAIModelConfiguration,
        )

        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        deployment = os.environ.get("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4.1")
        api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")

        if not endpoint:
            logger.warning(
                "Evaluation: AZURE_OPENAI_ENDPOINT not set. "
                "SDK built-in evaluators will be skipped."
            )
            return None

        config_kwargs = {
            "azure_deployment": deployment,
            "azure_endpoint": endpoint,
        }
        if api_key:
            config_kwargs["api_key"] = api_key

        return AzureOpenAIModelConfiguration(**config_kwargs)

    except ImportError:
        logger.warning(
            "Evaluation: azure-ai-evaluation not installed. "
            "Run: pip install azure-ai-evaluation"
        )
        return None


# ─── Per-suite evaluation runners ────────────────────────────────────────


def _run_custom_suite(
    dataset_name: str,
    evaluator,
    data_path: Path,
    evaluator_name: str,
) -> dict:
    """Run a single custom evaluator against a JSONL dataset.

    Parameters:
        dataset_name (str): Label for the suite.
        evaluator: Callable evaluator instance.
        data_path (Path): Path to JSONL file.
        evaluator_name (str): Name for logging.

    Returns:
        dict: Row-level results + aggregate metrics.
    """
    if not data_path.exists():
        logger.warning(
            "Evaluation: Dataset %s not found at %s",
            dataset_name,
            data_path,
        )
        return {"error": f"Dataset not found: {data_path}"}

    records = _load_jsonl(data_path)
    row_results: list[dict] = []
    scores: list[float] = []

    for idx, record in enumerate(records):
        try:
            result = evaluator(
                response=record.get("response", ""),
                context=record.get("context", ""),
                query=record.get("query", ""),
            )
            result["_row_index"] = idx
            result["_query"] = record.get("query", "")[:200]
            row_results.append(result)

            # Extract score (convention: <name>_score)
            score_key = next(
                (k for k in result if k.endswith("_score")),
                None,
            )
            if score_key is not None:
                scores.append(result[score_key])
        except Exception as exc:
            logger.error(
                "Evaluation: %s row %d failed: %s",
                evaluator_name,
                idx,
                exc,
            )
            row_results.append({"_row_index": idx, "error": str(exc)})

    avg_score = round(sum(scores) / len(scores), 2) if scores else 0
    pass_rate = (
        round(
            sum(1 for s in scores if s >= 4) / len(scores) * 100,
            1,
        )
        if scores
        else 0
    )

    return {
        "suite": dataset_name,
        "evaluator": evaluator_name,
        "total_rows": len(records),
        "avg_score": avg_score,
        "pass_rate_pct": pass_rate,
        "rows": row_results,
    }


def run_evaluation(
    include_builtin: bool = True,
    include_custom: bool = True,
    output_path: Optional[str] = None,
) -> dict:
    """Run the full evaluation pipeline.

    Parameters:
        include_builtin (bool): Include Azure AI SDK evaluators.
        include_custom (bool): Include custom evaluators.
        output_path (str | None): Directory for results JSON.

    Returns:
        dict: Evaluation results with per-suite and aggregate data.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    if output_path is None:
        output_path = str(RESULTS_DIR / f"eval_run_{timestamp}.json")

    all_results: dict[str, dict] = {}

    # ── Custom evaluator suites ──────────────────────────────────
    if include_custom:
        logger.info("Evaluation: Running custom evaluator suites...")

        # 1. Routing accuracy
        all_results["routing_accuracy"] = _run_custom_suite(
            dataset_name="routing_accuracy",
            evaluator=_routing_evaluator,
            data_path=DATASETS_DIR / "routing_queries.jsonl",
            evaluator_name="RoutingAccuracyEvaluator",
        )

        # 2. Adversarial routing
        all_results["adversarial_routing"] = _run_custom_suite(
            dataset_name="adversarial_routing",
            evaluator=_routing_evaluator,
            data_path=DATASETS_DIR / "adversarial_routing.jsonl",
            evaluator_name="RoutingAccuracyEvaluator",
        )

        # 3. Exam content accuracy
        all_results["cert_info_completeness"] = _run_custom_suite(
            dataset_name="cert_info_completeness",
            evaluator=_exam_content_evaluator,
            data_path=DATASETS_DIR / "cert_info_golden.jsonl",
            evaluator_name="ExamContentAccuracyEvaluator",
        )

        # 4. Study plan feasibility
        all_results["study_plan_feasibility"] = _run_custom_suite(
            dataset_name="study_plan_feasibility",
            evaluator=_study_plan_evaluator,
            data_path=DATASETS_DIR / "study_plan_scenarios.jsonl",
            evaluator_name="StudyPlanFeasibilityEvaluator",
        )

        # 5. Quiz quality
        all_results["quiz_quality"] = _run_custom_suite(
            dataset_name="quiz_quality",
            evaluator=_quiz_quality_evaluator,
            data_path=DATASETS_DIR / "quiz_quality.jsonl",
            evaluator_name="QuizQualityEvaluator",
        )

        # 6. Content safety on cert info
        all_results["content_safety"] = _run_custom_suite(
            dataset_name="content_safety",
            evaluator=_content_safety_evaluator,
            data_path=DATASETS_DIR / "cert_info_golden.jsonl",
            evaluator_name="ContentSafetyEvaluator",
        )

        logger.info(
            "Evaluation: Custom suites complete. %d suites run.",
            len(all_results),
        )

    # ── SDK built-in evaluators ──────────────────────────────────
    if include_builtin:
        model_config = _get_model_config()
        if model_config:
            try:
                from azure.ai.evaluation import (
                    CoherenceEvaluator,
                    RelevanceEvaluator,
                    evaluate,
                )

                cert_info_path = DATASETS_DIR / "cert_info_golden.jsonl"
                if cert_info_path.exists():
                    evaluators = {}
                    evaluator_config = {}

                    relevance_eval = RelevanceEvaluator(model_config=model_config)
                    evaluators["relevance"] = relevance_eval
                    evaluator_config["relevance"] = {
                        "column_mapping": {
                            "query": "${data.query}",
                            "response": "${data.response}",
                        }
                    }

                    coherence_eval = CoherenceEvaluator(model_config=model_config)
                    evaluators["coherence"] = coherence_eval
                    evaluator_config["coherence"] = {
                        "column_mapping": {
                            "query": "${data.query}",
                            "response": "${data.response}",
                        }
                    }

                    logger.info(
                        "Evaluation: Running SDK built-in "
                        "evaluators (Relevance, Coherence)..."
                    )

                    sdk_output = str(RESULTS_DIR / f"sdk_eval_{timestamp}")
                    sdk_result = evaluate(
                        data=str(cert_info_path),
                        evaluators=evaluators,
                        evaluator_config=evaluator_config,
                        output_path=sdk_output,
                    )
                    all_results["sdk_builtin"] = sdk_result
                    logger.info(
                        "Evaluation: SDK results saved to %s",
                        sdk_output,
                    )
                else:
                    logger.warning(
                        "Evaluation: cert_info_golden.jsonl "
                        "not found. Skipping SDK evaluators."
                    )

            except ImportError as exc:
                logger.warning(
                    "Evaluation: SDK evaluators unavailable: %s",
                    exc,
                )
        else:
            logger.info("Evaluation: Skipping SDK evaluators (no model config).")

    # ── Aggregate summary ────────────────────────────────────────
    summary: dict[str, float] = {}
    for suite_name, suite_data in all_results.items():
        if isinstance(suite_data, dict) and "avg_score" in suite_data:
            summary[suite_name] = suite_data["avg_score"]

    final_result = {
        "timestamp": timestamp,
        "summary": summary,
        "overall_avg": (
            round(sum(summary.values()) / len(summary), 2) if summary else 0
        ),
        "suites": all_results,
    }

    # ── Save results ─────────────────────────────────────────────
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_result, f, indent=2, default=str)
    logger.info("Evaluation: Results saved to %s", output_path)

    return final_result


# ─── Inline single-response evaluation ───────────────────────────────────


def evaluate_single_response(
    query: str,
    response: str,
    context: str = "",
) -> dict:
    """Evaluate a single agent response using custom evaluators.

    Designed for inline quality checks — no dataset or SDK needed.

    Parameters:
        query (str): User query.
        response (str): Agent response text.
        context (str): Optional grounding context.

    Returns:
        dict: Per-evaluator scores and overall grade.
    """
    safety_result = _content_safety_evaluator(response=response)
    exam_content_result = _exam_content_evaluator(response=response)

    scores = [
        safety_result["content_safety_score"],
        exam_content_result["exam_content_accuracy_score"],
    ]
    avg_score = round(sum(scores) / len(scores), 2)

    return {
        "query": query[:200],
        "overall_score": avg_score,
        "max_score": 5,
        "grade": (
            "A"
            if avg_score >= 4.5
            else "B"
            if avg_score >= 3.5
            else "C"
            if avg_score >= 2.5
            else "D"
            if avg_score >= 1.5
            else "F"
        ),
        "content_safety": safety_result,
        "exam_content_accuracy": exam_content_result,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }
