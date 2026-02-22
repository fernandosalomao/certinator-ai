"use client";

import { useState, useCallback } from "react";
import { CopilotChat, type CopilotKitCSSProperties } from "@copilotkit/react-ui";
import CertinatorHooks from "./components/CertinatorHooks";
import CustomAssistantMessage from "./components/CustomAssistantMessage";
import QuizDashboard from "./components/QuizDashboard";
import ErrorBoundary from "./components/ErrorBoundary";
import ErrorBanner from "./components/ErrorBanner";
import SlowRunIndicator from "./components/SlowRunIndicator";
import type { CertinatorAgentState } from "./types";

const PROMPT_SUGGESTIONS = [
  "Give me an overview of the AZ-104 certification",
  "Create a 6-week plan for AI-900 with 1 hour on weekdays and 3 hours on weekends.",
  "Start a 10-question practice quiz for AI-102.",
] as const;

export default function Page() {
  // Track agent shared state for the sidebar quiz dashboard.
  const [agentState, setAgentState] = useState<CertinatorAgentState>({});
  // Shown when CopilotChat fires onError (e.g. backend unreachable).
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleStateChange = useCallback(
    (state: CertinatorAgentState) => setAgentState(state),
    [],
  );

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handleCopilotError = useCallback((errorEvent: any) => {
    const raw: unknown = errorEvent?.error;
    const rawMsg =
      raw instanceof Error
        ? raw.message
        : typeof raw === "string"
          ? raw
          : null;

    // Map low-level network errors to a user-friendly message.
    const isNetworkError =
      rawMsg === null ||
      rawMsg === "" ||
      /fetch failed|network|failed to fetch|load failed/i.test(rawMsg);

    const msg = isNetworkError
      ? "Unable to reach the AI service. Make sure the backend is running and try again."
      : (rawMsg ?? "Something went wrong. Please try again.");

    console.error("[CertinatorAI] CopilotKit error:", raw ?? errorEvent);
    setErrorMessage(msg);
  }, []);

  const quiz = agentState.active_quiz_state;

  const copilotTheme = {
    "--copilot-kit-primary-color": "#6f87ff",
    "--copilot-kit-contrast-color": "#ffffff",
    "--copilot-kit-background-color": "#0b1227",
    "--copilot-kit-secondary-color": "#111a36",
    "--copilot-kit-secondary-contrast-color": "#e8eeff",
    "--copilot-kit-separator-color": "#2a355e",
    "--copilot-kit-muted-color": "#9cadde",
    "--copilot-kit-input-background-color": "#101938",
  } as CopilotKitCSSProperties;

  const chatSuggestions = PROMPT_SUGGESTIONS.map((prompt) => ({
    title: prompt,
    message: prompt,
  }));

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

        {/* Inline error banner — shown when CopilotChat fires onError. */}
        {errorMessage && (
          <ErrorBanner
            message={errorMessage}
            onDismiss={() => setErrorMessage(null)}
          />
        )}

        <div
          className="surface-card embedded-chat rounded-2xl p-3 md:p-4"
          style={copilotTheme}
        >
          {/* Slow-run indicator — shown after 30 s of an active run. */}
          <SlowRunIndicator />
          <CopilotChat
            suggestions={chatSuggestions}
            AssistantMessage={CustomAssistantMessage}
            onError={handleCopilotError}
            labels={{
              title: "CertinatorAI Copilot",
              initial:
                "I can help you choose a Microsoft certification, build a study plan, and run practice with feedback.",
              placeholder: "Ask about exams, study plans, or practice questions...",
            }}
          />
        </div>
        </section>

      </ErrorBoundary>
    </main>
  );
}
