"use client";

import { useRef } from "react";
import type { WorkflowProgress as WorkflowProgressState } from "../types";
import { useWorkflowProgress } from "./WorkflowProgressContext";

type WorkflowStepProps = {
  /** State snapshot captured when this step was emitted. */
  progress: WorkflowProgressState;
};

function CheckIcon() {
  return (
    <svg
      style={{ width: 13, height: 13, color: "white", flexShrink: 0 }}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      role="img"
      aria-label="Completed"
    >
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
    </svg>
  );
}

function SpinnerIcon() {
  return (
    <svg
      style={{
        width: 13,
        height: 13,
        color: "white",
        flexShrink: 0,
        animation: "wpspin 1s linear infinite",
      }}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      role="img"
      aria-label="In progress"
    >
      <style>{`@keyframes wpspin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
      <circle style={{ opacity: 0.25 }} cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        style={{ opacity: 0.75 }}
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );
}

/**
 * Renders a single step row in the chat.
 * One instance is created per progress update via useRenderToolCall.
 *
 * isDone when:
 *   • the overall workflow has completed (liveStatus === "completed"), OR
 *   • a later step has advanced past this one (liveStep > thisStep)
 *
 * Route discrimination: only react to live progress from the SAME route.
 * A different route starting (e.g. "practice" after "study-plan-generator")
 * must not flip earlier steps back to spinning.
 *
 * Ratchet: once a step transitions to done, it stays done permanently.
 * This prevents flicker when a new route overwrites the global progress.
 */
export default function WorkflowProgress({ progress }: WorkflowStepProps) {
  // Get live state from context for reactive updates
  const { currentProgress } = useWorkflowProgress();
  const frozenDone = useRef(false);

  if (!progress?.route) return null;

  // Only consider live progress from the same route — updates
  // from a different route must not affect this step's state.
  const sameRoute = currentProgress?.route === progress.route;
  const liveStatus = sameRoute
    ? (currentProgress?.status ?? progress.status)
    : progress.status;
  const liveStep = sameRoute
    ? (currentProgress?.current_step ?? progress.current_step)
    : progress.current_step;

  const computedDone =
    liveStatus === "completed" ||
    liveStep > progress.current_step;

  // Ratchet: once done, never revert to spinning.
  if (computedDone) frozenDone.current = true;
  const isDone = frozenDone.current;

  const statusText = isDone ? "Completed" : "In progress";

  return (
    <div
      className={`workflow-progress__step ${
        isDone ? "workflow-progress__step--done" : "workflow-progress__step--active"
      }`}
      style={{ margin: "2px 0" }}
      role="status"
      aria-label={`${progress.message} — ${statusText}`}
    >
      <span className="workflow-progress__step-icon-wrap">
        {isDone ? <CheckIcon /> : <SpinnerIcon />}
      </span>
      <span className="workflow-progress__step-body">
        <span className="workflow-progress__step-text">
          {progress.message}
          <span className="sr-only"> — {statusText}</span>
        </span>
        {progress.reasoning && (
          <span className="workflow-progress__step-reasoning">{progress.reasoning}</span>
        )}
      </span>
      {!isDone && <span className="workflow-progress__step-pulse" aria-hidden="true" />}
    </div>
  );
}
