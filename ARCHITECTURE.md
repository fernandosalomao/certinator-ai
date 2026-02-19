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
| **Demo UX** | CopilotKit Next.js frontend with AG-UI adapter (`agent-framework-ag-ui`)|
| **Auth** | `DefaultAzureCredential` / `AzureCliCredential` (Azure Identity) |

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **MAF Workflows or Orchestrations** over Connected Agents | Connected Agents (Foundry) use LLM-decided delegation with max depth 2. MAF workflows give explicit graph-based control with unlimited depth, checkpointing, and human-in-the-loop. |
| **`AzureAIClient`** | `AzureAIClient` from `agent-framework-azure-ai` manages agent creation and LLM invocation via the Azure AI Foundry service. `as_agent()` returns an `Agent` that supports `agent.run("user message")` for async execution. MCP tools use `AzureAIClient.get_mcp_tool()` static method. (to be confirmed) |
More.. TBD

---

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
| **Tools** | MS Learn MCP (`AzureAIClient.get_mcp_tool()`), Code Interpreter |

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

**Role**: Generates practice questions aligned with exam objectives and evaluates student responses.

| Property | Value |
|----------|-------|
| **Name** | `practice-question-agent` |
| **Model** | `gpt-4o` (question quality is critical for learning) |
| **Tools** | Function Tool (answer evaluation, quiz formatting, scoring) |
| **Output** | Questions with explanations, performance feedback |

**Responsibilities**:
- Generate multiple-choice questions mapped to specific exam objectives
- Provide detailed explanations for correct and incorrect answers
- Track student answers and compute performance metrics per skill area
- Identify areas of strength and weakness
- Recommend further study topics based on performance gaps


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
| **MS Learn MCP Server** | CertInfo | Hosted MCP (`get_mcp_tool`) | Search Microsoft Learn docs, fetch articles, find code samples (primary data source) |
| **Code Interpreter** | StudyPlan | Hosted (`get_code_interpreter_tool`) | Generate iCal files, compute schedules |
| **Schedule Calculator** | StudyPlan | `FunctionTool` | Calculate optimal topic distribution given time constraints |
| **Quiz Formatter** | Practice | `FunctionTool` | Structure questions in consistent format |
| **Score Calculator** | Practice | `FunctionTool` | Score student answers and compute per-skill metrics |

### 4.2 Microsoft Learn MCP Server (Hosted MCP) — Primary Data Source

The MS Learn MCP Server is the **primary** tool for retrieving certification and exam information. It provides semantic search, article fetching, and code sample search across all Microsoft Learn content. Hosted and managed by Azure AI Foundry — no server infrastructure to manage.

**Server URL**: `https://learn.microsoft.com/api/mcp`

**Available Tools** (provided dynamically by the MCP server):
- `microsoft_docs_search` — semantic search across Microsoft Learn documentation
- `microsoft_docs_fetch` — fetch and convert a full article to markdown
- `microsoft_code_sample_search` — search for code samples in documentation


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

### 5.2 Critic / Verifier

Dimension-specific checks per agent:

1. **Post-CertInfo**: Data accuracy against MCP sources, completeness of exam details, proper source citations
2. **Post-StudyPlan**: Feasibility (total hours ≤ available time), completeness (all skill areas covered), resource validity
3. **Post-Practice** (final summary only): Question quality, answer correctness, explanation clarity, alignment to documented exam objectives

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
Practice Agent
    │
    ├──► Generate question batch (5 questions per skill area)
    ├──► After student answers → Score and analyze per-skill metrics
    ├──► Identify weak areas from scoring breakdown
    ├──► Generate targeted follow-up questions for weak areas
    └──► Repeat until student is satisfied or all areas assessed
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
    Critic Agent
         │ Verify: data accuracy, source citations, completeness
         │ Verdict: PASS ✓
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
    CertInfo Agent → Critic (PASS) → context saved
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
         │
    User: "Now give me practice questions on identity and governance"
         │
    Coordinator → Practice Agent
         │ skill_area = "identity and governance"
         ▼
    Practice Agent
         │ Generate 5 multiple-choice questions
         │ Present to user, collect answers
         │ Score and provide per-skill feedback (bypasses Critic)
         │ Identify weak areas → offer follow-up questions
         ▼
    Practice Agent → final quiz summary → Critic (PASS)
         ▼
    User: quiz results + recommendations
```

### 6.3 Error Handling Flow

```
User: "Help me with the XY-999 certification"
         │
    Coordinator → CertInfo Agent
         │ 1. Query MS Learn MCP → No results
         │ 2. Return: "Certification not found"
         ▼
    Critic Agent
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

## Frontend
The AG-UI server exposes the workflow via the official `agent-framework-ag-ui`
Uses the `CopilotKit` Next.js starter as the frontend, with custom components to display certification info, study plans, and practice questions in an engaging format.
---

## Key SDK Packages

> **Pinning strategy**: Use `==` (exact pin) for `agent-framework-*` packages while the SDK is in preview to avoid breaking changes between releases. Use `>=` (minimum version) for stable Azure SDK packages.

Agent Framework: 1.0.0b260212
https://github.com/microsoft/agent-framework/tree/python-1.0.0b260212

CopilotKit: v1.50.1
https://github.com/CopilotKit/CopilotKit/tree/v1.50.1