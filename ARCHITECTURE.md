# Certinator AI — System Architecture

Multi-agent workflow system for Microsoft certification exam preparation, built on **Microsoft Agent Framework (MAF)** with a graph-based workflow engine, HITL (human-in-the-loop) interactions, and critic-validated outputs.

---

## High-Level Overview

```
┌──────────────────────────────────────────────────────────────────┐
│  Frontend (Next.js + CopilotKit)                                 │
│    └── POST /api/copilotkit → HttpAgent → Agent Framework HTTP   │
└──────────────────────────────────────────────────────────────────┘
                              │
                    HTTP / AG-UI Protocol
                              │
┌──────────────────────────────────────────────────────────────────┐
│  Backend (Python — Agent Framework)                              │
│                                                                  │
│    app.py  →  workflow.py  →  WorkflowBuilder graph              │
│             (6 agents, 7 executors, graph-based routing)         │
│                                                                  │
│    Run modes: HTTP server (default) │ AG-UI │ CLI                │
└──────────────────────────────────────────────────────────────────┘
                              │
                   Azure AI Foundry (LLMs)
                   Microsoft Learn MCP (docs)
```

---

## Workflow Graph Topology

The workflow is a directed graph built with `WorkflowBuilder`. The **CoordinatorRouter** is the start node; it classifies user intent and emits a typed `RoutingDecision` that switch-case edges route to specialist handlers.

```
CoordinatorRouter (start)
    │
    └── switch-case on RoutingDecision.route
          │
          ├── "cert_info"  → CertInfoHandler ──► CriticExecutor
          │                                       ├── PASS → emit to user
          │                                       └── FAIL → RevisionRequest → CertInfoHandler (loop)
          │
          ├── "study_plan" → LearningPathFetcherHandler
          │                        │ (LearningPathsData)
          │                        ▼
          │                  StudyPlanSchedulerHandler ──► CriticExecutor
          │                                                ├── PASS → PostStudyPlanHandler
          │                                                │             ├── HITL YES → PracticeQuizOrchestrator
          │                                                │             └── HITL NO  → end
          │                                                └── FAIL → RevisionRequest → StudyPlanScheduler (loop)
          │
          ├── "practice"   → PracticeQuizOrchestrator (HITL quiz loop)
          │                        ├── PASS (≥70%)  → congratulations + exam link
          │                        └── FAIL (<70%)  → HITL study plan offer
          │                              ├── YES → StudyPlanFromQuizRequest → LearningPathFetcher pipeline
          │                              └── NO  → end
          │
          └── default      → GeneralHandler (echo coordinator response)
```

### Cross-Route Flows

The architecture supports **bidirectional routing** between study plan and practice features:

- **Practice → Study Plan**: When a student fails a quiz and accepts the study plan offer, a `StudyPlanFromQuizRequest` routes to the `LearningPathFetcherHandler`, entering the full study plan pipeline with topic data scoped to weak areas.
- **Study Plan → Practice**: After a study plan passes critic review, `PostStudyPlanHandler` asks via HITL if the student wants practice questions. On acceptance, a `RoutingDecision` routes to `PracticeQuizOrchestrator`.

---

## Layer Architecture

### 1. Entrypoint — `src/app.py`

| Mode | Description |
|------|-------------|
| **HTTP server** (default) | FastAPI + Uvicorn; used by `agentdev` / AI Toolkit Agent Inspector |
| **AG-UI** | FastAPI with AG-UI endpoint; bridges to CopilotKit frontend |
| **CLI** | Interactive REPL for terminal testing |

Tracing is configured via OpenTelemetry (gRPC port 4317) for the AI Toolkit trace viewer.

### 2. Workflow — `src/workflow.py`

Factory function `build_workflow()` that:
1. Creates all 6 agents (with credentials and tools)
2. Instantiates all 7 executors
3. Wires the graph with `WorkflowBuilder` (switch-case + conditional edges)
4. Returns `(workflow.as_agent(), credential)` for HTTP/CLI serving

**Routing predicates:**

| Predicate | Purpose |
|-----------|---------|
| `_is_route(route)` | Match `RoutingDecision` by route field |
| `_revision_for(executor_id)` | Match `RevisionRequest` by source executor |
| `_is_approved_study_plan` | Match `ApprovedStudyPlanOutput` for post-study-plan HITL |
| `_is_study_plan_from_quiz` | Match `StudyPlanFromQuizRequest` for post-quiz routing |

