# Certinator AI — System Architecture and Design Principles

> A multi-agent system for Microsoft certification exam preparation, built with the **Microsoft Agent Framework (MAF)** and powered by **Azure AI Foundry Agent Service**.
>
> **Status**: Active Development · **Last updated**: 2026-02-18

---

## Table of Contents
TBD

---

## 1. High-Level Architecture

```
TBD
```

### Technology Stack

| Component | Technology |
|-----------|-----------|
| **Framework** | Microsoft Agent Framework (MAF) — `agent-framework` + `agent-framework-azure-ai` Python packages |
| **LLM Backend** | Azure AI Foundry Agent Service v2 — `AzureAIClient` for agent creation and LLM invocation|
| **Supporting SDKs** | `azure-ai-projects`, TBD... |
| **Language** | Python 3.12+ |
| **Default Model** | GPT-4.1 |
| **Orchestration** | TBD |
| **Telemetry** | TBD |
| **Evaluation** | TBD |
| **External APIs** | MS Learn MCP Server |
| **UX** | TBD|
| **Auth** | `DefaultAzureCredential` / `AzureCliCredential` (Azure Identity) |

## 2. Agent Roles and Responsibilities

### Model Strategy

Not all agents require the same model. Cost and latency can be optimized by assigning lighter models to agents that perform simpler tasks (routing, verification) while reserving more capable models for content-rich generation.

| Agent | Model | Rationale |
|-------|-------|----------|
| **Coordinator** | `gpt-4.1-mini` | Routing decisions and light reformulation — no deep generation needed. Low latency, cost-effective. |
| **CertInfo** | `gpt-4.1` | Synthesizes rich certification summaries from multiple data sources. Needs strong comprehension. |
| **StudyPlan** | `gpt-4.1` | Generates detailed, personalized multi-week study plans. Benefits from strong reasoning. |
| **Practice** | `gpt-4.1` | Creates exam-style questions with detailed explanations. Quality is critical for learning. |
| **Critic** | `gpt-4.1-mini` | Text analysis and verification against rubrics — no external tools, no generation. Fast and cheap. |

### 2.1 Coordinator Agent (Planner)

**Role**: Entry point for all user requests. Decomposes user intent into actionable tasks, routes to specialized agents, and **lightly reformulates** specialist outputs into a cohesive user-facing response.

| Property | Value |
|----------|-------|
| **Name** | `coordinator-agent` |
| **Model** | `gpt-4.1-mini` |
| **Pattern** | Planner–Executor |

**Instructions** (summary):
- Analyze user request and determine which certification they need help with
- Decompose the request into sub-tasks: info retrieval, study planning, practice questions
- Route to appropriate specialized agents via workflow
- Perform **light reformulation** of specialist outputs: organize sections, add transitions, ensure consistent tone — but **never generate new factual content** beyond what specialists provided
- Pass specialist outputs through largely verbatim where quality is already high

### 2.2 Certification Info Agent

**Role**: Retrieves and structures information about Microsoft certifications from official sources.

| Property | Value |
|----------|-------|
| **Name** | `cert-info-agent` |
| **Model** | `gpt-4.1` |
| **Tools** | MS Learn MCP  |

**Responsibilities**:
- Query MS Learn MCP Server for certification study guides, exam details, and learning paths
- Search Microsoft Learn documentation via hosted MCP for detailed study guides
- Retrieve exam format, question types, pricing, registration details

### 2.3 Study Plan Agent

**Role**: Generates personalized study plans based on certification info and student context.

| Property | Value |
|----------|-------|
| **Name** | `study-plan-agent` |
| **Model** | `gpt-4o` (schedule generation requires strong reasoning) |
| **Tools** | Code Interpreter (iCal generation), Function Tool (scheduling) |
| **Output** | Study plan with schedule, resources, and iCal file |

**Responsibilities**:
- Accept certification info + student schedule/preferences as input
- Generate a structured study plan with milestones
- Recommend Microsoft Learn modules, documentation, and external resources
- Use Code Interpreter to generate `.ics` (iCal) calendar files
- Provide preparation tips aligned with exam objectives

