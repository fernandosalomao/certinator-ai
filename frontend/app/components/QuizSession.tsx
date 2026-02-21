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

import { useCallback, useState } from "react";
import QuizCard from "./QuizCard";

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
};

export default function QuizSession({
  certification,
  questions,
  respond,
}: QuizSessionProps) {
  const total = questions.length;

  // Track current question index and all collected answers.
  const [currentIdx, setCurrentIdx] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitted, setSubmitted] = useState(false);

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
  }, [answers, respond, submitted]);

  if (!current) return null;

  return (
    <div className="quiz-session">
      {/* Progress bar */}
      <div className="quiz-session__progress">
        <div className="quiz-session__bar-track">
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
      <div className="quiz-session__dots">
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
            >
              {idx + 1}
            </button>
          );
        })}
      </div>

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
            disabled={!allAnswered || submitted}
            onClick={handleSubmit}
            className="quiz-session__btn quiz-session__btn--submit"
          >
            {submitted
              ? "Submitting…"
              : allAnswered
                ? "Submit Quiz"
                : `${total - answeredCount} unanswered`}
          </button>
        )}
      </div>
    </div>
  );
}
