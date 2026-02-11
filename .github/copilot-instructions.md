# Certinator AI — Copilot Instructions

## Project Overview

Multi-agent system for Microsoft certification exam preparation, built on the **Agent Framework** (`agent_framework`) with **Azure AI Foundry** as the LLM provider. Competes in the [Agents League — Reasoning Agents track](https://github.com/microsoft/agentsleague).

## Architecture

Two-tier orchestration using Agent Framework workflow builders:

1. **Magentic (top-level)** — `src/workflows/orchestration_workflow.py` uses `MagenticBuilder` with the Orchestrator as manager. It dynamically routes to participants:
   - `StudyPlanWorkflow` (sub-workflow wrapped as an agent via `.as_agent()`)
   - `AssessmentAgent` — practice questions & scoring
   - `CertificationAgent` — exam info lookup

2. **Sequential (sub-workflow)** — `src/workflows/study_plan_workflow.py` uses `SequentialBuilder` to chain:
   `LearningPathCurator → StudyPlanGenerator → ReminderAgent`

### Agent Pattern

Each agent file in `src/agents/` exports only two string constants — no classes:
- `*_INSTRUCTIONS` — the system prompt (multi-line string)
- `*_DESCRIPTION` — one-line summary for the orchestrator

Agents are instantiated in workflow builder functions via `provider.create_agent(name, description, instructions)`. Do **not** subclass or add methods to agent files.

### Data Models

All models live in `src/models/` and use **Pydantic v2** `BaseModel` with `Field(...)` descriptors:
- `StudentProfile` — student input (certification target, schedule, learning style)
- `StudyPlanMilestones` / `StudyMilestone` / `LearningResource` — study plan output
- `AssessmentResults` / `QuestionResult` — practice exam scoring

Models are re-exported from `src/models/__init__.py`. Import from there: `from src.models import StudentProfile`.

## Key Conventions

- **Imports**: use `from src.agents.<module> import ...` and `from src.models import ...` (project root is on `sys.path`)
- **Async**: workflow builders are `async def` since `provider.create_agent()` is async. The entrypoint in `main.py` bridges sync→async with `asyncio`
- **Environment**: requires `.env` with `AZURE_AI_PROJECT_ENDPOINT` and `AZURE_AI_MODEL_DEPLOYMENT_NAME`. Auth via `AzureCliCredential`
- **Provider lifecycle**: `AzureAIAgentsProvider` and `AzureCliCredential` need `__aenter__` before use (see `main.py:_build_workflow`)
- **Copyright header**: every `.py` file starts with `# Copyright (c) Certinator AI. All rights reserved.`
- **Module docstrings**: every `.py` file has a module-level docstring after the copyright line

## Running

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py              # launches DevUI at http://localhost:8080
```

## Adding a New Agent

1. Create `src/agents/<name>_agent.py` with `<NAME>_INSTRUCTIONS` and `<NAME>_DESCRIPTION` constants
2. Register it as a participant in the appropriate workflow builder (`orchestration_workflow.py` or `study_plan_workflow.py`)
3. If it needs structured I/O, add a Pydantic model in `src/models/` and re-export from `__init__.py`

## Adding a New Workflow

1. Create `src/workflows/<name>_workflow.py` with an `async def build_<name>_workflow(provider)` function
2. Use `SequentialBuilder` for pipelines or `MagenticBuilder` for dynamic orchestration
3. To nest inside the top-level orchestration, wrap with `.as_agent()` and add to participants in `orchestration_workflow.py`