### 2.4 Practice Question Agent

**Role**: Generates practice questions aligned with exam objectives and evaluates student responses through a multi-turn interactive quiz.

| Property | Value |
|----------|-------|
| **Name** | `practice-question-agent` |
| **Model** | `gpt-4.1` (question quality is critical for learning) |
| **Tools** | `score_quiz` (deterministic scoring), MS Learn MCP via LearningPathFetcher |
| **Output** | JSON question array (generation) or Markdown feedback report (evaluation) |
| **State** | `QuizState` serialised as HTML comment `<!--QUIZ_STATE:...-->` in assistant messages |

**Responsibilities**:
- Fetch exam topics and weights from MS Learn via the LearningPathFetcher agent
- Generate all practice questions at once as a JSON array (at least 1 per topic, distributed by weight)
- Present questions one at a time to the student across multiple turns
- Score all answers deterministically via `score_quiz()` (Python, not LLM)
- Generate a rich feedback report with per-topic breakdown and study recommendations
- Send final evaluation through CriticExecutor for quality validation
- Offer a personalised study plan for weak topics (human-in-the-loop)

**Feature flag**: `DEFAULT_PRACTICE_QUESTIONS` (env var, default 10)


### 2.5 Critic Agent (Verifier)

**Role**: Reviews and validates outputs from other agents for quality, accuracy, and alignment.

| Property | Value |
|----------|-------|
| **Name** | `critic-agent` |
| **Model** | `gpt-4.1-mini` (text analysis only — no tools, no generation) |
| **Pattern** | Critic / Verifier with self-reflection |
| **Output** | Validation report with improvement suggestions |

**Responsibilities**:
- Validate certification info accuracy against known sources
- Review study plan feasibility and completeness
- Check practice questions for factual correctness and exam alignment
- Provide confidence scores and flag items needing revision
- Trigger re-generation when quality thresholds are not met

---

## 3. Multi-Agent Orchestration

### 3.1 Primary Pattern: MAF Graph-Based Workflows (Recommended)

---

## 4. Tools and Integrations

### 4.1 Tool Catalog

| Tool | Agent(s) | Type | Purpose |
|------|----------|------|---------|
| **MS Learn MCP Server** | CertInfo, Practice (via LearningPathFetcher) | Hosted MCP | Search Microsoft Learn docs, fetch articles, find code samples (primary data source) |
| **Code Interpreter** | StudyPlan | Hosted  | Generate iCal files, compute schedules |
| **Schedule Calculator** | StudyPlan | Function Tool | Calculate optimal topic distribution given time constraints |
| **Score Calculator** | Practice | Python Function (`score_quiz`) | Score student answers deterministically and compute per-topic metrics |

### 4.2 Microsoft Learn MCP Server (Hosted MCP) — Primary Data Source

The MS Learn MCP Server is the **primary** tool for retrieving certification and exam information. It provides semantic search, article fetching, and code sample search across all Microsoft Learn content. Hosted and managed by Azure AI Foundry — no server infrastructure to manage.


**Use Cases** (primary):
- Search for exam study guides and skills measured
- Fetch detailed certification pages with prerequisites, exam objectives, and learning paths
- Find preparation tips and documentation on specific exam topics
- Retrieve learning path and module content descriptions


### 4.4 Code Interpreter (Hosted Tool)

Used by the **StudyPlan Agent** to generate iCal (.ics) files for calendar export. Accessed via MAF's hosted tool pattern.

### 4.5 Custom Function Tools


## 5. Reasoning Patterns

### 5.1 Planner–Executor

The **Coordinator Agent** acts as the planner; specialist agents act as executors.

```
User Request
    │
    ▼
Coordinator (Planner)
    │ 1. Analyze user intent
    │ 2. Decompose into sub-tasks
    │ 3. Determine ordering & dependencies
    │ 4. Route each sub-task to appropriate executor
    │
    ├──► CertInfo Agent (executes retrieval)
    ├──► StudyPlan Agent (executes planning, depends on CertInfo output)
    └──► Practice Agent (executes assessment)
```

