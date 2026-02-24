"use client";

/**
 * CertinatorHooks — CopilotKit v2 hook registrations for Certinator AI.
 *
 * Migrations from v1 → v2:
 *   • useCoAgent             → useAgent  (state via agent.state)
 *   • useCoAgentStateRender  → useRenderTool on "update_active_quiz_state"
 *   • useRenderToolCall (v1) → useRenderTool  (Zod-typed; uses "parameters" not "args";
 *                              status is string literal not enum)
 *   • useCopilotReadable     → useAgentContext
 *
 * New v2 capabilities added:
 *   • useHumanInTheLoop — registered as "request_info" (the AG-UI tool name
 *                         emitted by MAF's WorkflowAgent).  Dispatches to the
 *                         correct component based on args.data.type.
 *                         Replaces the CustomAssistantMessage +
 *                         useCopilotChatInternal workaround (Gap G13).
 *   • useConfigureSuggestions — static (before first message) + dynamic (after
 *                               first message) suggestions.  Fixes Gap G14.
 */

import { useEffect } from "react";
import { z } from "zod";
import {
  useAgent,
  useAgentContext,
  useRenderTool,
  useHumanInTheLoop,
  useConfigureSuggestions,
} from "@copilotkit/react-core/v2";

import type { CertinatorAgentState } from "../types";
import QuizDashboard from "./QuizDashboard";
import WorkflowProgress from "./WorkflowProgress";
import QuizSession from "./QuizSession";
import OfferCard from "./OfferCard";

/** Must match the agent name in layout.tsx CopilotKit `agent` prop and route.ts. */
const AGENT_NAME = "my_agent";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

type CertinatorHooksProps = {
  /**
   * Fires whenever agent shared state changes.
   * The parent (page.tsx) uses this to show the QuizDashboard outside the chat.
   */
  onStateChange?: (state: CertinatorAgentState) => void;
};