### 3. Executors — `src/executors/`

Executors are stateless workflow nodes that receive typed messages, call agents or tools, and emit typed messages downstream. They use `@handler` for typed dispatch and `@response_handler` for HITL replies.

| Executor | ID | Input(s) | Output(s) | Description |
|----------|----|----------|-----------|-------------|
| **CoordinatorRouter** | `coordinator-router` | `list[ChatMessage]` | `RoutingDecision` | Intent classification and routing via structured LLM output |
| **CertInfoHandler** | `cert-info-handler` | `RoutingDecision`, `RevisionRequest` | `SpecialistOutput` | Certification info retrieval using MS Learn MCP |
| **LearningPathFetcherHandler** | `learning-path-fetcher` | `RoutingDecision`, `StudyPlanFromQuizRequest` | `LearningPathsData` | Fetches exam topics, weights, and learning paths from MS Learn MCP |
| **StudyPlanSchedulerHandler** | `study-plan-scheduler` | `LearningPathsData`, `RevisionRequest` | `SpecialistOutput` | Generates week-by-week study plan using deterministic scheduling tool + LLM formatting |
| **CriticExecutor** | `critic-executor` | `SpecialistOutput` | `emit` / `RevisionRequest` / `ApprovedStudyPlanOutput` | Validates specialist output; PASS emits to user (or forwards study plans to `PostStudyPlanHandler`), FAIL sends revision request. Max 2 iterations, then auto-approves. |
| **PostStudyPlanHandler** | `post-study-plan-handler` | `ApprovedStudyPlanOutput` | `RoutingDecision` (to practice) or end | HITL: emits study plan, offers practice questions |
| **PracticeQuizOrchestrator** | `practice-handler` | `RoutingDecision` | `StudyPlanFromQuizRequest` or end | HITL quiz loop: generates questions upfront, presents one-by-one, scores deterministically, generates feedback report, offers study plan on failure |
| **GeneralHandler** | `general-handler` | `RoutingDecision` | emit | Echoes coordinator's direct response for general queries |

### 4. Agents — `src/agents/`

Each agent is an `AzureAIClient`-backed chat agent with specific instructions and optional tools. Created by factory functions in respective modules.

| Agent | Model | Tools | Purpose |
|-------|-------|-------|---------|
| **Coordinator** | `gpt-4.1-mini` | — | Intent classification → structured `CoordinatorResponse` |
| **CertInfo** | `gpt-4.1` | MS Learn MCP | Certification information retrieval |
| **LearningPathFetcher** | `gpt-4.1` | MS Learn MCP | Structured topic/learning-path extraction |
| **StudyPlan** | `gpt-4.1` | `schedule_study_plan` | Study plan formatting (scheduling is deterministic) |
| **Practice** | `gpt-4.1` | — | Mode 1: JSON question generation. Mode 2: Markdown feedback reports |
| **Critic** | `gpt-4.1-mini` | — | Content validation → `CriticVerdictResponse` |

### 5. Data Models — `src/executors/models.py`

All inter-executor messages are typed Pydantic models or dataclasses.

#### Routing & Coordination

| Model | Flow | Description |
|-------|------|-------------|
| `RoutingDecision` | Coordinator → switch-case | Route, task, certification, context, optional response |
| `CoordinatorResponse` | LLM → Coordinator | Strict `response_format` schema |

#### Specialist Pipeline

| Model | Flow | Description |
|-------|------|-------------|
| `SpecialistOutput` | Specialist → Critic | Content + metadata for validation |
| `LearningPathsData` | Fetcher → StudyPlanScheduler | Topics array + original routing decision |
| `RevisionRequest` | Critic → Specialist | FAIL feedback + iteration counter |
| `ApprovedStudyPlanOutput` | Critic → PostStudyPlanHandler | Approved study plan for HITL offer |

#### Learning Path Schemas

| Model | Description |
|-------|-------------|
| `LearningPathFetcherResponse` | Structured response schema for the fetcher agent |
| `LearningPathTopic` | Topic name, weight, and learning paths |
| `LearningPathItem` | Single MS Learn path (name, URL, duration) |

#### Practice Quiz

| Model | Description |
|-------|-------------|
| `PracticeQuestion` | Single MC question (text, options A-D, answer, explanation, topic, difficulty) |
| `QuizState` | Full quiz lifecycle state (questions, answers, index, status) |
| `StudyPlanFromQuizRequest` | Post-quiz → study plan routing (certification, weak topics, score) |

