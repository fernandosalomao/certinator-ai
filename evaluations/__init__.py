"""
Certinator AI — Evaluation Package

End-to-end evaluation pipeline for the multi-agent certification
study assistant.  Combines custom domain-specific evaluators with
Azure AI Evaluation SDK built-in evaluators.

Usage:
    python -m evaluations --run                 Run full evaluation
    python -m evaluations --generate-dataset    Generate sample eval datasets
    python -m evaluations --run --no-builtin    Run only custom evaluators
    make eval                                   Shortcut for full run
"""