export default function CertinatorHooks({ onStateChange }: CertinatorHooksProps) {
  // ------------------------------------------------------------------
  // 1. Agent state — replaces useCoAgent (v1)
  // ------------------------------------------------------------------
  const { agent } = useAgent({ agentId: AGENT_NAME });
  const agentState = agent.state as CertinatorAgentState;

  useEffect(() => {
    if (onStateChange) {
      onStateChange(agentState);
    }
  }, [agentState, onStateChange]);

  // ------------------------------------------------------------------
  // 2. Tool renderers — replaces useRenderToolCall (v1)
  //
  //    v2 key differences:
  //      • parameters typed via Zod (replaces free-form args cast)
  //      • render prop uses "parameters" (not "args")
  //      • status is a string literal: "inProgress" | "executing" | "complete"
  // ------------------------------------------------------------------

  // Workflow progress rows rendered in chat — one row per backend step.
  useRenderTool(
    {
      name: "update_workflow_progress",
      parameters: z.object({
        progress: z.object({
          route: z.string(),
          active_executor: z.string(),
          message: z.string(),
          current_step: z.number(),
          total_steps: z.number(),
          status: z.string(),
          updated_at: z.string(),
          reasoning: z.string().optional(),
        }),
      }),
      render: ({ parameters, status }) => {
        if (status === "inProgress") return <></>;
        const progress = parameters.progress as CertinatorAgentState["workflow_progress"];
        if (!progress?.route) return <></>;
        return (
          <WorkflowProgress
            progress={progress}
            currentProgress={agentState?.workflow_progress}
          />
        );
      },
    },
    [agentState?.workflow_progress],
  );

  // Quiz dashboard rendered in chat when the quiz completes.
  // (Also rendered outside the chat in page.tsx via agent state.)
  useRenderTool(
    {
      name: "update_active_quiz_state",
      parameters: z.object({
        active_quiz_state: z.record(z.unknown()).optional(),
      }),
      render: ({ parameters, status }) => {
        if (status === "inProgress") return <></>;
        const quiz = parameters.active_quiz_state as CertinatorAgentState["active_quiz_state"];
        if (!quiz || quiz.status !== "completed" || !quiz.questions?.length) return <></>;
        return <QuizDashboard quiz={quiz} />;
      },
    },
    [],
  );

  // ------------------------------------------------------------------
  // 3. HITL — single "request_info" hook dispatching by data.type
  //
  //    MAF's WorkflowAgent always emits HITL calls with tool name
  //    "request_info".  The payload contains { request_id, data }
  //    where data.type discriminates the interaction kind.
  //    We register one useHumanInTheLoop that routes to the correct
  //    component based on data.type.
  //    Replaces the CustomAssistantMessage workaround (Gap G13).
  // ------------------------------------------------------------------

  useHumanInTheLoop(
    {
      name: "request_info",
      description: "Handle all HITL interactions (quiz, study plan offer, practice offer)",
      parameters: z.object({
        request_id: z.string(),
        data: z.record(z.unknown()),
      }),
      render: ({ args, respond }) => {
        const data = (args.data ?? {}) as Record<string, unknown>;
        const hitlType = data.type as string | undefined;

        // quiz_session: full quiz experience.
        if (hitlType === "quiz_session") {
          const questions = (data.questions ?? []) as Array<{
            question_number: number;
            question_text: string;
            options: Record<string, string>;
            topic: string;
            difficulty: string;
          }>;
          // Still streaming / no questions yet — show placeholder.
          if (!respond && !questions.length) {
            return (
              <div className="quiz-processing-indicator">
                <div className="quiz-processing-indicator__spinner" />
                <span className="quiz-processing-indicator__text">
                  Preparing your quiz…
                </span>
              </div>
            );
          }
          // Args resolved and waiting for user input.
          if (respond) {
            return (
              <QuizSession
                certification={(data.certification as string) ?? ""}
                questions={questions}
                respond={(payload) => void respond(payload)}
                canSubmit
              />
            );
          }
          // User responded — awaiting backend scoring.
          return (
            <div className="quiz-processing-indicator">
              <div className="quiz-processing-indicator__spinner" />
              <span className="quiz-processing-indicator__text">
                Evaluating your answers and generating feedback…
              </span>
            </div>
          );
        }

        // study_plan_offer: yes/no card shown after a failed quiz.
        if (hitlType === "study_plan_offer" && respond) {
          return (
            <OfferCard
              message={(data.prompt as string) ?? "Would you like a study plan?"}
              certification={(data.certification as string) ?? ""}
              yesLabel="Create study plan"
              noLabel="Maybe later"
              onRespond={(choice) => void respond(choice)}
            />
          );
        }

        // practice_offer: yes/no card shown after study plan delivery.
        if (hitlType === "practice_offer" && respond) {
          return (
            <OfferCard
              message={(data.prompt as string) ?? "Would you like practice questions?"}
              certification={(data.certification as string) ?? ""}
              yesLabel="Start practice"
              noLabel="Not now"
              onRespond={(choice) => void respond(choice)}
            />
          );
        }

        // Unknown or still loading — no-op.
        return <></>;
      },
    },
    [],
  );

  // ------------------------------------------------------------------
  // 4. Agent context — replaces useCopilotReadable (v1)
  // ------------------------------------------------------------------
  useAgentContext({
    description: "User preferences for practice quiz sessions",
    value: {
      preferredDifficulty: "mixed",
      preferredQuestionCount: 10,
      locale: typeof navigator !== "undefined" ? navigator.language : "en-US",
    },
  });

  // ------------------------------------------------------------------
  // 5. Suggestions — static before first message + dynamic after (G14)
  // ------------------------------------------------------------------

  // Static entry-point suggestions — always visible so users can
  // quickly start a new topic even after an ongoing conversation.
  useConfigureSuggestions({
    suggestions: [
      {
        title: "AZ-104 overview",
        message: "Give me an overview of the AZ-104 certification",
      },
      {
        title: "AI-900 study plan",
        message:
          "Create a 6-week plan for AI-900 with 1 hour on weekdays and 3 hours on weekends.",
      },
      {
        title: "AI-102 practice quiz",
        message: "Start a 10-question practice quiz for AI-102.",
      },
    ],
    available: "always",
  });

  // Dynamic follow-up suggestions generated by the agent after first message.
  useConfigureSuggestions({
    instructions:
      "Suggest follow-up actions based on the conversation so far. " +
      "If a study plan was recently delivered, suggest starting a practice quiz. " +
      "If quiz results showed weak areas, suggest a focused study plan for those topics. " +
      "If certification info was shown, suggest creating a study plan or taking a practice quiz. " +
      "Keep suggestions concise and actionable. Limit to 3 suggestions.",
    maxSuggestions: 3,
    available: "after-first-message",
  });

  // Renders no DOM — purely registers v2 hooks.
  return null;
}
