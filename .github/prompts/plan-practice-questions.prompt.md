---
name: planPracticeQuestions
description: Plan the implementation of the practice question agent, including its interactions with other agents and tools.
agent: AIAgentExpert
model: [Claude Opus 4.6 (copilot)]
tools: [vscode, execute, read, agent, edit, search, web, 'github/*', 'microsoftdocs/mcp/*', ms-python.python/getPythonEnvironmentInfo, ms-python.python/getPythonExecutableCommand, ms-python.python/installPythonPackage, ms-python.python/configurePythonEnvironment, ms-windows-ai-studio.windows-ai-studio/aitk_get_ai_model_guidance, ms-windows-ai-studio.windows-ai-studio/aitk_get_agent_model_code_sample, ms-windows-ai-studio.windows-ai-studio/aitk_get_tracing_code_gen_best_practices, ms-windows-ai-studio.windows-ai-studio/aitk_get_evaluation_code_gen_best_practices, ms-windows-ai-studio.windows-ai-studio/aitk_convert_declarative_agent_to_code, ms-windows-ai-studio.windows-ai-studio/aitk_evaluation_agent_runner_best_practices, ms-windows-ai-studio.windows-ai-studio/aitk_evaluation_planner, ms-windows-ai-studio.windows-ai-studio/aitk_get_custom_evaluator_guidance, ms-windows-ai-studio.windows-ai-studio/check_panel_open, ms-windows-ai-studio.windows-ai-studio/get_table_schema, ms-windows-ai-studio.windows-ai-studio/data_analysis_best_practice, ms-windows-ai-studio.windows-ai-studio/read_rows, ms-windows-ai-studio.windows-ai-studio/read_cell, ms-windows-ai-studio.windows-ai-studio/export_panel_data, ms-windows-ai-studio.windows-ai-studio/get_trend_data, ms-windows-ai-studio.windows-ai-studio/aitk_list_foundry_models, ms-windows-ai-studio.windows-ai-studio/aitk_agent_as_server, ms-windows-ai-studio.windows-ai-studio/aitk_add_agent_debug, ms-windows-ai-studio.windows-ai-studio/aitk_gen_windows_ml_web_demo, todo]
---

# Practice Question Agent Implementation Plan
Plan the implementation of the practice question feature, including its interactions with other agents and tools.
Review [PROJECT](../../PROJECT.md) document for feature overview.
Review the #codebase

After PLAN is generated I might consider the implementation.

## How is that feature triggered?
### coordinator -> practice handler -> learning path fetcher -> practice question generation (assumptions)
Initial Student Input: Give me questions about AZ-900
The practice handler will need to generate the questions based on the certification learning path scope, at least 1 question per topic.

### coordinator - learning path fetcher - study plan generation - optional(practice question generation)
After study plan generation, the user is asked if he wants some questions to practice based on the study plan. If yes, the Practice Question Generation agent is triggered.
This will require HITL

The practice handler will need to generate the questions based on the study plan scope, at least 1 question per topic.

## presentation of the questions
The questions will be presented to the student one-by-one, he will select A, B, C or D.

The LLM will generate the questions before the presentation, not on the fly, to avoid latency issues.

At the end of the questions, the student will get a explanation of the correct answer for each question, and the overall score, feedback on which topics he needs to focus more, etc.

If he passes (> 70%), he will he will be congratulated and encouraged to schedule the exam, with a link to the scheduling page.

if he fails, he will be asked if he wants to generate a study plan based on his results, to focus on the topics he struggled the most.

if he accepts route to study plan generation workflow with the topics that he needs help with, if not, end the conversation.

# Considerations for Implementation:
- An initial implementation already exists in the codebase, but it is not complete and might need to be reworked to fit into the overall architecture. Feel free to ignore the existing implementation if you think it is not useful.
- Simplify this architecture or add more components as needed.
- Reuse agents if possible, for example, the learning path fetcher can be reused to get the topics for the practice question generation.
- Add more nested workflows if needed

# Code references that might be useful for this implementation:
- #fetch https://github.com/microsoft/agent-framework/blob/python-1.0.0b260107/python/samples/getting_started/workflows/state-management/workflow_kwargs.py
- #fetch https://github.com/microsoft/agent-framework/blob/python-1.0.0b260107/python/samples/getting_started/workflows/human-in-the-loop/guessing_game_with_human_input.py