- The Coordinator's instructions explicitly require step-by-step reasoning about what information is needed, which agents to involve, and in what order
- The plan is expressed as a structured routing decision so downstream agents receive clear task assignments

### 5.2 Critic / Verifier (Workflow Node)

The Critic is a **dedicated CriticExecutor node** in the workflow graph — not embedded inside specialist handlers. Specialist handlers output a `SpecialistOutput` message, which the workflow routes to the CriticExecutor via graph edges. The CriticExecutor validates the content and either:

- **PASS** → emits the final response to the user (terminal)
- **FAIL** (iteration < max) → sends a `RevisionRequest` back to the source handler via conditional edges (feedback loop)
- **FAIL** (iteration ≥ max) → auto-approves with a disclaimer note (safety cap)

```
CertInfoHandler / StudyPlanHandler
        │
        ▼  (SpecialistOutput)
   CriticExecutor
        │
        ├── PASS → emit response to user
        └── FAIL → RevisionRequest → source handler → retry
```

**Maximum iterations**: 2 (configurable via `MAX_CRITIC_ITERATIONS` in `executors/critic.py`).

Dimension-specific checks per content type:

1. **certification_info** (Post-CertInfo): Data accuracy against MCP sources, completeness of exam details, proper source citations
2. **study_plan** (Post-StudyPlan): Feasibility (total hours ≤ available time), completeness (all skill areas covered), resource validity
3. **practice_questions** (Post-Practice, final summary only): Question quality, answer correctness, explanation clarity, alignment to documented exam objectives

