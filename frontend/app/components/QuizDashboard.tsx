"use client";

/**
 * QuizDashboard — Real-time quiz progress panel.
 *
 * Reads `active_quiz_state` from CopilotKit shared state via the
 * `useCoAgent` hook and renders a progress bar, topic breakdown,
 * and current status outside the chat window.
 */

import type { QuizState } from "../types";

type QuizDashboardProps = {
  quiz: QuizState;
};

export default function QuizDashboard({ quiz }: QuizDashboardProps) {
  const { certification, questions, current_index, answers, status, topics } =
    quiz;

  const total = questions.length;
  const answered = answers.length;
  const progressPct = total > 0 ? Math.round((answered / total) * 100) : 0;

  return (
    <div className="quiz-dashboard">
      <div className="quiz-dashboard__header">
        <h3 className="quiz-dashboard__title">
          {certification} Practice Quiz
        </h3>
        <span
          className={`quiz-dashboard__status ${
            status === "completed"
              ? "quiz-dashboard__status--done"
              : "quiz-dashboard__status--active"
          }`}
        >
          {status === "completed" ? "Completed" : "In Progress"}
        </span>
      </div>

      {/* Progress bar */}
      <div className="quiz-dashboard__progress">
        <div className="quiz-dashboard__bar-track">
          <div
            className="quiz-dashboard__bar-fill"
            style={{ width: `${progressPct}%` }}
          />
        </div>
        <span className="quiz-dashboard__bar-label">
          {answered} / {total} answered ({progressPct}%)
        </span>
      </div>

      {/* Topic badges */}
      <div className="quiz-dashboard__topics">
        {topics.map((topic) => (
          <span key={topic} className="quiz-badge">
            {topic}
          </span>
        ))}
      </div>

      {/* Current question indicator */}
      {status === "in_progress" && current_index < total && (
        <p className="quiz-dashboard__current">
          Next up: Question {current_index + 1} —{" "}
          <em>{questions[current_index]?.topic}</em> (
          {questions[current_index]?.difficulty})
        </p>
      )}
    </div>
  );
}
