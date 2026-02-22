"use client";

/**
 * CertinatorHooks — CopilotKit hook registrations for Certinator AI.
 *
 * This component is rendered inside the CopilotKit provider and
 * registers all hooks that power shared-state rendering and workflow
 * progress between the MAF backend and the React frontend.
 *
 * CopilotKit features used:
 *   • useCoAgent             — read/write agent shared state
 *   • useCoAgentStateRender  — render completed quiz dashboard in chat
 *   • useRenderToolCall      — render workflow progress rows in chat
 *   • useCopilotReadable     — expose frontend context to backend agent
 *
 * HITL rendering (request_info):
 *   Handled by CustomAssistantMessage (passed to CopilotChat in page.tsx).
 *   CopilotKit's `useLazyToolRenderer` only renders `toolCalls[0]`,
 *   but `request_info` is typically `toolCalls[2]` (after workflow_progress
 *   and active_quiz_state). The custom AssistantMessage searches ALL
 *   tool calls in the message history and renders the quiz/offer UI.
 */

import { useEffect } from "react";
import {
  useCoAgent,
  useCoAgentStateRender,
  useRenderToolCall,
  useCopilotReadable,
} from "@copilotkit/react-core";

import type { CertinatorAgentState } from "../types";
import QuizDashboard from "./QuizDashboard";
import WorkflowProgress from "./WorkflowProgress";

/** Name the agent is served as (must match layout.tsx `agent` prop). */
const AGENT_NAME = "my_agent";

// -----------------------------------------------------------------------
// Component
// -----------------------------------------------------------------------

type CertinatorHooksProps = {
  /**
   * Callback fired whenever agent shared state changes.
   * The parent component can use this to render the QuizDashboard
   * outside the chat (e.g. in a sidebar).
   */
  onStateChange?: (state: CertinatorAgentState) => void;
};

export default function CertinatorHooks({
  onStateChange,
}: CertinatorHooksProps) {
  // ------------------------------------------------------------------
  // 1. Shared state — read quiz state written by PracticeQuizOrchestrator
  // ------------------------------------------------------------------

  const { state } = useCoAgent<CertinatorAgentState>({
    name: AGENT_NAME,
  });

  // Notify parent whenever state changes (for sidebar rendering).
  useEffect(() => {
    if (onStateChange) {
      onStateChange(state);
    }
  }, [state, onStateChange]);

  // ------------------------------------------------------------------
  // 2. In-chat state rendering
  // ------------------------------------------------------------------

  // Quiz dashboard — shown when the backend marks the quiz "completed"
  // (with results/scores). Interactive QuizSession during the quiz is
  // rendered by CustomAssistantMessage (see page.tsx).
  useCoAgentStateRender<CertinatorAgentState>({
    name: AGENT_NAME,
    render: ({ state: agentState }) => {
      const quiz = agentState?.active_quiz_state;
      if (
        quiz &&
        quiz.status === "completed" &&
        Array.isArray(quiz.questions) &&
        quiz.questions.length > 0
      ) {
        return <QuizDashboard quiz={quiz} />;
      }
      return null;
    },
  });

  // Workflow progress rows — one row per tool call, appearing in real-time.
  useRenderToolCall({
    name: "update_workflow_progress",
    render: ({ args }) => {
      const progress = args?.progress as CertinatorAgentState["workflow_progress"];
      if (!progress?.route) return <></>;
      return (
        <WorkflowProgress
          progress={progress}
          currentProgress={state?.workflow_progress}
        />
      );
    },
  });

  // ------------------------------------------------------------------
  // 3. Readables — expose frontend context to the backend agent
  // ------------------------------------------------------------------

  useCopilotReadable({
    description: "User preferences for practice quiz sessions",
    value: {
      preferredDifficulty: "mixed",
      preferredQuestionCount: 10,
      locale: typeof navigator !== "undefined" ? navigator.language : "en-US",
    },
  });

  // This component only registers hooks — no visible DOM output.
  return null;
}
