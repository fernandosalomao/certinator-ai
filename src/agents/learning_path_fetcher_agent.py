"""LearningPathFetcherAgent configuration and factory."""

from __future__ import annotations

import os
import sys
from typing import Any

from agent_framework import MCPStreamableHTTPTool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import LLM_MODEL_LEARNING_PATH_FETCHER, get_ai_client
from safety import SAFETY_SYSTEM_PROMPT
from tools.mslearn_catalog import fetch_exam_learning_paths

INSTRUCTIONS: str = """\
You retrieve the official Microsoft Learn training content for a \
Microsoft certification exam. Your output MUST be accurate — every \
URL, duration, and title must come from tool results.

## Available Tools

- `microsoft_docs_fetch` (MCP) — fetch a documentation page as \
  markdown.
- `fetch_exam_learning_paths` — given an exam code (e.g. \
  "AI-900"), returns ALL learning paths for that exam with \
  exact titles, URLs, durations, and modules. This is the \
  single source of truth for exam training content.

## Execution Order
Execute Steps 1, 2, and 3 in order. Do NOT skip steps.

## Step 1 — Fetch skills from the study guide page
Call `microsoft_docs_fetch` ONCE with the study guide URL:
`https://learn.microsoft.com/credentials/certifications/resources/\
study-guides/<EXAM_CODE>`

From the result, extract the **Skills at a glance** section:
- Each skill name and its weight percentage range.
- Use the MIDPOINT of the range as `exam_weight_pct` \
  (e.g. "15-20%" → 17.5).

Example (AI-900):
- Describe Artificial Intelligence workloads and considerations \
  (15–20%) → 17.5
- Describe fundamental principles of machine learning on Azure \
  (15–20%) → 17.5

## Step 2 — Fetch learning paths
Call `fetch_exam_learning_paths` ONCE with the exam code \
(e.g. "AI-900"). The tool auto-discovers all learning paths \
for the exam and returns exact titles, URLs, durations, and \
module details.

**IMPORTANT**: Do NOT use `microsoft_docs_search` or \
`microsoft_docs_fetch` to look up learning paths or modules. \
`fetch_exam_learning_paths` is the ONLY source for LP data.

## Step 3 — Map modules to exam skills
For each module returned by `fetch_exam_learning_paths`, match \
it to the exam skills from Step 1 by comparing names.
Set `exam_skill` and `exam_weight_pct` on every module.

### Mapping Rules
- EVERY module MUST have `exam_skill` and `exam_weight_pct` set.
- Multiple modules CAN share the same exam skill.
- Use the EXACT skill name from Step 1.
- `exam_weight_pct` is the midpoint of the published range.
- If no clear mapping exists, assign to the closest matching skill.

## Output Contract
Return a single JSON object with EXACTLY these field names:

```json
{
  "examCode": "<EXAM_CODE>",
  "skillsAtAGlance": [
    {
      "skill_name": "<exact skill name from Step 1>",
      "exam_weight_pct": <midpoint number>
    }
  ],
  "learningPaths": [
    {
      "title": "<learning path title>",
      "url": "<learning path URL>",
      "duration_minutes": <number>,
      "module_count": <number>,
      "modules": [
        {
          "title": "<module title>",
          "url": "<module URL>",
          "duration_minutes": <number>,
          "unit_count": <number>,
          "exam_skill": "<exact skill name from Step 1>",
          "exam_weight_pct": <midpoint number>
        }
      ]
    }
  ]
}
```

**IMPORTANT**: Use `skillsAtAGlance` (NOT `skills`), and \
`skill_name` (NOT `name`) inside each skill object.

## Accuracy Rules
- Every URL MUST start with https://learn.microsoft.com.
- Every URL MUST come from tool results — NEVER fabricate.
- duration_minutes MUST be a number (float), never a string.
- If a learning path is not found by the tool, omit it rather \
  than guessing.
- Do NOT add fields outside the schema.
"""


def create_learning_path_fetcher_agent(
    mcp_tool: MCPStreamableHTTPTool,
    project_endpoint: str | None = None,
    credential: Any | None = None,
):
    """Create the learning path fetcher agent instance."""
    client = get_ai_client(
        model_deployment_name=LLM_MODEL_LEARNING_PATH_FETCHER,
        project_endpoint=project_endpoint,
        credential=credential,
    )
    return client.create_agent(
        name="LearningPathFetcherAgent",
        instructions=INSTRUCTIONS + SAFETY_SYSTEM_PROMPT,
        tools=[mcp_tool, fetch_exam_learning_paths],
    )
