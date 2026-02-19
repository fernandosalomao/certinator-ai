---
name: reviewArchitecture
description: Review a architecture document and provide structured feedback with improvements and questions.
agent: AIAgentExpert
argument-hint: The architecture document or file to review
model: [Claude Opus 4.6 (copilot), GPT-5.2 (copilot)]
tools: [execute, read, edit, search, web, agent, todo]
---
Review [ARCHITECTURE](../../ARCHITECTURE.md) document and deliver a structured, expert-level critique.

Organize your feedback into the following sections:

## Suggested Improvements
Group improvement suggestions by category (e.g., Architecture & Design, Agent/Component Design, Code Patterns, Evaluation & Observability, Security, Responsible AI, Missing Sections). For each suggestion:
- State the issue concisely
- Explain **why** it matters
- Suggest a concrete fix or addition

## Questions to Resolve Before Implementation
Present a table of open questions that should be answered before coding begins, with columns for the question and its impact area (e.g., latency, cost, reliability, UX, project planning).

### Guidelines
- Focus on **operational concerns** (deployment, auth, error resilience, cost) that are commonly under-specified
- Flag **code-level inconsistencies** in reference patterns or examples
- Identify **bottlenecks**, **single points of failure**, and **missing error handling strategies**
- Call out ambiguities in component responsibilities or data flow
- Note any **deprecation risks** or **technical debt** that should be tracked
- Keep feedback actionable — every critique should imply a clear next step
