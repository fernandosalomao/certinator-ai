"use client";

/**
 * OfferCard — Yes / No HITL decision card.
 *
 * Used by two `useHumanInTheLoop` hooks:
 *   1. "study_plan_offer"  — after a failed quiz, offer a study plan.
 *   2. "practice_offer"    — after a study plan, offer practice questions.
 *
 * Replaces plain-text "yes/no" typing with prominent action buttons.
 */

import { useState } from "react";
import { useInactivityTimer } from "../hooks/useInactivityTimer";

type OfferCardProps = {
  message: string;
  certification: string;
  /** Label for the affirmative action (default "Yes"). */
  yesLabel?: string;
  /** Label for the decline action (default "No thanks"). */
  noLabel?: string;
  /** Called with the user's decision text. */
  onRespond: (response: string) => void;
  /** Disable buttons while the backend respond callback isn't ready yet. */
  disabled?: boolean;
};

export default function OfferCard({
  message,
  certification,
  yesLabel = "Yes, please!",
  noLabel = "No thanks",
  onRespond,
  disabled = false,
}: OfferCardProps) {
  const [answered, setAnswered] = useState<"yes" | "no" | null>(null);

  // Auto-decline after 2 minutes of inactivity so the backend HITL
  // doesn't hang indefinitely (G15 — HITL session abandonment).
  useInactivityTimer({
    timeoutMs: 2 * 60 * 1000,
    enabled: answered === null && !disabled,
    onTimeout: () => {
      if (answered === null) {
        setAnswered("no");
        onRespond("no");
      }
    },
  });

  const handleClick = (choice: "yes" | "no") => {
    if (answered || disabled) return;
    setAnswered(choice);
    onRespond(choice);
  };

  return (
    <div className="offer-card">
      {certification && (
        <span className="offer-card__cert">{certification}</span>
      )}
      <p className="offer-card__message">{message}</p>

      {!answered ? (
        <div className="offer-card__actions" role="group" aria-label={`Actions for ${certification}`}>
          <button
            type="button"
            className="offer-btn offer-btn--yes"
            onClick={() => handleClick("yes")}
            disabled={disabled}
            aria-label={`${yesLabel} — ${certification}`}
          >
            {yesLabel}
          </button>
          <button
            type="button"
            className="offer-btn offer-btn--no"
            onClick={() => handleClick("no")}
            disabled={disabled}
            aria-label={`${noLabel} — ${certification}`}
          >
            {noLabel}
          </button>
        </div>
      ) : (
        <p className="offer-card__result" aria-live="polite">
          {answered === "yes"
            ? "Great — preparing your content..."
            : "No problem! Come back anytime."}
        </p>
      )}
    </div>
  );
}
