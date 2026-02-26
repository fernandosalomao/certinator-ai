"use client";

/**
 * QuizSession — Full quiz experience rendered in a single HITL call.
 *
 * The backend sends ALL questions at once via `request_info` with
 * `type: "quiz_session"`.  This component renders them one-by-one,
 * lets the student navigate and answer each, then submits the entire
 * answer set back in a single `respond()` call:
 *
 *   respond(JSON.stringify({ answers: { "1": "B", "2": "A", ... } }))
 *
 * This eliminates per-question round-trips and avoids the SDK's
 * `_extract_function_responses` error when re-sending full history.
 */

import { useCallback, useMemo, useState } from "react";
import QuizCard from "./QuizCard";
import { useSessionStorage } from "../hooks/useSessionStorage";
import { useInactivityTimer } from "../hooks/useInactivityTimer";

/** Shape of each question from the backend payload. */
type SessionQuestion = {
  question_number: number;
  question_text: string;
  options: Record<string, string>;
  topic: string;
  difficulty: string;
};

type QuizSessionProps = {
  certification: string;
  questions: SessionQuestion[];
  /** Send the full answer payload back to the backend. */
  respond: (payload: string) => void;
  /**
   * Whether the backend respond callback is wired up and ready.
   * The submit button is disabled until this is true, but the quiz
   * UI renders immediately so the student can start reading/answering.
   */
  canSubmit?: boolean;
};

export default function QuizSession({
  certification,
  questions,
  respond,
  canSubmit = true,
}: QuizSessionProps) {
  const total = questions.length;

  // Stable storage key derived from certification + question count so
  // stale data from a previous quiz doesn't collide (G15).
  const storageKey = useMemo(
    () => `certinator:quiz:${certification}:${total}`,
    [certification, total],
  );

  // Track current question index and all collected answers.
  // Persisted to sessionStorage so answers survive page reloads (G15).
  const [answers, setAnswers, clearAnswers] = useSessionStorage<
    Record<string, string>
  >(`${storageKey}:answers`, {});
  const [currentIdx, setCurrentIdx, clearIdx] = useSessionStorage<number>(
    `${storageKey}:idx`,
    0,
  );
  const [submitted, setSubmitted] = useState(false);

  // Inactivity timer — warn the student after 5 minutes of no interaction (G15).
  const { isInactive, reset: resetInactivity } = useInactivityTimer({
    timeoutMs: 5 * 60 * 1000,
    enabled: !submitted,
  });

  const answeredCount = Object.keys(answers).length;
  const allAnswered = answeredCount === total;
  const current = questions[currentIdx];

  /** Record an answer for the current question. */
  const handleAnswer = useCallback(
    (letter: string) => {
      setAnswers((prev) => ({
        ...prev,
        [String(current.question_number)]: letter,
      }));

      // Auto-advance to next unanswered question after a brief pause.
      setTimeout(() => {
        if (currentIdx < total - 1) {
          setCurrentIdx((i) => i + 1);
        }
      }, 350);
    },
    [current, currentIdx, total],
  );

  /** Submit all answers back to the backend. */
  const handleSubmit = useCallback(() => {
    if (submitted) return;
    setSubmitted(true);
    respond(JSON.stringify({ answers }));
    // Clear persisted quiz state on successful submission (G15).
    clearAnswers();
    clearIdx();
  }, [answers, respond, submitted, clearAnswers, clearIdx]);

  if (!current) return null;

  return (
    <div className="quiz-session">
      {/* Inactivity warning banner (G15). */}
      {isInactive && !submitted && (
        <div className="quiz-session__inactivity" role="alert">
          <span>
            You&apos;ve been inactive — your progress is saved locally.
            Resume answering or submit your quiz.
          </span>
          <button
            type="button"
            className="quiz-session__inactivity-dismiss"
            onClick={resetInactivity}
            aria-label="Dismiss inactivity warning"
          >
            Got it
          </button>
        </div>
      )}

      {/* Progress bar */}
      <div className="quiz-session__progress">
        <div
          className="quiz-session__bar-track"
          role="progressbar"
          aria-valuenow={answeredCount}
          aria-valuemin={0}
          aria-valuemax={total}
          aria-label={`Quiz progress: ${answeredCount} of ${total} questions answered`}
        >
          <div
            className="quiz-session__bar-fill"
            style={{
              width: `${Math.round((answeredCount / total) * 100)}%`,
            }}
          />
        </div>
        <span className="quiz-session__bar-label">
          {answeredCount} / {total} answered
        </span>
      </div>

      {/* Question dots for navigation */}
      <nav className="quiz-session__dots" aria-label="Question navigation">
        {questions.map((q, idx) => {
          const isAnswered = !!answers[String(q.question_number)];
          const isCurrent = idx === currentIdx;
          return (
            <button
              key={q.question_number}
              type="button"
              onClick={() => setCurrentIdx(idx)}
              className={[
                "quiz-session__dot",
                isCurrent ? "quiz-session__dot--current" : "",
                isAnswered ? "quiz-session__dot--answered" : "",
              ]
                .filter(Boolean)
                .join(" ")}
              title={`Question ${idx + 1}`}
              aria-label={`Question ${idx + 1}${isAnswered ? ", answered" : ", unanswered"}${isCurrent ? ", current" : ""}`}
              aria-current={isCurrent ? "step" : undefined}
            >
              {idx + 1}
            </button>
          );
        })}
      </nav>

      {/* Current question card */}
      <QuizCard
        key={current.question_number}
        questionText={current.question_text}
        optionA={current.options.A ?? ""}
        optionB={current.options.B ?? ""}
        optionC={current.options.C ?? ""}
        optionD={current.options.D ?? ""}
        questionNumber={current.question_number}
        totalQuestions={total}
        topic={current.topic}
        difficulty={current.difficulty}
        selectedAnswer={answers[String(current.question_number)] ?? null}
        onAnswer={handleAnswer}
      />

      {/* Navigation + submit */}
      <div className="quiz-session__nav">
        <button
          type="button"
          disabled={currentIdx === 0}
          onClick={() => setCurrentIdx((i) => Math.max(0, i - 1))}
          className="quiz-session__btn quiz-session__btn--nav"
        >
          ← Previous
        </button>

        {currentIdx < total - 1 ? (
          <button
            type="button"
            onClick={() =>
              setCurrentIdx((i) => Math.min(total - 1, i + 1))
            }
            className="quiz-session__btn quiz-session__btn--nav"
          >
            Next →
          </button>
        ) : (
          <button
            type="button"
            disabled={!allAnswered || submitted || !canSubmit}
            onClick={handleSubmit}
            className="quiz-session__btn quiz-session__btn--submit"
          >
            {submitted
              ? "Submitting…"
              : !canSubmit
                ? "Connecting…"
                : allAnswered
                  ? "Submit Quiz"
                  : `${total - answeredCount} unanswered`}
          </button>
        )}
      </div>
    </div>
  );
}
