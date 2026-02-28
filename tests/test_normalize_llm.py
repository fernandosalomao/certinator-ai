"""Test _normalize_llm_keys and model parsing with LLM output variations."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from executors.learning_path_fetcher_executor import LearningPathFetcherExecutor
from executors.models import LearningPathFetcherResponse


def test_normalize_skills_to_skills_at_a_glance():
    """LLM uses 'skills' with 'name' — should be normalised."""
    data = {
        "examCode": "AI-900",
        "skills": [
            {"name": "Describe AI workloads", "exam_weight_pct": 17.5},
            {"name": "ML on Azure", "exam_weight_pct": 17.5},
        ],
        "learningPaths": [
            {
                "title": "Intro to AI",
                "url": "https://learn.microsoft.com/training/paths/intro/",
                "duration_minutes": 100,
                "module_count": 1,
                "modules": [
                    {
                        "title": "AI Concepts",
                        "url": "https://learn.microsoft.com/training/modules/ai/",
                        "duration_minutes": 40,
                        "unit_count": 10,
                        "exam_skill": "Describe AI workloads",
                        "exam_weight_pct": 17.5,
                    }
                ],
            }
        ],
    }
    normalised = LearningPathFetcherExecutor._normalize_llm_keys(data)
    assert "skillsAtAGlance" in normalised
    assert "skills" not in normalised
    assert normalised["skillsAtAGlance"][0]["skill_name"] == "Describe AI workloads"
    assert "name" not in normalised["skillsAtAGlance"][0]

    parsed = LearningPathFetcherResponse.model_validate(normalised)
    assert parsed.exam_code == "AI-900"
    assert len(parsed.skills_at_a_glance) == 2
    assert parsed.skills_at_a_glance[0].skill_name == "Describe AI workloads"
    assert len(parsed.learning_paths) == 1
    assert parsed.learning_paths[0].modules[0].exam_skill == "Describe AI workloads"


def test_already_correct_keys():
    """LLM uses correct 'skillsAtAGlance' with 'skill_name' — no change needed."""
    data = {
        "examCode": "AZ-305",
        "skillsAtAGlance": [
            {"skill_name": "Design infra", "exam_weight_pct": 25.0},
        ],
        "learningPaths": [
            {
                "title": "AZ-305 Path",
                "url": "https://learn.microsoft.com/training/paths/az305/",
                "duration_minutes": 200,
                "module_count": 1,
                "modules": [
                    {
                        "title": "Design Module",
                        "url": "https://learn.microsoft.com/training/modules/design/",
                        "duration_minutes": 60,
                        "unit_count": 5,
                        "exam_skill": "Design infra",
                        "exam_weight_pct": 25.0,
                    }
                ],
            }
        ],
    }
    normalised = LearningPathFetcherExecutor._normalize_llm_keys(data)
    parsed = LearningPathFetcherResponse.model_validate(normalised)
    assert parsed.skills_at_a_glance[0].skill_name == "Design infra"


def test_no_skills_field_defaults_to_empty():
    """LLM omits skills entirely — should default to empty list."""
    data = {
        "examCode": "AZ-104",
        "learningPaths": [
            {
                "title": "AZ-104 Path",
                "url": "https://learn.microsoft.com/training/paths/az104/",
                "duration_minutes": 300,
                "module_count": 1,
                "modules": [
                    {
                        "title": "Manage Azure",
                        "url": "https://learn.microsoft.com/training/modules/manage/",
                        "duration_minutes": 90,
                        "unit_count": 8,
                        "exam_skill": "Manage Azure",
                        "exam_weight_pct": 20.0,
                    }
                ],
            }
        ],
    }
    normalised = LearningPathFetcherExecutor._normalize_llm_keys(data)
    parsed = LearningPathFetcherResponse.model_validate(normalised)
    assert parsed.skills_at_a_glance == []
    assert len(parsed.learning_paths) == 1


def test_extra_fields_ignored():
    """LLM adds extra fields — they should be ignored (not cause errors)."""
    data = {
        "examCode": "AI-900",
        "certification": "AI-900",
        "skills": [
            {"name": "AI workloads", "exam_weight_pct": 17.5, "extra_field": True}
        ],
        "learningPaths": [
            {
                "title": "AI Path",
                "url": "https://learn.microsoft.com/training/paths/ai/",
                "duration_minutes": 100,
                "module_count": 1,
                "id": "learn.ai",
                "modules": [
                    {
                        "title": "AI Module",
                        "url": "https://learn.microsoft.com/training/modules/aim/",
                        "duration_minutes": 50,
                        "unit_count": 6,
                        "exam_skill": "AI workloads",
                        "exam_weight_pct": 17.5,
                    }
                ],
            }
        ],
    }
    normalised = LearningPathFetcherExecutor._normalize_llm_keys(data)
    parsed = LearningPathFetcherResponse.model_validate(normalised)
    assert parsed.exam_code == "AI-900"
    assert parsed.skills_at_a_glance[0].skill_name == "AI workloads"


if __name__ == "__main__":
    test_normalize_skills_to_skills_at_a_glance()
    print("PASS: test_normalize_skills_to_skills_at_a_glance")
    test_already_correct_keys()
    print("PASS: test_already_correct_keys")
    test_no_skills_field_defaults_to_empty()
    print("PASS: test_no_skills_field_defaults_to_empty")
    test_extra_fields_ignored()
    print("PASS: test_extra_fields_ignored")
    print("\nAll tests PASSED")
