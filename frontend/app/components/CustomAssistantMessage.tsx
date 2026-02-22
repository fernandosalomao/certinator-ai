"use client";

/**
 * CustomAssistantMessage — Extends the default CopilotKit AssistantMessage
 * to render `request_info` tool calls that CopilotKit's built-in rendering
 * pipeline cannot reach.
 *
 * Why this is needed:
 *   CopilotKit's `useLazyToolRenderer` only renders `message.toolCalls[0]`.
 *   When the backend emits multiple tool calls in a single run
 *   (update_workflow_progress, update_active_quiz_state, request_info),
 *   `request_info` ends up at index 2 and is silently ignored.
 *
 *   This component finds `request_info` in ANY position within the message
 *   history and renders the appropriate UI (QuizSession, OfferCard, etc.)
 *   on the LAST assistant message so it appears after the text intro.
 *
 * Submit mechanism:
 *   The `request_id` from the tool call args IS the `toolCallId`.
 *   On submit, we construct a `{ role: "tool", toolCallId, content }` message
 *   and send it via `sendMessage`, triggering a new AG-UI run.
 *   The backend `RequestInfoOrchestrator` detects the pending request +
 *   tool result and resumes processing.
 *
 * Processing indicator:
 *   After submit, `sendMessage` triggers a new AG-UI run which remounts all
 *   message components — destroying local React state. To survive this, the
 *   "processing" state is derived from the message history itself:
 *   if a `request_info` tool call HAS a matching tool result (user submitted)
 *   but this message has no text content yet (feedback not arrived),
 *   show a spinner. This is purely computed from props, no local state needed.
 */

import { useMemo, useCallback, useRef, useState } from "react";
import {
  AssistantMessage,
  type AssistantMessageProps,
} from "@copilotkit/react-ui";
import { useCopilotChatInternal } from "@copilotkit/react-core";
import QuizSession from "./QuizSession";
import OfferCard from "./OfferCard";

// -----------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------

/** Minimal shape of a tool call from CopilotKit message objects. */
interface ToolCallShape {
  id: string;
  type?: string;
  function?: {
    name: string;
    arguments: string | Record<string, unknown>;
  };
  // Some CopilotKit versions flatten these:
  name?: string;
  toolCallId?: string;
}

/** Minimal message shape for searching the history. */
interface MsgShape {
  id: string;
  role: string;
  content?: string;
  toolCalls?: ToolCallShape[];
  toolCallId?: string;
}

/** Parsed request_info payload if one is pending. */
interface PendingRequestInfo {
  toolCallId: string;
  data: Record<string, unknown>;
}

/**
 * Search all messages for a `request_info` tool call that has NO matching
 * tool result message. Returns the parsed args if found, null otherwise.
 */
function findPendingRequestInfo(
  messages: unknown[] | undefined,
): PendingRequestInfo | null {
  if (!messages) return null;
  const msgs = messages as MsgShape[];

  for (const msg of msgs) {
    if (msg.role !== "assistant") continue;
    const toolCalls = msg.toolCalls;
    if (!Array.isArray(toolCalls)) continue;

    for (const tc of toolCalls) {
      // The tool call name can be in `function.name` or directly in `name`
      const tcName = tc.function?.name ?? tc.name;
      if (tcName !== "request_info") continue;

      const tcId = tc.id ?? tc.toolCallId;
      if (!tcId) continue;

      // Check if a tool result already exists for this tool call
      const hasResult = msgs.some(
        (m) => m.role === "tool" && m.toolCallId === tcId,
      );
      if (hasResult) continue;

      // Parse arguments — may be a JSON string or already parsed object
      try {
        const rawArgs = tc.function?.arguments;
        const args: Record<string, unknown> =
          typeof rawArgs === "string" ? JSON.parse(rawArgs) : rawArgs ?? {};
        const requestId = (args.request_id as string) || tcId;
        const data = (args.data as Record<string, unknown>) ?? {};
        return { toolCallId: requestId, data };
      } catch {
        // Unparseable — skip
      }
    }
  }

  return null;
}

/**
 * Check if a `request_info` tool call has been answered (tool result exists)
 * in the message history. This indicates the user submitted a response
 * and we're waiting for the backend to process it.
 *
 * Returns true when the user has submitted (quiz answers, offer response, etc.)
 * and the backend is still working on the result.
 */
function hasSubmittedRequestInfo(
  messages: unknown[] | undefined,
): boolean {
  if (!messages) return false;
  const msgs = messages as MsgShape[];

  for (const msg of msgs) {
    if (msg.role !== "assistant") continue;
    const toolCalls = msg.toolCalls;
    if (!Array.isArray(toolCalls)) continue;

    for (const tc of toolCalls) {
      const tcName = tc.function?.name ?? tc.name;
      if (tcName !== "request_info") continue;

      const tcId = tc.id ?? tc.toolCallId;
      if (!tcId) continue;

      // Found a request_info tool call WITH a matching tool result →
      // the user submitted a response and we're awaiting backend processing.
      const hasResult = msgs.some(
        (m) => m.role === "tool" && m.toolCallId === tcId,
      );
      if (hasResult) return true;
    }
  }

  return false;
}

