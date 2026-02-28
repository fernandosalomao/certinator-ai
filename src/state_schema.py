"""
Certinator AI — AG-UI State Schema Configuration

Defines the predict_state_config and state_schema mappings used by
CopilotKit's AG-UI bridge for frontend shared-state synchronisation.
"""


def build_predict_state_config() -> dict[str, dict[str, str]]:
    """Return AG-UI predict_state_config mapping synthetic tool calls to state keys."""
    return {
        "workflow_progress": {
            "tool": "update_workflow_progress",
            "tool_argument": "progress",
        },
        "active_quiz_state": {
            "tool": "update_active_quiz_state",
            "tool_argument": "quiz_state",
        },
        "post_study_plan_context": {
            "tool": "update_post_study_plan_context",
            "tool_argument": "context",
        },
    }


def build_state_schema() -> dict[str, dict[str, str]]:
    """Return AG-UI state schema used by frontend shared-state hooks."""
    return {
        "active_quiz_state": {
            "type": "object",
            "description": "Current quiz session state",
        },
        "post_study_plan_context": {
            "type": "object",
            "description": "Post-study-plan context for HITL practice offer",
        },
        "workflow_progress": {
            "type": "object",
            "description": "Current multi-step workflow execution progress",
        },
    }
