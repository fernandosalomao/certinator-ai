"""Tests for schedule Pydantic models and compute_schedule()."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from executors.models import (
    ScheduleResult,
    ScheduleWeek,
    ScheduleWeekItem,
    SkillSummaryItem,
    SkippedModule,
    StudyConstraints,
)
from tools.schedule import compute_schedule, schedule_study_plan

# ── Fixtures ────────────────────────────────────────────────────────


def _sample_learning_paths() -> list[dict]:
    """Return a minimal learning path list for testing."""
    return [
        {
            "title": "AZ-900: Azure Fundamentals",
            "url": "https://learn.microsoft.com/training/paths/az900/",
            "duration_minutes": 120,
            "module_count": 2,
            "modules": [
                {
                    "title": "Cloud Concepts",
                    "url": "https://learn.microsoft.com/training/modules/cloud/",
                    "duration_minutes": 40,
                    "unit_count": 8,
                    "exam_skill": "Describe cloud concepts",
                    "exam_weight_pct": 25.0,
                },
                {
                    "title": "Azure Architecture",
                    "url": "https://learn.microsoft.com/training/modules/arch/",
                    "duration_minutes": 50,
                    "unit_count": 10,
                    "exam_skill": "Describe Azure architecture",
                    "exam_weight_pct": 35.0,
                },
            ],
        },
        {
            "title": "AZ-900: Azure Services",
            "url": "https://learn.microsoft.com/training/paths/services/",
            "duration_minutes": 90,
            "module_count": 1,
            "modules": [
                {
                    "title": "Compute Services",
                    "url": "https://learn.microsoft.com/training/modules/compute/",
                    "duration_minutes": 60,
                    "unit_count": 12,
                    "exam_skill": "Describe Azure services",
                    "exam_weight_pct": 40.0,
                },
            ],
        },
    ]


# ── Model Validation Tests ──────────────────────────────────────────


class TestScheduleWeekItem:
    """ScheduleWeekItem model validation."""

    def test_valid_item(self) -> None:
        """Create a valid ScheduleWeekItem."""
        item = ScheduleWeekItem(
            module="Cloud Concepts",
            url="https://learn.microsoft.com/training/modules/cloud/",
            duration_minutes=40.0,
            hours=0.67,
            exam_skill="Describe cloud concepts",
            exam_weight_pct=25.0,
            learning_path="AZ-900: Azure Fundamentals",
        )
        assert item.module == "Cloud Concepts"
        assert item.hours == 0.67


class TestScheduleWeek:
    """ScheduleWeek model validation."""

    def test_valid_week(self) -> None:
        """Create a valid ScheduleWeek with items."""
        week = ScheduleWeek(
            week=1,
            hours=1.5,
            items=[
                ScheduleWeekItem(
                    module="Cloud Concepts",
                    url="https://example.com",
                    duration_minutes=40.0,
                    hours=0.67,
                    exam_skill="Cloud",
                    exam_weight_pct=25.0,
                    learning_path="AZ-900",
                ),
            ],
        )
        assert week.week == 1
        assert len(week.items) == 1


class TestSkillSummaryItem:
    """SkillSummaryItem model validation."""

    def test_defaults(self) -> None:
        """Fields with defaults should initialise correctly."""
        item = SkillSummaryItem(
            exam_skill="Cloud",
            exam_weight_pct=25.0,
            total_minutes=120.0,
        )
        assert item.modules_included == 0
        assert item.modules_skipped == 0
        assert item.selected_minutes == 0.0


class TestScheduleResult:
    """ScheduleResult model validation."""

    def test_model_dump_json_round_trip(self) -> None:
        """Serialise and deserialise via JSON."""
        result = ScheduleResult(
            total_hours_available=48.0,
            total_hours_planned=2.5,
            total_weeks_needed=1,
            coverage_pct=100,
            skill_summary=[],
            weekly_plan=[],
            skipped_modules=[],
            notes=["All good"],
        )
        json_str = result.model_dump_json()
        restored = ScheduleResult.model_validate_json(json_str)
        assert restored.total_hours_available == 48.0
        assert restored.notes == ["All good"]

    def test_defaults(self) -> None:
        """Optional lists should default to empty."""
        result = ScheduleResult(
            total_hours_available=10.0,
            total_hours_planned=5.0,
            total_weeks_needed=1,
            coverage_pct=100,
            skill_summary=[],
            weekly_plan=[],
        )
        assert result.skipped_modules == []
        assert result.notes == []


class TestStudyConstraints:
    """StudyConstraints model validation."""

    def test_defaults(self) -> None:
        """Default constraints should be sensible."""
        c = StudyConstraints()
        assert c.hours_per_week == 6.0
        assert c.total_weeks == 8
        assert c.prioritize_by_date is False

    def test_custom_values(self) -> None:
        """Custom constraint values should be stored."""
        c = StudyConstraints(
            hours_per_week=10.0,
            total_weeks=4,
            prioritize_by_date=True,
        )
        assert c.hours_per_week == 10.0
        assert c.total_weeks == 4
        assert c.prioritize_by_date is True


# ── compute_schedule() Tests ────────────────────────────────────────


class TestComputeSchedule:
    """Integration tests for the compute_schedule function."""

    def test_returns_schedule_result(self) -> None:
        """compute_schedule should return a ScheduleResult."""
        result = compute_schedule(
            paths_list=_sample_learning_paths(),
            hours_per_week=6.0,
            total_weeks=8,
            prioritize_by_date=False,
        )
        assert isinstance(result, ScheduleResult)

    def test_all_modules_included_no_deadline(self) -> None:
        """Without deadline pressure, all modules are included."""
        result = compute_schedule(
            paths_list=_sample_learning_paths(),
            hours_per_week=6.0,
            total_weeks=8,
            prioritize_by_date=False,
        )
        assert result.coverage_pct == 100
        assert result.skipped_modules == []
        total_items = sum(len(w.items) for w in result.weekly_plan)
        assert total_items == 3  # 3 modules total

    def test_skill_summary_covers_all_skills(self) -> None:
        """Skill summary should include all exam skills."""
        result = compute_schedule(
            paths_list=_sample_learning_paths(),
            hours_per_week=6.0,
            total_weeks=8,
            prioritize_by_date=False,
        )
        skills = {s.exam_skill for s in result.skill_summary}
        assert "Describe cloud concepts" in skills
        assert "Describe Azure architecture" in skills
        assert "Describe Azure services" in skills

    def test_hours_planned_matches_modules(self) -> None:
        """Planned hours should equal sum of module durations."""
        result = compute_schedule(
            paths_list=_sample_learning_paths(),
            hours_per_week=6.0,
            total_weeks=8,
            prioritize_by_date=False,
        )
        expected_hours = round((40 + 50 + 60) / 60, 1)
        assert result.total_hours_planned == expected_hours

    def test_prioritize_by_date_skips_modules(self) -> None:
        """With tight deadline, excess modules are skipped."""
        result = compute_schedule(
            paths_list=_sample_learning_paths(),
            hours_per_week=1.0,  # 1h/week
            total_weeks=1,  # only 1 week = 1h total
            prioritize_by_date=True,
        )
        assert len(result.skipped_modules) > 0
        assert result.coverage_pct < 100

    def test_weekly_plan_hours_consistent(self) -> None:
        """Sum of weekly hours should match total planned."""
        result = compute_schedule(
            paths_list=_sample_learning_paths(),
            hours_per_week=6.0,
            total_weeks=8,
            prioritize_by_date=False,
        )
        weekly_total = sum(w.hours for w in result.weekly_plan)
        assert abs(weekly_total - result.total_hours_planned) < 0.1

    def test_empty_paths_produces_empty_schedule(self) -> None:
        """Empty input produces an empty schedule."""
        result = compute_schedule(
            paths_list=[],
            hours_per_week=6.0,
            total_weeks=8,
            prioritize_by_date=False,
        )
        assert result.weekly_plan == []
        assert result.total_hours_planned == 0

    def test_skipped_modules_are_typed(self) -> None:
        """Skipped modules should be SkippedModule instances."""
        result = compute_schedule(
            paths_list=_sample_learning_paths(),
            hours_per_week=1.0,
            total_weeks=1,
            prioritize_by_date=True,
        )
        for mod in result.skipped_modules:
            assert isinstance(mod, SkippedModule)
            assert mod.module  # non-empty
            assert mod.learning_path  # non-empty


# ── schedule_study_plan() @ai_function wrapper ──────────────────────


class TestScheduleStudyPlanWrapper:
    """Tests for the @ai_function JSON wrapper."""

    def test_returns_valid_json(self) -> None:
        """Wrapper should return valid JSON string."""
        paths_json = json.dumps(_sample_learning_paths())
        result_json = schedule_study_plan(
            learning_paths=paths_json,
            hours_per_week=6.0,
            total_weeks=8,
            prioritize_by_date=False,
        )
        parsed = json.loads(result_json)
        assert "total_hours_planned" in parsed
        assert "weekly_plan" in parsed

    def test_invalid_json_returns_error(self) -> None:
        """Invalid JSON input should return error object."""
        result_json = schedule_study_plan(
            learning_paths="not valid json",
            hours_per_week=6.0,
            total_weeks=8,
            prioritize_by_date=False,
        )
        parsed = json.loads(result_json)
        assert "error" in parsed

    def test_output_matches_schedule_result_schema(self) -> None:
        """Wrapper JSON should be parseable as ScheduleResult."""
        paths_json = json.dumps(_sample_learning_paths())
        result_json = schedule_study_plan(
            learning_paths=paths_json,
            hours_per_week=6.0,
            total_weeks=8,
            prioritize_by_date=False,
        )
        result = ScheduleResult.model_validate_json(result_json)
        assert result.coverage_pct == 100
        assert len(result.weekly_plan) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