#### Critic

| Model | Description |
|-------|-------------|
| `CriticVerdict` | Parsed verdict with confidence and feedback |
| `CriticVerdictResponse` | Strict `response_format` schema for the critic LLM |

#### HITL Payloads (dataclasses)

| Dataclass | Used by | Purpose |
|-----------|---------|---------|
| `QuizQuestionRequest` | `PracticeQuizOrchestrator` | Present a quiz question |
| `PostQuizStudyPlanOffer` | `PracticeQuizOrchestrator` | Offer study plan after failed quiz |
| `PostStudyPlanPracticeOffer` | `PostStudyPlanHandler` | Offer practice questions after study plan |

### 6. Tools — `src/tools/`

| Tool | Type | Used by | Description |
|------|------|---------|-------------|
| **MS Learn MCP** | `MCPStreamableHTTPTool` | CertInfo, LearningPathFetcher agents | Queries `learn.microsoft.com/api/mcp` for documentation |
| **`score_quiz`** | Python function | PracticeQuizOrchestrator | Deterministic quiz scoring: overall %, per-topic breakdown, weak topics (<70%) |
| **`schedule_study_plan`** | `@ai_function` | StudyPlan agent | Computes week-by-week study schedule from topics JSON + constraints |

### 7. Configuration — `src/config.py`

| Variable | Env Var | Default | Description |
|----------|---------|---------|-------------|
| `FOUNDRY_PROJECT_ENDPOINT` | `FOUNDRY_PROJECT_ENDPOINT` | `""` | Azure AI Foundry project endpoint |
| `DEFAULT_PRACTICE_QUESTIONS` | `DEFAULT_PRACTICE_QUESTIONS` | `10` | Default quiz size |

### 8. Frontend — `frontend/`

Next.js + CopilotKit application. The API route (`app/api/copilotkit/route.ts`) bridges CopilotKit requests to the backend via AG-UI protocol using `HttpAgent`.

| Env Var | Default | Description |
|---------|---------|-------------|
| `CERTINATOR_AGENT_URL` / `AGENT_URL` | `http://127.0.0.1:8000/` | Backend agent HTTP endpoint |

### CopilotKit Integration (Frontend ↔ Backend Glue)

The frontend uses CopilotKit hooks to bridge the MAF backend with a rich React UI. The AG-UI protocol is the transport layer between CopilotKit and the Agent Framework HTTP server.

| CopilotKit Feature | Hook / Component | Purpose |
|--------------------|-----------------|---------|
| **Human-in-the-Loop** | `useHumanInTheLoop("quiz_answer")` | Renders a `QuizCard` with clickable A/B/C/D buttons instead of typing answers in chat |
| **Human-in-the-Loop** | `useHumanInTheLoop("study_plan_offer")` | Renders an `OfferCard` with "Create study plan" / "Maybe later" buttons after a failed quiz |
| **Human-in-the-Loop** | `useHumanInTheLoop("practice_offer")` | Renders an `OfferCard` with "Start practice" / "Not now" buttons after a study plan is delivered |
| **Shared State (Read)** | `useCoAgent` | Reads `active_quiz_state` from the backend's shared state to drive the `QuizDashboard` component outside the chat |
| **Agent State Render** | `useCoAgentStateRender` | Renders quiz progress inline in the chat window as the student answers questions |
| **Readables** | `useCopilotReadable` | Exposes user preferences (difficulty, question count, locale) as context that the backend agent can use |

**Component mapping:**

| Component | CopilotKit Hook | Renders |
|-----------|----------------|---------|
| `CertinatorHooks` | All hooks above | Invisible — registers all hooks inside the CopilotKit provider |
| `QuizCard` | `useHumanInTheLoop` | Multiple-choice question with option buttons |
| `OfferCard` | `useHumanInTheLoop` | Yes/No decision card for study plan and practice offers |
| `QuizDashboard` | `useCoAgent` | Progress bar, topic badges, and current question indicator |

---

## HITL (Human-in-the-Loop) Pattern

The system uses the MAF HITL pattern for interactive features:

1. An executor calls `ctx.request_info(request_data=<payload>, response_type=str)`
2. The workflow pauses and emits a `RequestInfoEvent` to the client
3. The client collects the user's response
4. The client calls `send_responses_streaming({request_id: response})`
5. The `@response_handler` decorated method receives the original request + response
6. The executor continues processing (present next question, route to another handler, or end)

