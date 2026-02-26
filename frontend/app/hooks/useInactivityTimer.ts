"use client";

/**
 * useInactivityTimer — Detects user inactivity and fires a callback.
 *
 * Resets on mouse move, key press, touch, scroll, and focus events.
 * Returns `isInactive` state and a manual `reset()` function.
 *
 * Part of G15 — Frontend Error Resilience: protects HITL sessions
 * from abandonment by warning the user after prolonged inactivity.
 */

import { useCallback, useEffect, useRef, useState } from "react";

/** Events that count as "user activity". */
const ACTIVITY_EVENTS: (keyof WindowEventMap)[] = [
  "mousemove",
  "mousedown",
  "keydown",
  "touchstart",
  "scroll",
  "focus",
];

type UseInactivityTimerOptions = {
  /** Inactivity threshold in milliseconds. */
  timeoutMs: number;
  /** Callback fired when the timer expires. */
  onTimeout?: () => void;
  /** Whether the timer is active. Defaults to `true`. */
  enabled?: boolean;
};

type UseInactivityTimerReturn = {
  /** `true` when the user has been inactive longer than `timeoutMs`. */
  isInactive: boolean;
  /** Manually reset the timer (e.g. after the user interacts with the UI). */
  reset: () => void;
};

export function useInactivityTimer({
  timeoutMs,
  onTimeout,
  enabled = true,
}: UseInactivityTimerOptions): UseInactivityTimerReturn {
  const [isInactive, setIsInactive] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onTimeoutRef = useRef(onTimeout);
  onTimeoutRef.current = onTimeout;

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const startTimer = useCallback(() => {
    clearTimer();
    timerRef.current = setTimeout(() => {
      setIsInactive(true);
      onTimeoutRef.current?.();
    }, timeoutMs);
  }, [clearTimer, timeoutMs]);

  /** Reset inactivity state and restart the countdown. */
  const reset = useCallback(() => {
    setIsInactive(false);
    startTimer();
  }, [startTimer]);

  // Wire up DOM activity listeners.
  useEffect(() => {
    if (!enabled || typeof window === "undefined") return;

    const handleActivity = () => {
      setIsInactive(false);
      startTimer();
    };

    // Start the first countdown.
    startTimer();

    for (const event of ACTIVITY_EVENTS) {
      window.addEventListener(event, handleActivity, { passive: true });
    }

    return () => {
      clearTimer();
      for (const event of ACTIVITY_EVENTS) {
        window.removeEventListener(event, handleActivity);
      }
    };
  }, [enabled, startTimer, clearTimer]);

  return { isInactive, reset };
}
