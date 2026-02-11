---
agent: 'microsoft-agent-framework-python'
description: 'Initial Implementation for Certinator AI using Microsoft Agent Framework for Python.'
---

# Initial Implementation for Certinator AI *(using Microsoft Agent Framework)*

The goal is to build a multi-agent system that can effectively assist students in their preparation for Microsoft certification exams. The system should be capable of understanding the exam syllabus, generating study plans, providing practice questions, and offering feedback on performance.

You are about to implement a multi‑agent system to help students prepare for Microsoft certification exams. Follow the guidelines below to build the initial version using the
**Python version of the Microsoft Agent Framework** (MAF) in conjunction with [Azure AI Foundry Agents](https://learn.microsoft.com/en-us/agent-framework/user-guide/agents/agent-types/azure-ai-foundry-agent?pivots=programming-language-python)

## 🎯 High‑Level Use Case

Create an AI assistant that supports learners preparing for Microsoft certification exams (e.g. AZ‑900).
The assistant should understand a student’s goals and constraints, recommend personalised learning paths from [**Microsoft Learn MCP**](https://learn.microsoft.com/en-us/training/support/mcp) or other sources, generate a time‑phased study plan, schedule reminders, administer practice assessments aligned to the official exam blueprint, and provide information about exam registration and requirements.

## 🧩 Architectural Overview

1. **Orchestrator Agent (entry point)**
   - Accepts student input (target certification, exam date, current knowledge level, weekly study hours, preferred learning style and intent). Normalises this into a `StudentProfile` data model.
   - Selects the appropriate workflow or agent based on the intent (**study plan**, **practice questions**, **certification info**, or **all**). It acts as a planner/router.
   - Handles human‑in‑the‑loop confirmations (confirm study plan, retake assessments, accept/reject calendar invites) and gracefully terminates or loops the workflow as appropriate.

2. **Learning Path Curator Agent**
   - Receives a `StudentProfile` and queries the Microsoft Learn MCP API (and optionally GitHub/web search) to gather relevant learning resources (modules, learning
     paths, labs) tied to the student’s target exam and knowledge level.
   - Collates and deduplicates these resources into a `StudyPlanMilestones` data model, capturing unit names, durations, prerequisites and success criteria.
   - You may optionally implement a [**concurrent**](https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/orchestrations/concurrent?pivots=programming-language-python) pattern here, [fanning out](https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/core-concepts/edges?pivots=programming-language-python#fan-out-edges) multiple asynchronous calls to different resource providers and merging the results.

3. **Study Plan Generator Agent**
   - Consumes the curated resources and the `StudentProfile` to build a detailed study plan aligned to the student’s exam date and available study hours. Break the plan into milestones or weeks, assigning durations and ordering of topics. See [Microsoft Learn Plans Best practices](https://learn.microsoft.com/en-us/training/support/plans-best-practices) for inspiration.
   - Writes the plan back to a `StudyPlanMilestones` model and returns it to the orchestrator.
   - Supports iterative adjustments based on student feedback or assessment results.

4. **Reminder Agent**
   - Takes the finalised study plan and generates calendar events (e.g. iCalendar
     attachments) for each milestone. Handles integration with email/calendar APIs. (optional)

5. **Assessment Agent**
   - Generates practice questions aligned to the official exam blueprint (include skill
     description, multiple‑choice answers and rubric). Present questions one at a time,
     collect answers and evaluate the overall score (≥70% = pass).
   - Returns a structured `AssessmentResults` model detailing per‑topic scores and
     recommendations for improvement. If the student opts to retake, repeat the assessment.

6. **Certification Agent**
   - Provides authoritative information about exam registration, exam structure (duration,
     number of questions, passing score) and related certifications.

## 🔄 Workflows & Patterns

### Certification Orchestration Workflow
Use a [**GroupChat**](https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/orchestrations/group-chat?pivots=programming-language-python) or [**Magnetic**](https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/orchestrations/magentic?pivots=programming-language-python) orchestration pattern to manage the conversation. The orchestrator is the “manager” (planner) and the other agents or subworkflows are “participants.” When the student requests a study plan, the orchestrator hands control to the Study Plan Workflow; when the student requests practice questions, it summons the Assessment
Agent; when certification info is requested, it calls the Certification Agent. Refer to
the MAF documentation on group chat and magnetic coordination for implementation details.

### Study Plan Workflow
Implement a [**Sequential**](https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/orchestrations/sequential?pivots=programming-language-python) workflow: `Learning Path Curator Agent → Study Plan Generator Agent → Reminder Agent`. Pass a `StudentProfile` into the first agent; pass a `StudyPlanMilestones` model between agents. Each agent enriches the data, then passes it along. At the end, return the populated study plan back to the orchestrator for human approval.

## 🛠️ Implementation Guidelines

1. **Use MAF Python APIs**
   - Define each conceptual agent as a subclass or instance of `AzureAIAgentClient` from the `agent_framework` package. Provide a concise system prompt that describes the agent’s role, tools and decision boundaries.
   - Construct the workflows using `Sequential`, `GroupChat` or `Magnetic` classes. Treat subworkflows [as agents](https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/as-agents?pivots=programming-language-python) when embedding them into higher‑level orchestrations.
   - Leverage context providers and thread‐based state for persisting the `StudentProfile` and other models across turns.
   - Define data contracts using Pydantic models or dataclasses (e.g. `StudentProfile`, `StudyPlanMilestones`, `AssessmentResults`) to ensure structured outputs and robust tool calling.

2. **Async & Concurrency**
   - For the Learning Path Curator Agent, implement asynchronous calls to the Microsoft Learn MCP API and other resources concurrently. You can use Python’s `asyncio.gather` or MAF’s concurrent execution patterns to fetch resources in parallel and combine the results.

3. **Error Handling & Fallbacks**
   - Implement try/except or the MAF retry/fallback features. If the MCP API call fails, attempt a web search on `learn.microsoft.com`. Provide helpful messages when resources cannot be found or assessments cannot be generated.

4. **Human‑in‑the‑Loop**
   - Ask for confirmation at key steps (e.g. once the study plan is generated, before sending calendar invites, when offering to retake assessments). Use `request_info` nodes to capture user approval or further instructions.

5. **Safety and Disclaimers**
   - Add a disclaimer reminding the student that this system complements official Microsoft training but does not replace it. Validate inputs, avoid generating inappropriate content and abide by responsible AI practices.

6. **Telemetry & Testing**
   - Instrument your app with MAF telemetry to capture agent interactions, tool call successes/failures and latency. Create some “golden” student profiles and expected outputs to validate your workflows.

## 📁 Deliverables

For this initial implementation, structure your project as follows:

```
certinator-ai/
│
├── src/                # Python source code implementing your agents, data models & workflows
│   ├── agents/
│   │   ├── orchestrator_agent.py
│   │   ├── learning_path_curator_agent.py
│   │   ├── study_plan_generator_agent.py
│   │   ├── reminder_agent.py
│   │   ├── assessment_agent.py
│   │   └── certification_agent.py
│   ├── workflows/
│   │   ├── study_plan_workflow.py
│   │   └── orchestration_workflow.py
│   └── models/
│       ├── student_profile.py
│       ├── study_plan.py
│       └── assessment_results.py
│
├── .env                # Contains AZURE_AI_PROJECT_ENDPOINT and model deployment name
└── main.py             # Entry point that constructs the orchestrator and launches the interactive UI
└── requirements.txt    # Lists project dependencies
```

You can adapt this structure to suit your needs. Make sure your `main.py` wires up the
workflows and exposes the system via the `agent_framework.devui` UI for local testing.


# AI Simulation (For Inspiration)

>> Starts Group Chat `Certification Orchestration` workflow with `Orchestrator Agent`

## 1. Introduction
`Orchestrator Agent`: Hello! I am Certinator AI, an AI system designed to help you prepare for Microsoft certification exams. 

## 2. Gather Student Certification Interest (topics/certification)
`Orchestrator Agent`: What **certification** are you interested in?
`Student`: I'm interested in preparing for the Microsoft Azure Fundamentals certification.
`Orchestrator Agent`: Excellent choice! The Microsoft Azure Fundamentals (AZ-900) certification is a great starting point for learning about cloud services and how they are provided with Microsoft Azure.

## 3. Gather Student Intent (study plan or practice questions or certification info or all)
`Orchestrator Agent`: Would you like help with creating a personalized **study plan**, practicing **exam questions**, getting **certification information**, or **all** of them?
`Student`: I would like help with all of the above.
`Orchestrator Agent`: Great! I can assist you with creating a personalized study plan, providing practice exam questions, and giving you information about the certification process.

>> If `Student` selected **exam questions** redirect to #7
>> If `Student` selected **certification information** redirect to #8 

## 4. Ask about target exam date
`Orchestrator Agent`: Do you have a target date for taking the Azure Fundamentals exam (AZ-900)?
`Student`: Yes, I plan to take the exam in three months.
>> `Orchestrator Agent` adds the target exam date to the `Student Profile Schema`.
`Orchestrator Agent`: Perfect! That gives us a good timeline to work with for creating your study plan.

## 5. Gather Student Constraints (knowledge level, available study time, preferred learning style)
`Orchestrator Agent`: To get started, I need to gather some information about your study preferences and goals.
`Orchestrator Agent`: Could you please tell me about your current knowledge level of Azure? Are you a beginner, intermediate, or advanced user?
`Student`: I have some basic knowledge of cloud computing, but I'm new to Azure specifically.
>> `Orchestrator Agent` adds the **knowledge level** to the `Student Profile Schema`.
`Orchestrator Agent`: No problem! How much time can you dedicate to studying each week?
`Student`: I can dedicate about 10 hours per week to studying.
>> `Orchestrator Agent` adds the **available study time** to the `Student Profile Schema`.
`Orchestrator Agent`: Thanks for sharing that. Lastly, what is your preferred learning style? Do you prefer videos, reading materials, or hands-on labs?
`Student`: I learn best through reading materials and hands-on labs.
>> `Orchestrator Agent` adds the **preferred learning style** to the `Student Profile Schema`.
`Orchestrator Agent`: Thank you for the information! To summarize, you're preparing for the Microsoft Azure Fundamentals certification in three months, you're a beginner with some basic cloud knowledge, you can study 10 hours per week, and you prefer reading materials and hands-on labs. Is that correct?
`Student`: Yes, that's correct.
`Orchestrator Agent`: Great! Let's get started on creating your personalized study plan.

>> `Orchestrator Agent` passes the `Student Profile Schema` to Sequential `Study Plan Workflow` which includes the following steps:
>> - `Learning Path Curator Agent` takes `Student Profile Schema` and curates a personalized learning path based on the student's interests, knowledge level, and preferred learning style. It gathers relevant learning resources such as documentation, tutorials, videos, and hands-on labs. It uses Microsoft Learn MCP to find the best resources for the student.
>> - `Learning Path Curator Agent` sends the curated learning paths via `Study Plan & Milestones Schema` to `Study Plan Generator Agent`.
>> - `Study Plan Generator Agent` takes the curated learning path and creates a detailed study plan with milestones and deadlines based on the student's available study time and target exam date.

`Study Plan Generator Agent`: Here is your personalized study plan for the Microsoft Azure Fundamentals certification. The plan includes a variety of resources such as documentation, tutorials, videos, and hands-on labs that are tailored to your learning preferences and knowledge level.
Week 1:
- Learning Path: Introduction to Cloud Infrastructure: Describe cloud concepts (52 min)
... (continues with the study plan details)

## 6. Confirm study plan and create calendar
>> `Orchestrator Agent` calls `Reminder Agent` to create a calendar with milestones and send it to the student.
`Reminder Agent`: I have created a calendar with your study plan milestones. You can download it here: [link to calendar]. This will help you stay on track with your study schedule and ensure that you are prepared for the exam by your target date.

`Orchestrator Agent`: Does this study plan look good to you?
`Student`: Yes, it looks great! I'm excited to get started.
>> If the student is not satisfied with the study plan, `Orchestrator Agent` can ask for feedback and send it back to `Study Plan Generator Agent` to adjust the plan based on the student's feedback and preferences until the student is satisfied with the study plan.

## 7. Practice exam questions and provide feedback
`Orchestrator Agent`: Would you like to practice some exam questions to test your knowledge and get a feel for the types of questions that may be on the exam?
`Student`: Yes, that would be great.

>> `Orchestrator Agent` calls `Assessment Agent` to provide practice exam questions to the student.

`Assessment Agent`: Here is a set of practice exam questions for the Microsoft Azure Fundamentals certification. These questions are designed to help you test your knowledge and get familiar with the format of the exam.

Question 1 - Skill measured: Describe cloud concepts (25–30%)

What is the primary benefit of using cloud services?
A) Cost savings
B) Scalability
C) Flexibility
D) All of the above

