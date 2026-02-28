"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { CopilotChat } from "@copilotkit/react-core/v2";
import CertinatorHooks from "./components/CertinatorHooks";
import ErrorBoundary from "./components/ErrorBoundary";
import SlowRunIndicator from "./components/SlowRunIndicator";
import { WorkflowProgressProvider } from "./components/WorkflowProgressContext";
import { useSessionStorage } from "./hooks/useSessionStorage";
import type { CertinatorAgentState } from "./types";

// Suggestions have moved to useConfigureSuggestions in CertinatorHooks
// (supports both static before-first-message AND dynamic after-first-message).

/** Auto-dismiss duration for the "session recovered" banner (ms). */
const RECOVERY_BANNER_MS = 4_000;

export default function Page() {
  // Track agent shared state for the sidebar quiz dashboard.
  // Persisted to sessionStorage so completed quizzes / workflow progress
  // survive page reloads (G15 — Frontend Error Resilience).
  const [persistedState, setPersistedState, clearPersistedState] =
    useSessionStorage<CertinatorAgentState>("certinator:agent-state", {});

  const [agentState, setAgentState] = useState<CertinatorAgentState>(
    () => persistedState,
  );

  // Show a brief "Session recovered" banner when state was restored.
  const [showRecovery, setShowRecovery] = useState(false);
  useEffect(() => {
    // If we recover meaningful state (e.g. a completed quiz), show the banner.
    if (persistedState.active_quiz_state || persistedState.workflow_progress) {
      setShowRecovery(true);
      const timer = setTimeout(() => setShowRecovery(false), RECOVERY_BANNER_MS);
      return () => clearTimeout(timer);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Run once on mount.

  // Collapsible hero panel — auto-collapses on first user interaction
  // so the chat area gets maximum vertical space (D1 fix).
  const [heroCollapsed, setHeroCollapsed] = useState(false);
  const hasAutoCollapsed = useRef(false);

  const handleStateChange = useCallback(
    (state: CertinatorAgentState) => {
      setAgentState(state);
      setPersistedState(state);

      // Auto-collapse hero once the user starts interacting.
      if (!hasAutoCollapsed.current && state.workflow_progress) {
        hasAutoCollapsed.current = true;
        setHeroCollapsed(true);
      }
    },
    [setPersistedState],
  );

  return (
    <main className="flex h-screen flex-col overflow-hidden">
      <ErrorBoundary>
        <WorkflowProgressProvider currentProgress={agentState.workflow_progress}>
        {/* Recovery banner — shown briefly after state is restored from sessionStorage (G15). */}
        {showRecovery && (
          <div className="session-recovered-banner" role="status" aria-live="polite">
            <span>✓ Your previous session was recovered.</span>
            <button
              type="button"
              className="session-recovered-banner__dismiss"
              onClick={() => {
                setShowRecovery(false);
                clearPersistedState();
              }}
              aria-label="Dismiss recovery notice"
            >
              Dismiss
            </button>
          </div>
        )}
        {/* Register all CopilotKit hooks (HITL, shared state, readables). */}
        <CertinatorHooks onStateChange={handleStateChange} />

        <section className="mx-auto flex w-full max-w-6xl flex-1 min-h-0 flex-col gap-4 px-6 pt-6 pb-4 md:px-10">
          {/* ── Collapsible hero — shrinks to a compact bar when collapsed (D1). ── */}
          <div
            className={`hero-panel rounded-3xl flex-shrink-0 overflow-hidden transition-all duration-300 ease-in-out ${
              heroCollapsed
                ? "max-h-0 p-0 border-transparent opacity-0"
                : "max-h-[500px] p-8 md:p-10"
            }`}
            aria-hidden={heroCollapsed}
          >
            <div className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs tracking-[0.2em] text-white/80 uppercase">
              Reasoning Agent for Microsoft Certifications
            </div>
            <h1 className="mt-5 max-w-3xl text-4xl font-semibold tracking-tight md:text-6xl">
              CertinatorAI
            </h1>
            <p className="mt-4 max-w-2xl text-base text-white/80 md:text-lg">
              Your all-in-one exam prep copilot: discover certification paths,
              get personalized study schedules, and train with feedback-rich
              practice sessions.
            </p>
            <div className="mt-6 grid gap-4 sm:grid-cols-3">
              <div className="glass-card rounded-2xl p-4">
                <p className="text-xs text-white/60 uppercase tracking-[0.15em]">
                  Retrieval Agent
                </p>
                <p className="mt-2 text-sm text-white/90">
                  Pulls official Microsoft exam objectives, prerequisites, and
                  registration details.
                </p>
              </div>
              <div className="glass-card rounded-2xl p-4">
                <p className="text-xs text-white/60 uppercase tracking-[0.15em]">
                  Study Planner
                </p>
                <p className="mt-2 text-sm text-white/90">
                  Builds a personalized weekly plan with learning resources and
                  exam milestones.
                </p>
              </div>
              <div className="glass-card rounded-2xl p-4">
                <p className="text-xs text-white/60 uppercase tracking-[0.15em]">
                  Practice + Critic
                </p>
                <p className="mt-2 text-sm text-white/90">
                  Generates weighted practice questions and gives actionable
                  performance feedback.
                </p>
              </div>
            </div>
          </div>

          {/* ── Hero toggle button ── */}
          <button
            type="button"
            className="hero-collapse-toggle flex-shrink-0 self-center"
            onClick={() => setHeroCollapsed((c) => !c)}
            aria-expanded={!heroCollapsed}
            aria-label={heroCollapsed ? "Show introduction" : "Hide introduction"}
          >
            <svg
              className={`hero-collapse-toggle__chevron ${heroCollapsed ? "hero-collapse-toggle__chevron--collapsed" : ""}`}
              width="16"
              height="16"
              viewBox="0 0 16 16"
              fill="none"
              aria-hidden="true"
            >
              <path d="M4 10L8 6L12 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span className="text-xs">
              {heroCollapsed ? "Show CertinatorAI intro" : "Hide intro"}
            </span>
          </button>

        {/* Quiz dashboard is rendered inside the chat via
            useRenderTool("update_active_quiz_state") in CertinatorHooks.
            No external rendering needed here. */}

        {/* ── Chat panel — fills remaining viewport height (D1 fix). ── */}
        <div
          className="hero-panel rounded-2xl p-5 md:p-6 flex-1 min-h-0 flex flex-col"
        >
          {/* Slow-run indicator — shown after 30 s of an active run. */}
          <SlowRunIndicator />
          <CopilotChat
            agentId="my_agent"
            /* ── Auto-scroll & scroll-to-bottom button ────────────────── */
            autoScroll={true}
            /* ── Layout slots (inherited from CopilotChatView) ────────── */
            chatView="cpk:min-h-0 cpk:flex-1"
            /* scrollView accepts Partial<ScrollViewProps> — includes feather */
            scrollView={{
              className: "cpk:bg-transparent",
              feather:
                "cpk:from-transparent cpk:via-transparent cpk:dark:from-transparent cpk:dark:via-transparent",
            }}
            /* ── Message bubbles ──────────────────────────────────── */
            messageView={{
              className: "cpk:px-2",
              assistantMessage: {
                className: "certinator-assistant-msg cpk:mb-4",
              },
              userMessage: {
                className: "certinator-user-msg",
                messageRenderer: "certinator-user-bubble",
              },
            }}
            /* ── Input area (includes disclaimer sub-slot) ────────── */
            input={{
              className: "certinator-chat-input",
              textArea:
                "cpk:text-base cpk:text-foreground",
              sendButton: "cpk:bg-primary cpk:text-primary-foreground",
              disclaimer: "cpk:text-muted-foreground",
            }}
            /* ── Labels ───────────────────────────────────────────── */
            labels={{
              chatInputPlaceholder: "Ask about exams, study plans, or practice questions...",
              modalHeaderTitle: "CertinatorAI Copilot",
              welcomeMessageText:
                "I can help you choose a Microsoft certification, build a study plan, and run practice with feedback.",
            }}
          />
        </div>
        </section>
        </WorkflowProgressProvider>
      </ErrorBoundary>
    </main>
  );
}
