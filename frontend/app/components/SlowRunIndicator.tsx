"use client";

/**
 * SlowRunIndicator — Shows a "This is taking longer than usual" notice
 * when a CopilotKit run has been in-flight for more than SLOW_THRESHOLD_MS.
 *
 * G15 — Frontend Error Resilience: adds a "Cancel" button so the user
 * can abort a stuck run via `agent.stop()` instead of waiting indefinitely.
 *
 * Must be rendered inside the CopilotKit provider so it can call
 * useAgent. Placed just above the CopilotChat window.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useAgent } from "@copilotkit/react-core/v2";

/** Time (ms) before showing the slow-run warning. */
const SLOW_THRESHOLD_MS = 30_000;

/** Auto-dismiss the "cancelled" confirmation after this many ms. */
const CANCELLED_DISPLAY_MS = 5_000;

export default function SlowRunIndicator() {
  const { agent } = useAgent({ agentId: "my_agent" });
  const isLoading = agent.isRunning;
  const [isSlow, setIsSlow] = useState(false);
  const [cancelled, setCancelled] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancelTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (isLoading) {
      setCancelled(false);
      timerRef.current = setTimeout(() => setIsSlow(true), SLOW_THRESHOLD_MS);
    } else {
      if (timerRef.current) clearTimeout(timerRef.current);
      setIsSlow(false);
    }
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [isLoading]);

  // Auto-dismiss the "cancelled" banner after a few seconds.
  useEffect(() => {
    if (cancelled) {
      cancelTimerRef.current = setTimeout(
        () => setCancelled(false),
        CANCELLED_DISPLAY_MS,
      );
    }
    return () => {
      if (cancelTimerRef.current) clearTimeout(cancelTimerRef.current);
    };
  }, [cancelled]);

  /** Abort the current in-flight run (G15). */
  const handleCancel = useCallback(() => {
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (agent as any).abortRun();
    } catch {
      // abortRun() may throw if there's no active run — ignore.
    }
    setIsSlow(false);
    setCancelled(true);
  }, [agent]);

  // "Cancelled" confirmation message.
  if (cancelled) {
    return (
      <div className="slow-run-indicator slow-run-indicator--cancelled" role="status" aria-live="polite">
        <span className="slow-run-indicator__text">
          Request cancelled — you can send a new message to retry.
        </span>
      </div>
    );
  }

  if (!isSlow) return null;

  return (
    <div className="slow-run-indicator" role="status" aria-live="polite">
      <div className="slow-run-indicator__spinner" aria-hidden="true" />
      <span className="slow-run-indicator__text">
        This is taking longer than usual — Microsoft Learn may be slow to respond.
      </span>
      <button
        type="button"
        className="slow-run-indicator__cancel"
        onClick={handleCancel}
        aria-label="Cancel the current request"
      >
        Cancel
      </button>
    </div>
  );
}
