"""
Certinator AI — Evaluation CLI Entry Point

Usage:
    python -m evaluations --run                  Run full evaluation
    python -m evaluations --run --no-builtin     Custom evaluators only
    python -m evaluations --generate-dataset     Generate sample datasets
    python -m evaluations --run --data <path>    Run eval on custom dataset
"""

import json
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

from evaluations.evaluation import run_evaluation


def main() -> None:
    """Parse CLI arguments and run the evaluation."""
    if "--run" in sys.argv:
        include_builtin = "--no-builtin" not in sys.argv
        result = run_evaluation(
            include_builtin=include_builtin,
            include_custom=True,
        )

        # Print summary to stdout
        print("\n" + "=" * 60)
        print("  Certinator AI — Evaluation Results")
        print("=" * 60)

        summary = result.get("summary", {})
        if summary:
            print(f"\n  Overall Average Score: {result.get('overall_avg', 0)}/5.0\n")
            for suite_name, avg_score in summary.items():
                status = (
                    "PASS"
                    if avg_score >= 4.0
                    else "WARN"
                    if avg_score >= 3.0
                    else "FAIL"
                )
                print(f"  [{status}] {suite_name}: {avg_score}/5.0")

            # Critic calibration aggregate metrics
            suites = result.get("suites", {})
            critic_data = suites.get("critic_calibration", {})
            if "precision" in critic_data:
                print("\n  Critic Calibration Metrics:")
                cm = critic_data.get("confusion_matrix", {})
                print(
                    f"    Confusion Matrix: TP={cm.get('tp', 0)} "
                    f"TN={cm.get('tn', 0)} "
                    f"FP={cm.get('fp', 0)} "
                    f"FN={cm.get('fn', 0)}"
                )
                print(f"    Precision: {critic_data['precision']}")
                print(f"    Recall:    {critic_data['recall']}")
                print(f"    F1:        {critic_data['f1']}")
                print(f"    Accuracy:  {critic_data['accuracy']}")
                print(f"    Conf. MAE: {critic_data['confidence_mae']}")
        else:
            print("\n  No evaluation results available.")

        print("\n" + "=" * 60)
        print(f"  Full results: {result.get('suites', {}).keys()}")
        print("=" * 60 + "\n")

    elif "--generate-dataset" in sys.argv:
        from evaluations.evaluation import DATASETS_DIR

        print(f"Datasets are located at: {DATASETS_DIR}")
        print("Available datasets:")
        if DATASETS_DIR.exists():
            for f in sorted(DATASETS_DIR.glob("*.jsonl")):
                lines = sum(1 for _ in open(f))
                print(f"  {f.name}: {lines} records")
        else:
            print("  No datasets directory found.")

    else:
        print("Certinator AI — Evaluation Pipeline")
        print("Usage:")
        print("  python -m evaluations --run                  Run full evaluation")
        print("  python -m evaluations --run --no-builtin     Custom evaluators only")
        print("  python -m evaluations --generate-dataset     List datasets")


if __name__ == "__main__":
    main()