**HITL points in the system:**

| Executor | HITL Action | User Input | Frontend Component |
|----------|-------------|------------|-------------------|
| `PracticeQuizOrchestrator` | Present quiz question | A/B/C/D answer | `QuizCard` |
| `PracticeQuizOrchestrator` | Offer study plan after failed quiz | yes/no | `OfferCard` |
| `PostStudyPlanHandler` | Offer practice after study plan | yes/no | `OfferCard` |

---

## Critic Validation Loop

All specialist outputs (except practice quizzes, which are self-contained) pass through `CriticExecutor`:

1. Specialist handler emits `SpecialistOutput`
2. Critic agent validates content against quality criteria
3. **PASS** → output emitted to user (or forwarded to `PostStudyPlanHandler` for study plans)
4. **FAIL** → `RevisionRequest` sent back to source handler (conditional edges route by `source_executor_id`)
5. Max iterations: **2** — auto-approves with disclaimer after cap

---

## File Structure

```
src/
├── app.py                          # Entrypoint (HTTP / AG-UI / CLI)
├── config.py                       # Environment configuration
├── workflow.py                     # Workflow graph builder
├── agents/
│   ├── __init__.py                 # Re-exports all agent factories
│   ├── coordinator_agent.py        # Intent classification (gpt-4.1-mini)
│   ├── cert_info_agent.py          # Certification info (gpt-4.1 + MCP)
│   ├── learning_path_fetcher_agent.py  # Topic extraction (gpt-4.1 + MCP)
│   ├── study_plan_agent.py         # Study plan formatting (gpt-4.1)
│   ├── practice_agent.py           # Question gen + feedback (gpt-4.1)
│   └── critic_agent.py             # Quality validation (gpt-4.1-mini)
├── executors/
│   ├── __init__.py                 # Shared helpers (emit_response, etc.)
│   ├── models.py                   # All typed data models
│   ├── coordinator.py              # CoordinatorRouter
│   ├── cert_info.py                # CertInfoHandler
│   ├── learning_path_fetcher.py    # LearningPathFetcherHandler
│   ├── study_plan.py               # StudyPlanSchedulerHandler
│   ├── critic.py                   # CriticExecutor
│   ├── post_study_plan.py          # PostStudyPlanHandler (HITL)
│   └── practice.py                 # PracticeQuizOrchestrator (HITL)
├── tools/
│   ├── __init__.py
│   ├── mcp.py                      # MS Learn MCP tool factory
│   ├── practice.py                 # Deterministic quiz scoring
│   └── schedule.py                 # Study plan scheduling (@ai_function)
frontend/
├── app/
│   ├── page.tsx                    # Main UI + quiz dashboard
│   ├── layout.tsx                  # Root layout (CopilotKit provider)
│   ├── types.ts                    # Shared TS types (mirrors models.py)
│   ├── globals.css                 # Global styles (incl. quiz/offer cards)
│   ├── components/
│   │   ├── CertinatorHooks.tsx     # All CopilotKit hook registrations
│   │   ├── QuizCard.tsx            # HITL quiz answer card (A/B/C/D buttons)
│   │   ├── OfferCard.tsx           # HITL yes/no offer card
│   │   └── QuizDashboard.tsx       # Real-time quiz progress panel
│   └── api/copilotkit/route.ts     # CopilotKit → Agent Framework bridge
```

---

## Design Principles

1. **Typed message passing**: All inter-executor data flows through Pydantic models — no raw strings or dicts at boundaries.
2. **Deterministic where possible**: Scoring (`score_quiz`) and scheduling (`schedule_study_plan`) are Python functions — LLMs never do arithmetic.
3. **LLMs for language**: Agents handle classification, generation, and formatting — tasks where language understanding adds value.
4. **Single-responsibility executors**: Each executor owns one concern; new features add new executors rather than growing existing ones.
5. **Critic gate**: Specialist outputs pass through quality validation before reaching the user, with bounded revision loops.
6. **HITL for decisions**: Workflow pauses for meaningful student choices (answers, study plan acceptance) using the MAF `request_info`/`response_handler` pattern.
7. **Reusable agents**: The same agent instance (e.g., `learning_path_agent`) can be shared across multiple executors that need topic data.