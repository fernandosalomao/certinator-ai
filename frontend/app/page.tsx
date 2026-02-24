"use client";

import { useState, useCallback } from "react";
import { CopilotChat } from "@copilotkit/react-core/v2";
import CertinatorHooks from "./components/CertinatorHooks";
import QuizDashboard from "./components/QuizDashboard";
import ErrorBoundary from "./components/ErrorBoundary";
import SlowRunIndicator from "./components/SlowRunIndicator";
import type { CertinatorAgentState } from "./types";

// Suggestions have moved to useConfigureSuggestions in CertinatorHooks
// (supports both static before-first-message AND dynamic after-first-message).

export default function Page() {
  // Track agent shared state for the sidebar quiz dashboard.
  const [agentState, setAgentState] = useState<CertinatorAgentState>({});

  const handleStateChange = useCallback(
    (state: CertinatorAgentState) => setAgentState(state),
    [],
  );

  const quiz = agentState.active_quiz_state;

  return (
    <main className="min-h-screen">
      <ErrorBoundary>
        {/* Register all CopilotKit hooks (HITL, shared state, readables). */}
        <CertinatorHooks onStateChange={handleStateChange} />

        <section className="mx-auto flex w-full max-w-6xl flex-col gap-10 px-6 pb-16 pt-12 md:px-10">
          <div className="hero-panel rounded-3xl p-8 md:p-10">
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

        {/* Quiz dashboard — visible outside the chat once a quiz is completed.
            During in_progress, the QuizSession component inside the chat
            already shows its own live progress bar + question navigator. */}
        {quiz && quiz.status === "completed" && (
          <QuizDashboard quiz={quiz} />
        )}

        <div
          className="hero-panel rounded-2xl p-5 md:p-6"
        >
          {/* Slow-run indicator — shown after 30 s of an active run. */}
          <SlowRunIndicator />
          <CopilotChat
            agentId="my_agent"
            /* ── Layout slots (inherited from CopilotChatView) ────────── */
            chatView="cpk:min-h-0"
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

      </ErrorBoundary>
    </main>
  );
}
