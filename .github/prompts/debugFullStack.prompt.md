---
name: debugFullStack
description: Debug a full-stack app by validating backend logs and frontend browser flow.
argument-hint: Optional: specific flow or feature to test (e.g., "chat submission", "quiz flow")
---

- I would like you to debug the full stack **backend** (`[backend source folder]`) and **frontend** (`[frontend folder]`).
- The debug session will be running and you will observe it.

# Important
- Alyways restart backend and frontend and refresh the browser before starting the debug session / flows to ensure a clean state. Do not rely on any cached state from previous runs.
- Check .vscode/launch.json for any pre-configured debug sessions that can be used as a starting point for running the backend and frontend in a debuggable mode. There is the full mode there.


## Agent Roles

- **`AIAgentExpert`** — owns the backend:
  - Read backend source code and understand the architecture
  - Check running process health (ports, process status)
  - Fire direct HTTP requests to the backend to isolate agent/API behavior
  - Capture and parse server logs and traces
  - Identify errors, silent failures, misconfiguration, or missing events in the response stream

- **`NextCopilotKitExpert`** — owns the frontend:
  - Use `playwright/*` tools to open the browser and navigate to the running app
  - Exercise the UI flow specified by the user (or the primary happy path if none specified)
  - Capture screenshots at key interaction points (initial load, mid-stream, completion, error states)
  - Collect all browser console warnings and errors
  - Validate that the UI reflects the expected agent responses

## Session Protocol

1. **Start** — confirm both backend and frontend services are running; note their ports and process IDs.
2. **Baseline check** — take an initial screenshot; collect console errors at page load.
3. **Exercise the flow** — trigger the target feature (click suggestion, submit a message, or follow the specified argument).
4. **Backend validation** — while the frontend waits, inspect logs, trace output, and direct API responses to confirm the backend pipeline executes correctly.
5. **Frontend validation** — capture screenshots at streaming, completion, and any error states; note all console warnings.
6. **User notes** — the user may add observations in the chat during the session; incorporate them into findings.
7. **Aggregate** — at the end of the session, compile all findings into a structured bug report saved to `.github/debug/RUN[N].md`, where N is the run number.

## Bug Report Structure

The saved report must include:
- **System under test** — stack, versions, ports, LLM provider
- **Pre-session context** — any user notes about prior known state
- **Session observations** — what was tested and what happened
- **Bugs** — each with: file reference, observed symptom, root cause, recommended fix
- **Observations** — non-bug findings worth noting (performance, warnings, cleanup)
- **False positives** — anything that looked like a bug but was caused by the debug session itself
- **Recommended actions** — prioritised table
- **Screenshots captured** — list with descriptions