`Student`: D) All of the above
`Assessment Agent`: That's correct! Cloud services offer cost savings, scalability, and flexibility, making them a popular choice for businesses and individuals alike.

`Assessment Agent`: Question 2... (continues with more practice questions)

`Assessment Agent`: Congratulations on completing the practice questions! If scored more than 70%!

`Assessment Agent`: Based on your performance, I recommend focusing on the following areas in your study plan: [list of areas to focus on]. 


## 8. Provide certification information
`Orchestrator Agent`: Would you like to receive information about the exam?
`Student`: Yes, please.

>> `Orchestrator Agent` calls `Certification Agent` to provide information about the Microsoft Azure Fundamentals certification exam.

`Certification Agent`: 
Exam AZ-305: Designing Microsoft Azure Infrastructure Solutions
[url to exam details]

This exam is for candidates who have expertise in designing cloud and hybrid solutions that run on Microsoft Azure, including compute, network, storage, monitoring, and security.

Assessed on this exam: 
- Design identity, governance, and monitoring solutions (25–30%)
- Design data storage solutions (20–25%)
- Design business continuity solutions (15–20%)
- Design infrastructure solutions (30–35%)

Related certifications:
- Microsoft Certified: Azure Solutions Architect Expert

Duration: 150 minutes

## 9. Wait for further instructions from the student or end the conversation.
`Orchestrator Agent`: Let me know if you have any questions about the exam or if there's anything else I can assist.
>> Here the `Orchestrator Agent` can wait for further instructions from the student, redirect to other agents/workflows based on the student's needs, or end the conversation if the student is satisfied with the information provided.


