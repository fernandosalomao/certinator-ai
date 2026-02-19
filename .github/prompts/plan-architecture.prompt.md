---
name: Plan Architecture
description: Create a detailed architecture plan.
agent: CertinatorAIPlanner
model: [Claude Opus 4.6 (copilot), GPT-5.2 (copilot)]
tools: [execute, read, edit, search, web, agent, todo]

---
Help me create a detailed architecture for the Certinator AI project, a multi-agent system for Microsoft certification exam preparation.

Delegate to subagent `AIAgentExpert` when is needed as he is the AI Expert (specially in Microsoft Agent Framework and Azure AI Foundry) and can help with best practices, patterns, and technical guidance.

The outcome will be used to increment the [System Architecture and Design Principles](../../ARCHITECTURE.md) documentation, so please ensure the architecture plan is comprehensive and well-structured. This will be used for implementation, so include technical details, agent roles, interactions, and tool integrations.

#  Requirements
The solution must:
- Implement a **multi-agent system** aligned with the **scenario** (student preparation for Microsoft certification exams).
- Demonstrate **reasoning** and multi-step decision-making across agents.
- Integrate with **external tools**, APIs, and/or MCP (Model Context Protocol) servers to meaningfully extend agent capabilities (e.g., learning content retrieval, assessment generation, scheduling, notifications, data access, or evaluations).
- Be **demoable** (live or recorded) and clearly explain the agent interactions.
- Include **clear documentation** in the repository describing: agent roles and responsibilities, reasoning flow and orchestration logic, tools/API/MCP integrations.
- Use of **evaluations**, **telemetry**, or **monitoring**
- Advanced **reasoning patterns** (planner–executor, critics, reflection loops)
- **Responsible AI** considerations (guardrails, validation, fallbacks)

## Tech Stack

- **SDK / Framework**: Microsoft Agent Framework (MAF) for building and orchestrating agents and leveraging Azure AI Foundry agents (v2) for LLM capabilities
- **Programming Language**: Python 3.10+

## Criteria to focus on:
| Criterion | Description |
|-----------|--------|
| **Accuracy & Relevance** | — Solution meets challenge requirements, aligns with the scenario, and produces correct, relevant outputs |
| **Reasoning & Multi-step Thinking** | — Clear problem decomposition, structured reasoning, and effective agent collaboration |
| **Creativity & Originality** | — Novel ideas, unique agent roles, or unexpected but effective execution |
| **User Experience & Presentation** | — Polished, clear, and demoable experience with understandable workflows |
| **Reliability & Safety** | — Robust agent patterns, safe tool/API/MCP usage, and avoidance of common pitfalls |

# 🧠 Reasoning Patterns & Best Practices

When designing your reasoning agents and multi-agent workflows, consider applying well-established reasoning patterns and agentic best practices to improve robustness, transparency, and outcomes.

## Common reasoning patterns to explore include:

1. **Planner–Executor:** Separate agents responsible for planning (breaking down the problem) and execution (carrying out tasks step by step).
1. **Critic / Verifier:** Introduce an agent that reviews outputs, checks assumptions, and validates reasoning before final responses are returned.
1. **Self-reflection & Iteration:** Allow agents to reflect on intermediate results and refine their approach when confidence is low or errors are detected.
1. **Role-based specialization:** Assign clear responsibilities to each agent to reduce overlap and improve reasoning quality.

## Best practices for building with Microsoft Foundry:

1. Use **telemetry**, logs, and visual workflows in Foundry to understand how agents reason and collaborate.
    - Explore Foundry built-in monitoring tools to track agent interactions and performance: [Foundry Control Plane](https://learn.microsoft.com/azure/ai-foundry/control-plane/overview?view=foundry)
1. Apply **evaluation** strategies (e.g., test cases, scoring rubrics, or human-in-the-loop reviews) to continuously improve agent behavior.
    - [Evaluate generative AI models and applications by using Microsoft Foundry built-in features](https://learn.microsoft.com/azure/ai-foundry/how-to/evaluate-generative-ai-app?view=foundry&preserve-view=true)
    - [Evaluate your AI agents with the Microsoft Foundry SDK](https://learn.microsoft.com/azure/ai-foundry/how-to/develop/cloud-evaluation?view=foundry&tabs=python)
1. Build with **Responsible AI** principles in mind, at both application and data layers.
    - [Responsible AI in Microsoft Foundry](https://learn.microsoft.com/azure/ai-foundry/responsible-use-of-ai-overview?view=foundry)