> **Design note**: Placing the Critic as a workflow node (rather than an inline function call) follows the MAF [Writer-Critic Workflow pattern](https://github.com/microsoft/agent-framework/tree/main/dotnet/samples/GettingStarted/Workflows/_Foundational/08_WriterCriticWorkflow) which enables graph-visible validation, conditional routing for feedback loops, and independent testability.

### 5.3 Self-Reflection and Iteration

The **StudyPlan Agent** incorporates self-reflection *before* passing to the Critic:

```
StudyPlan Agent
    │
    ├──► Generate initial plan
    │
    ├──► Self-check: "Does this plan fit the student's schedule?"
    │    Calculate total hours required vs. available
    │    If over-scheduled (>110% capacity) → redistribute topics
    │
    ├──► Self-check: "Are all exam skill areas covered?"
    │    Cross-reference plan topics against skills_measured list
    │    If gaps → add missing topics, adjust weights
    │
    └──► Submit to Critic
```

The **Practice Agent** iterates during a quiz session:

```
Practice Agent (multi-turn across workflow runs)
    │
    ├──► Run 1: Fetch topics (MCP) → Generate all questions (JSON)
    │         → Store QuizState in HTML comment → Present Q1
    ├──► Runs 2–N: Parse QuizState → Record answer → Present next Q
    ├──► Run N+1: Score deterministically (score_quiz)
    │         → Generate feedback report → Send to CriticExecutor
    └──► Human-in-the-loop: Offer study plan for weak topics
              → User accepts → Coordinator routes to study_plan
```

### 5.4 Role-Based Specialization

Each agent has maximally focused instructions to reduce overlap and improve output quality:

| Agent | Specialization | What it does NOT do |
|-------|---------------|---------------------|
| **Coordinator** | Planning, routing, light reformulation | Does NOT retrieve data, does NOT generate new factual content |
| **CertInfo** | Data retrieval, summarization, citation | Does NOT create study plans or questions |
| **StudyPlan** | Schedule generation, resource mapping | Does NOT retrieve cert info or generate questions |
| **Practice** | Question generation, scoring, feedback | Does NOT create study plans |
| **Critic** | Quality verification, safety checking | Does NOT generate primary content |

---

## 6. Data Flow and User Interactions

### 6.1 Interaction Flow: Certification Info Request

```
User: "Tell me about the AZ-305 certification"
         │
         ▼
    Coordinator
         │ Plan: [1. Retrieve AZ-305 cert info]
         │ Route: CertInfo Agent
         ▼
    CertInfo Agent
         │ 1. Query MS Learn MCP:
         │    microsoft_docs_search("AZ-305 certification exam")
         │    microsoft_docs_fetch(study guide URL)
         │ 2. Synthesize structured response with citations
         ▼
    CriticExecutor (workflow node)
         │ Verify: data accuracy, source citations, completeness
         │ Verdict: PASS ✓  (or FAIL → loop back to CertInfoHandler)
         ▼
    Coordinator → User
         │ Formatted certification summary:
         │  - Exam objectives & skills measured
         │  - Prerequisites
         │  - Exam format, duration, pricing
         │  - Recent updates
```

### 6.2 Interaction Flow: Full Preparation Session

```
User: "Help me prepare for AZ-104. Exam in 6 weeks, 1.5 hours/day."
         │
         ▼
    Coordinator
         │ Plan: [1. Get AZ-104 info → 2. Generate study plan → 3. Offer practice]
         │ Route: CertInfo Agent (first)
         ▼
    CertInfo Agent → CriticExecutor (PASS) → context saved
         │
    Coordinator
         │ Route: StudyPlan Agent (with CertInfo output + user schedule)
         ▼
    StudyPlan Agent
         │ Input: skills_measured, learning_paths
         │ Input: 6 weeks × 7 days × 1.5 hrs = 63 total hours
         │ Self-reflect: total module hours vs available → adjust
         │ Generate weekly plan with MS Learn module links
         │ Generate .ics file via Code Interpreter
         ▼
    Critic (PASS) → Coordinator → User

    User: "Now give me practice questions on identity and governance"
         │
    Coordinator → Practice Handler (route="practice")
         │ 1. LearningPathFetcher agent (MCP) fetches exam topics + weights
         │ 2. Practice agent generates 10 MCQs as JSON (DEFAULT_PRACTICE_QUESTIONS)
         │ 3. QuizState stored as HTML comment <!--QUIZ_STATE:...-->
         ▼
    User ← Question 1 of 10 (with QuizState embedded)

    User: "B"
         │
    Coordinator (detects quiz_answer) → Practice Handler
         │ Parse QuizState → record answer → present Question 2
         ▼
    User ← Question 2 of 10

    ... (repeat for all questions) ...

    User: "D" (last answer)
         │
    Practice Handler
         │ 1. score_quiz() — deterministic scoring (Python, not LLM)
         │ 2. Practice agent generates rich Markdown feedback
         │ 3. Per-topic breakdown, study recommendations
         │ 4. If weak topics exist: "Want a study plan?"
         ▼
    CriticExecutor (workflow node)
         │ Verify: score math, explanation accuracy, study recs
         │ Verdict: PASS ✓ (or FAIL → revision loop)
         ▼
    User ← Quiz results + recommendations + study-plan offer

    User: "Yes, create a study plan"
         │
    Coordinator (detects post-quiz study request)
         │ Route: study_plan (context includes weak topics)
         ▼
    LearningPathFetcher → StudyPlanScheduler → Critic → User
```

### 6.3 Error Handling Flow

```
User: "Help me with the XY-999 certification"
         │
    Coordinator → CertInfo Agent
         │ 1. Query MS Learn MCP → No results
         │ 2. Return: "Certification not found"
         ▼
    CriticExecutor (workflow node)
         │ Verify: graceful failure, no hallucination
         │ Verdict: PASS (correct behavior)
         ▼
    User: "I couldn't find a certification matching 'XY-999'.
           Here are similar certifications:..."
```

```
Service Outage: MCP Server is down
         │
    CertInfo Agent
         │ 1. Query MCP → Connection timeout (retry 3x with backoff)
         │ 2. Circuit breaker opens after 3 failures
         │ 3. No data available
         ▼
    User: "I'm unable to retrieve certification information
           right now. Please try again in a few minutes."
    (Bypasses Critic — no content to verify)
```

---