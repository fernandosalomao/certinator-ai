"use client";

/**
 * SlowRunIndicator — Shows a "This is taking longer than usual" notice
 * when a CopilotKit run has been in-flight for more than SLOW_THRESHOLD_MS.
 *
 * Must be rendered inside the CopilotKit provider so it can call
 * useCopilotChatInternal. Placed just above the CopilotChat window.
 */

import { useEffect, useRef, useState } from "react";
import { useAgent } from "@copilotkit/react-core/v2";

const SLOW_THRESHOLD_MS = 30_000;

export default function SlowRunIndicator() {
  const { agent } = useAgent({ agentId: "my_agent" });
  const isLoading = agent.isRunning;
  const [isSlow, setIsSlow] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (isLoading) {
      timerRef.current = setTimeout(() => setIsSlow(true), SLOW_THRESHOLD_MS);
    } else {
      if (timerRef.current) clearTimeout(timerRef.current);
      setIsSlow(false);
    }
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [isLoading]);

  if (!isSlow) return null;

  return (
    <div className="slow-run-indicator" role="status" aria-live="polite">
      <div className="slow-run-indicator__spinner" aria-hidden="true" />
      <span className="slow-run-indicator__text">
        This is taking longer than usual — Microsoft Learn may be slow to respond.
      </span>
    </div>
  );
}
