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

type OfferCardProps = {
  message: string;
  certification: string;
  /** Label for the affirmative action (default "Yes"). */
  yesLabel?: string;
  /** Label for the decline action (default "No thanks"). */
  noLabel?: string;
  /** Called with the user's decision text. */
  onRespond: (response: string) => void;
};

export default function OfferCard({
  message,
  certification,
  yesLabel = "Yes, please!",
  noLabel = "No thanks",
  onRespond,
}: OfferCardProps) {
  const [answered, setAnswered] = useState<"yes" | "no" | null>(null);

  const handleClick = (choice: "yes" | "no") => {
    if (answered) return;
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
        <div className="offer-card__actions">
          <button
            type="button"
            className="offer-btn offer-btn--yes"
            onClick={() => handleClick("yes")}
          >
            {yesLabel}
          </button>
          <button
            type="button"
            className="offer-btn offer-btn--no"
            onClick={() => handleClick("no")}
          >
            {noLabel}
          </button>
        </div>
      ) : (
        <p className="offer-card__result">
          {answered === "yes"
            ? "Great — preparing your content..."
            : "No problem! Come back anytime."}
        </p>
      )}
    </div>
  );
}