// -----------------------------------------------------------------------
// Component
// -----------------------------------------------------------------------

export default function CustomAssistantMessage(props: AssistantMessageProps) {
  const { message, messages, isCurrentMessage } = props;
  const { sendMessage } = useCopilotChatInternal();

  // Track whether a response has been submitted to prevent double-sends.
  const submittedRef = useRef(false);
  const [submitted, setSubmitted] = useState(false);
  // Surfaces sendMessage failures inline so the user can retry.
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Only compute the pending request_info for the current (last) message
  // so the quiz/offer UI appears in the right position — after the text intro.
  const pendingRequestInfo = useMemo(() => {
    if (!isCurrentMessage) return null;
    return findPendingRequestInfo(messages);
  }, [isCurrentMessage, messages]);

  // Derive "processing" state from message history — survives component
  // remounts caused by sendMessage triggering a new AG-UI run.
  // True when: this is the current message, it has no text content yet,
  // and a request_info tool call has been answered (tool result exists).
  const processingHitl = useMemo(() => {
    if (!isCurrentMessage) return false;
    // If this message already has text content, feedback has arrived —
    // no need for a processing indicator.
    const content =
      typeof (message as Record<string, unknown> | undefined)?.content ===
      "string"
        ? ((message as Record<string, unknown>).content as string)
        : "";
    if (content.trim().length > 0) return false;
    // Check if the user submitted a response and we're awaiting results.
    return hasSubmittedRequestInfo(messages);
  }, [isCurrentMessage, message, messages]);

  const handleSubmit = useCallback(
    async (payload: string) => {
      if (!pendingRequestInfo || submittedRef.current) return;
      submittedRef.current = true;
      setSubmitted(true);
      setSubmitError(null);

      console.log(
        "[CustomAssistantMessage] Submitting HITL response:",
        { toolCallId: pendingRequestInfo.toolCallId, payloadLength: payload.length },
      );

      try {
        await sendMessage(
          {
            id: crypto.randomUUID?.() ?? String(Date.now()),
            role: "tool" as const,
            content: payload,
            toolCallId: pendingRequestInfo.toolCallId,
          } as Record<string, unknown>,
        );
      } catch (err) {
        console.error("[CustomAssistantMessage] sendMessage failed:", err);
        // Reset so the user can retry.
        submittedRef.current = false;
        setSubmitted(false);
        setSubmitError(
          err instanceof Error
            ? err.message
            : "Failed to submit your response. Please try again.",
        );
      }
    },
    [sendMessage, pendingRequestInfo],
  );

  // Build the extra UI to render after the default message content.
  let extraUI: React.ReactNode = null;

  if (pendingRequestInfo?.data && !submitted) {
    const { data } = pendingRequestInfo;
    const type = data.type as string | undefined;

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

      if (questions && questions.length > 0) {
        extraUI = (
          <QuizSession
            certification={(data.certification as string) ?? ""}
            questions={questions}
            respond={handleSubmit}
            canSubmit
          />
        );
      }
    } else if (type === "study_plan_offer") {
      extraUI = (
        <OfferCard
          message={(data.prompt as string) ?? "Would you like a study plan?"}
          certification={(data.certification as string) ?? ""}
          yesLabel="Create study plan"
          noLabel="Maybe later"
          onRespond={handleSubmit}
        />
      );
    } else if (type === "practice_offer") {
      extraUI = (
        <OfferCard
          message={
            (data.prompt as string) ??
            "Would you like some practice questions?"
          }
          certification={(data.certification as string) ?? ""}
          yesLabel="Start practice"
          noLabel="Not now"
          onRespond={handleSubmit}
        />
      );
    }
  } else if (submitted || processingHitl) {
    // Show a processing indicator between submit and results.
    // `submitted` covers the immediate render (same component instance).
    // `processingHitl` covers the case where the component was remounted
    // by a new AG-UI run (local state lost) — derived from message history.
    extraUI = (
      <div className="quiz-processing-indicator">
        <div className="quiz-processing-indicator__spinner" />
        <span className="quiz-processing-indicator__text">
          Evaluating your answers and generating feedback…
        </span>
      </div>
    );
  }

  // Surface sendMessage errors with a retry affordance.
  const errorUI = submitError ? (
    <div className="hitl-submit-error" role="alert">
      <span className="hitl-submit-error__message">{submitError}</span>
      <button
        className="hitl-submit-error__retry"
        onClick={() => setSubmitError(null)}
      >
        Dismiss
      </button>
    </div>
  ) : null;

  // Render the default AssistantMessage (text, markdown, generativeUI for
  // toolCalls[0]), then append our extra UI for request_info.
  return (
    <>
      <AssistantMessage {...props} />
      {errorUI}
      {extraUI}
    </>
  );
}
