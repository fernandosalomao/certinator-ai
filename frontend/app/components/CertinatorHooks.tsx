"use client";

/**
 * CertinatorHooks — CopilotKit hook registrations for Certinator AI.
 *
 * This component is rendered inside the CopilotKit provider and
 * registers all hooks that power the HITL interactions and shared
 * state rendering between the MAF backend and the React frontend.
 *
 * CopilotKit features used:
 *   • useHumanInTheLoop  — rich HITL UI for quiz answers and offers
 *   • useCoAgent         — read/write agent shared state
 *   • useCoAgentStateRender — render agent state inline in chat
 *   • useCopilotReadable — expose frontend context to backend agent
 *
 * HITL Mechanism:
 *   The MAF backend calls `ctx.request_info(data, str)` at every
 *   human-interaction point.  The AG-UI bridge converts this into a
 *   tool call named "request_info" with args:
 *     { request_id: string, data: { type, ...payload } }
 *
 *   We register ONE `useHumanInTheLoop("request_info")` hook that
 *   inspects `data.type` to decide which component to render:
 *     • "quiz_session"    → QuizSession (all questions at once)
 *     • "study_plan_offer" → OfferCard (create study plan?)
 *     • "practice_offer"   → OfferCard (start practice?)
 *     • (fallback)         → generic text prompt
 */

import { useEffect } from "react";
import {
  useCoAgent,
  useCoAgentStateRender,
  useCopilotReadable,
  useHumanInTheLoop,
} from "@copilotkit/react-core";

import type { CertinatorAgentState } from "../types";
import QuizSession from "./QuizSession";
import QuizDashboard from "./QuizDashboard";
import OfferCard from "./OfferCard";

/** Name the agent is served as (must match layout.tsx `agent` prop). */
const AGENT_NAME = "my_agent";

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
  // 2. In-chat state rendering — show quiz progress inline in chat
  // ------------------------------------------------------------------

  useCoAgentStateRender<CertinatorAgentState>({
    name: AGENT_NAME,
    render: ({ state: agentState }) => {
      const quiz = agentState?.active_quiz_state;
      if (!quiz || quiz.status === "completed") return null;
      return <QuizDashboard quiz={quiz} />;
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

  // ------------------------------------------------------------------
  // 4. HITL: unified "request_info" handler
  //
  //    The MAF backend always emits tool calls named "request_info".
  //    We dispatch to the correct component based on `data.type`.
  // ------------------------------------------------------------------

  useHumanInTheLoop({
    name: "request_info",
    description:
      "Handle human-in-the-loop requests from the Certinator AI backend. " +
      "Presents quiz questions, study plan offers, or practice offers.",
    parameters: [
      {
        name: "request_id",
        type: "string",
        description: "Unique request identifier for correlating the response",
        required: true,
      },
      {
        name: "data",
        type: "object",
        description:
          "Request payload. Contains a 'type' field to discriminate " +
          "between quiz_question, study_plan_offer, and practice_offer.",
        required: true,
      },
    ],
    render: ({ args, respond, status }) => {
      if (!respond) return <></>;

      // The AG-UI bridge wraps request_data inside { request_id, data }.
      // `args` should have `request_id` and `data`.
      const data = (args as Record<string, unknown>).data as
        | Record<string, unknown>
        | undefined;

      if (!data) {
        // Fallback: no structured data available
        return (
          <div className="offer-card">
            <p>The agent is waiting for your input.</p>
            <div className="offer-card__actions">
              <button
                className="offer-card__btn offer-card__btn--yes"
                onClick={() => respond("yes")}
              >
                Yes
              </button>
              <button
                className="offer-card__btn offer-card__btn--no"
                onClick={() => respond("no")}
              >
                No
              </button>
            </div>
          </div>
        );
      }

      const type = data.type as string | undefined;

      // ------ Quiz session → QuizSession (all questions) ------
      if (type === "quiz_session") {
        const questions = data.questions as
          | Array<{
              question_number: number;
              question_text: string;
              options: Record<string, string>;
              topic: string;
              difficulty: string;
            }>
          | undefined;

        if (!questions || questions.length === 0) {
          return (
            <div className="offer-card">
              <p>No questions were generated. Please try again.</p>
            </div>
          );
        }

        return (
          <QuizSession
            certification={(data.certification as string) ?? ""}
            questions={questions}
            respond={(payload) => respond(payload)}
          />
        );
      }

      // ------ Study plan offer → OfferCard ------
      if (type === "study_plan_offer") {
        return (
          <OfferCard
            message={(data.prompt as string) ?? "Would you like a study plan?"}
            certification={(data.certification as string) ?? ""}
            yesLabel="Create study plan"
            noLabel="Maybe later"
            onRespond={(choice) => respond(choice)}
          />
        );
      }

      // ------ Practice offer → OfferCard ------
      if (type === "practice_offer") {
        return (
          <OfferCard
            message={
              (data.prompt as string) ??
              "Would you like some practice questions?"
            }
            certification={(data.certification as string) ?? ""}
            yesLabel="Start practice"
            noLabel="Not now"
            onRespond={(choice) => respond(choice)}
          />
        );
      }

      // ------ Fallback: generic prompt with text input ------
      const prompt =
        (data.prompt as string) ?? "The agent is waiting for your input.";
      return (
        <div className="offer-card">
          <p style={{ whiteSpace: "pre-wrap" }}>{prompt}</p>
          <div className="offer-card__actions">
            <button
              className="offer-card__btn offer-card__btn--yes"
              onClick={() => respond("yes")}
            >
              Yes
            </button>
            <button
              className="offer-card__btn offer-card__btn--no"
              onClick={() => respond("no")}
            >
              No
            </button>
          </div>
        </div>
      );
    },
  });

  // This component only registers hooks — no visible DOM output.
  return null;
}
