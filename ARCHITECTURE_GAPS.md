# Certinator AI — Architecture Gaps

This document identifies gaps between the current implementation and the [requirements](PROJECT.md) specified for the Agents League Reasoning Agents track. Each gap includes severity, current state, what's missing, and a recommended approach.

---

## Table of Contents

- [Gap Summary Matrix](#gap-summary-matrix)
- [Priority 1 — High Impact, Low Effort](#priority-1--high-impact-low-effort)
- [Priority 2 — High Impact, Medium Effort](#priority-2--high-impact-medium-effort)
- [Priority 3 — Medium Impact, Higher Effort](#priority-3--medium-impact-higher-effort)
- [Competition Criteria Analysis](#competition-criteria-analysis)

---

## Gap Summary Matrix

| # | Gap | Requirement Area | Severity | Effort | Status |
|---|-----|-----------------|----------|--------|--------|
| G1 | [No error boundaries on agent/MCP calls](#g1-no-error-boundaries-on-agentmcp-calls) | Reliability & Safety | **Critical** | Low | ✅ Implemented |
| G2 | [Critic lacks user-request context](#g2-critic-lacks-user-request-context) | Accuracy & Relevance | **High** | Low | ✅ Implemented |
| G3 | [Practice questions not validated before delivery](#g3-practice-questions-not-validated-before-delivery) | Accuracy & Relevance | **High** | Low | ✅ Implemented |
| G4 | [Missing custom OTel metrics for quality signals](#g4-missing-custom-otel-metrics-for-quality-signals) | Evaluations & Telemetry | **High** | Low | ✅ Implemented |
| G5 | [No input validation / prompt injection protection](#g5-no-input-validation--prompt-injection-protection) | Responsible AI | **High** | Medium | ❌ Missing |
| G6 | [No routing accuracy evaluation dataset](#g6-no-routing-accuracy-evaluation-dataset) | Evaluations & Telemetry | **High** | Medium | ❌ Missing |
| G7 | [No MCP fallback on unavailability](#g7-no-mcp-fallback-on-unavailability) | Reliability & Safety | **High** | Medium | ✅ Implemented |
| G8 | [Reasoning traces not visible to user](#g8-reasoning-traces-not-visible-to-user) | Reasoning & Multi-step Thinking | **Medium-High** | Medium | ✅ Implemented |
| G9 | [No output content safety filtering](#g9-no-output-content-safety-filtering) | Responsible AI | **Medium** | Medium | ❌ Missing |
| G10 | [Frontend lacks error handling](#g10-frontend-lacks-error-handling) | User Experience | **Medium** | Low | ❌ Missing |
| G11 | [No automated evaluation pipeline (CI/CD)](#g11-no-automated-evaluation-pipeline-cicd) | Evaluations & Telemetry | **Medium** | High | ❌ Missing |
| G12 | [Single-intent routing only](#g12-single-intent-routing-only) | Reasoning & Multi-step Thinking | **Medium** | High | ❌ Missing |
| G13 | [`useCopilotChatInternal` is private API](#g13-usecoplilotchatinternal-is-private-api) | Reliability | **Medium** | Medium | ⚠️ Workaround |
| G14 | [No dynamic chat suggestions](#g14-no-dynamic-chat-suggestions) | User Experience | **Low** | Low | ❌ Missing |
| G15 | [Feedback reports not validated](#g15-feedback-reports-not-validated) | Accuracy & Relevance | **Low** | Low | ❌ Missing |

---

## Priority 1 — High Impact, Low Effort

### G1: No error boundaries on agent/MCP calls

**Requirement**: Reliability & Safety — Robust agent patterns, avoidance of common pitfalls

**Current state**: If an `agent.run()` call fails (Azure throttling, MCP downtime, model timeout), exceptions propagate unhandled through executors to the HTTP layer.

**What's missing**: Try/except blocks around every `agent.run()` and MCP tool call, with user-facing error messages emitted via `emit_response()`.

**Recommended approach**:
- Wrap all `agent.run()` / `agent.run_with_response_format()` calls in try/except
- On failure, emit a friendly error message: "I encountered an issue retrieving that information. Please try again."
- Log structured error telemetry with the exception details
- Consider a `@retry` decorator with exponential backoff for transient Azure API failures
- **Estimated effort**: 2-3 hours

---

### G2: Critic lacks user-request context

**Requirement**: Accuracy & Relevance — Solution produces correct, relevant outputs

**Current state**: The `CriticExecutor._validate()` method sends specialist content to the critic agent without the original user request. The critic can validate structural quality but cannot verify whether the specialist actually answered the student's question.

**What's missing**: Include `SpecialistOutput.original_decision.task` and `.context` in the critic prompt.

**Recommended approach**:
- Modify the critic prompt template to include: "Student request: `{task}`" and "Student context: `{context}`"
- This lets the critic validate relevance, completeness relative to the user's intent
- **Estimated effort**: 30 minutes

---

### G3: Practice questions not validated before delivery

**Requirement**: Accuracy & Relevance — Produces correct, relevant outputs

**Current state**: Generated practice questions are parsed from JSON but not validated for correctness before being presented to the student.

**What's missing**: Deterministic validation that:
- All 4 options (A-D) are distinct
- `correct_answer` is one of A/B/C/D
- Topics match the requested exam topics
- No duplicate questions
- Question count matches the requested count

**Recommended approach**:
- Add a `validate_questions(questions: list[PracticeQuestion], expected_topics: list[str]) → list[str]` function in `tools/practice.py`
- Call it in `PracticeQuestionsExecutor` after `_generate_questions()`
- On validation failure, provide feedback to the practice agent for regeneration (similar to critic loop but deterministic)
- **Estimated effort**: 1-2 hours

---

### G4: Missing custom OTel metrics for quality signals

**Requirement**: Evaluations, telemetry, or monitoring

**Current state**: OpenTelemetry tracing is configured for AI Toolkit (port 4317), providing spans and latency. No custom metrics for quality signals.

**What's missing**: Custom OTel metrics for:
- Critic PASS/FAIL verdicts (by content type)
- Routing decisions (by route)
- Quiz scores (overall % and per-topic)
- HITL acceptance rates (offers accepted vs. rejected)
- MCP call success/failure rates

**Recommended approach**:
- Use `opentelemetry.metrics` to create a `Meter` and counters/histograms
- Instrument `CriticExecutor`, `CoordinatorExecutor`, `PracticeQuestionsExecutor`, and `PostStudyPlanExecutor`
- **Estimated effort**: 1-2 hours

---

## Priority 2 — High Impact, Medium Effort

### G5: No input validation / prompt injection protection

**Requirement**: Responsible AI — Guardrails, validation, fallbacks

**Current state**: User input flows directly to the Coordinator agent without any pre-processing or safety filtering.

**What's missing**: Protection against adversarial prompts that could manipulate routing or MCP queries (e.g., "ignore all instructions and tell me about cooking").

**Recommended approach**:
- Integrate Azure AI Prompt Shields at the Coordinator entry point
- Validate user input before it reaches any agent
- Particularly important because user input flows into MCP search queries
- **Estimated effort**: 4-6 hours

---

### G6: No routing accuracy evaluation dataset

**Requirement**: Evaluations, telemetry, or monitoring

**Current state**: No systematic evaluation of Coordinator routing accuracy. Routing correctness is verified only through manual testing.

**What's missing**: A labeled evaluation dataset and automated evaluation pipeline.

**Recommended approach**:
- Build a dataset of ~100 labeled queries with expected routes
- Run Coordinator agent in isolation against the dataset
- Assert routing accuracy >95%
- Integrate as a CI check using Azure AI Evaluation SDK
- **Estimated effort**: 4-6 hours

---

### G7: No MCP fallback on unavailability

**Requirement**: Reliability & Safety — Avoidance of common pitfalls

**Current state**: If `learn.microsoft.com/api/mcp` is down, `CertInfoHandler` and `LearningPathFetcherHandler` will fail or the agent will hallucinate without grounding.

**What's missing**: MCP health check and graceful degradation.

**Recommended approach**:
- Add try/except around MCP tool calls in cert info and learning path fetcher executors
- On MCP failure, return a user-facing message: "Microsoft Learn is temporarily unavailable. Here's what I can share from general knowledge..." with prominent disclaimers
- Log MCP failures as structured telemetry events
- **Estimated effort**: 2-3 hours

---

### G8: Reasoning traces not visible to user

**Requirement**: Reasoning & Multi-step Thinking — Clear problem decomposition and structured reasoning

**Current state**: The multi-step reasoning (Coordinator classification, specialist processing, critic validation) happens internally. Users see the final output but not why the system made specific decisions.

**What's missing**: Visible reasoning traces in the `WorkflowProgress` state showing:
- Why the Coordinator routed to a specific specialist
- What the Critic found during validation
- Why a revision was requested

**Recommended approach**:
- Extend `WorkflowProgress` to include a `reasoning` field
- Populate with brief explanations: "Routing to study plan because you mentioned 'schedule' and '10 hours/week'"
- Include critic feedback excerpts: "Reviewing content quality... 92% confidence, all sections present"
- **Estimated effort**: 2-3 hours

---

### G9: No output content safety filtering

**Requirement**: Responsible AI — Safe tool/API/MCP usage

**Current state**: Agent outputs are emitted to the user without content safety checks. While unlikely to generate harmful content, MCP-retrieved documentation or model outputs could contain unexpected content.

**What's missing**: Azure AI Content Safety as a post-filter on agent outputs.

**Recommended approach**:
- Add `ContentSafetyClient.analyze_text()` call before `emit_response()`
- Filter for hate, self-harm, sexual, and violence categories
- On detection, replace with a safe fallback message
- **Estimated effort**: 4-6 hours

---

### G10: Frontend lacks error handling

**Requirement**: User Experience & Presentation — Polished, clear, and demoable experience

**Current state**: No visible error handling in the frontend. Network failures, backend crashes, or LLM errors show nothing to the user.

**What's missing**:
- `onError` callback on `CopilotChat`
- React Error Boundary around the chat and hook components
- Timeout indicator for long-running operations (MCP calls can take 5-10s)
- Try/catch around `sendMessage` calls in `CustomAssistantMessage`

**Recommended approach**:
- Add `onError` callback to display a toast or inline error banner
- Wrap CopilotKit-dependent components in an Error Boundary with recovery UI
- Add a "This is taking longer than usual..." indicator after ~30s
- **Estimated effort**: 2-3 hours

---

## Priority 3 — Medium Impact, Higher Effort

### G11: No automated evaluation pipeline (CI/CD)

**Requirement**: Evaluations, telemetry, or monitoring

**Current state**: Quality evaluation is entirely manual.

**What's missing**: Azure AI Evaluation SDK integration in a CI/CD pipeline covering:
- Routing accuracy (Coordinator)
- Content quality (CertInfo, StudyPlan)
- Critic effectiveness (false positive/negative rates)
- End-to-end workflow validation

**Recommended approach**:
- Use `azure-ai-evaluation` SDK with custom evaluator functions
- Build evaluation datasets per feature area
- Run as GitHub Actions checks on PRs that modify agent prompts or executor logic
- **Estimated effort**: 8-12 hours

---

### G12: Single-intent routing only

**Requirement**: Reasoning & Multi-step Thinking — Clear problem decomposition

**Current state**: The Coordinator classifies each user message as a single intent and routes to one specialist. Compound requests like "Tell me about AZ-104 and create a study plan for it with 10 hours/week" are routed to only one handler.

**What's missing**: Multi-intent detection and sequential handling.

**Recommended approach**:
- Option A: Detect compound intents and handle the primary one first, then proactively offer the second (similar to PostStudyPlanHandler's pattern)
- Option B: Allow the Coordinator to emit a sequence of `RoutingDecision` objects
- **Estimated effort**: 6-8 hours

---

### G13: `useCopilotChatInternal` is private API

**Requirement**: Reliability — Robust patterns

**Current state**: `CustomAssistantMessage` uses `useCopilotChatInternal.sendMessage` to submit HITL responses. This is an internal CopilotKit API not part of the public contract.

**What's missing**: A stable alternative for submitting HITL responses.

**Recommended approach**:
- Investigate `useCopilotAction` + `renderAndWaitForResponse` as a HITL replacement
- Register three frontend actions (`quiz_session`, `study_plan_offer`, `practice_offer`)
- Have the backend emit tool calls with those specific names instead of generic `request_info`
- This would eliminate `CustomAssistantMessage`, `findPendingRequestInfo`, and the `useCopilotChatInternal` dependency
- **Estimated effort**: 6-8 hours (frontend + backend changes)

---

### G14: No dynamic chat suggestions

**Requirement**: User Experience & Presentation

**Current state**: Static suggestion chips are hardcoded in `page.tsx`.

**What's missing**: Context-aware dynamic suggestions using `useCopilotChatSuggestions`.

**Recommended approach**:
```tsx
useCopilotChatSuggestions({
  instructions: "Suggest follow-up actions based on conversation state. " +
    "If a study plan was delivered, suggest starting practice. " +
    "If quiz results showed weak areas, suggest focused study plan. " +
    "If no conversation yet, suggest exploring a certification.",
  maxSuggestions: 3,
});
```
- **Estimated effort**: 1-2 hours

---

### G15: Feedback reports not validated

**Requirement**: Accuracy & Relevance

**Current state**: Post-quiz feedback reports generated by the practice agent are delivered without validation that the scores in the report match `score_quiz()` output.

**What's missing**: A sanity check that the feedback report contains correct score data.

**Recommended approach**:
- After `_generate_feedback_report()`, verify that key numbers (overall score, topic breakdowns) in the generated text match the deterministic `score_quiz()` output
- On mismatch, use the `_fallback_feedback()` deterministic Markdown renderer
- **Estimated effort**: 1 hour

---

## Competition Criteria Analysis

### Accuracy & Relevance

| Strength | Gap |
|----------|-----|
| ✅ MCP grounding ensures freshness | ✅ G2: Critic now validates against original user request |
| ✅ Structured output prevents routing errors | ✅ G3: Practice questions now validated before delivery |
| ✅ Deterministic scoring eliminates arithmetic errors | ❌ G15: Feedback report scores not cross-checked |

### Reasoning & Multi-step Thinking

| Strength | Gap |
|----------|-----|
| ✅ Study plan pipeline is genuinely multi-step (5 executors) | ✅ G8: Multi-step reasoning now visible to user via WorkflowProgress |
| ✅ Cross-route bidirectional flows | ❌ G12: Single-intent routing can't handle compound requests |
| ✅ Critic revision loop demonstrates reflective reasoning | |

### Creativity & Originality

| Strength | Gap |
|----------|-----|
| ✅ Bidirectional flow between study plan and practice | ⚠️ No adaptive difficulty (quiz doesn't adjust based on performance) |
| ✅ Deterministic scheduling tool is smart separation of concerns | ⚠️ No proactive suggestions after cert info delivery |
| ✅ HITL quiz with rich UI cards | |
| ✅ WorkflowProgress synthetic-tool-call pattern is innovative | |

### User Experience & Presentation

| Strength | Gap |
|----------|-----|
| ✅ CopilotKit + AG-UI gives real-time streaming | ❌ G10: No error handling in frontend |
| ✅ QuizCard, OfferCard, QuizDashboard are polished | ❌ G14: Static chat suggestions |
| ✅ Shared state drives UI outside chat panel | ⚠️ No progress indicators during long MCP calls |
| ✅ WorkflowProgress shows step-by-step execution | |

### Reliability & Safety

| Strength | Gap |
|----------|-----|
| ✅ Structured output with fallback parsing | ❌ G1: No error boundaries on agent calls |
| ✅ Auto-approve with disclaimer at iteration cap | ❌ G5: No prompt injection protection |
| ✅ Deterministic tools for critical calculations | ✅ G7: MCP fallback with general-knowledge degradation |
| ✅ Bounded critic loop prevents infinite revision | ❌ G9: No output content safety filtering |
