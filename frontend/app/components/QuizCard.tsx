"use client";

/**
 * QuizCard — Rich multiple-choice question card for quiz answers.
 *
 * Used inside `QuizSession` to render a single question.  Supports
 * both controlled mode (parent owns `selectedAnswer`) and uncontrolled
 * mode (local state) for backwards compatibility.
 */

import { useState } from "react";

type QuizCardProps = {
  questionText: string;
  optionA: string;
  optionB: string;
  optionC: string;
  optionD: string;
  questionNumber: number;
  totalQuestions: number;
  topic: string;
  difficulty: string;
  /** Externally-controlled selection (set by QuizSession). */
  selectedAnswer?: string | null;
  /** Called with the selected letter ("A" | "B" | "C" | "D"). */
  onAnswer: (letter: string) => void;
};

const DIFFICULTY_STYLES: Record<string, string> = {
  easy: "quiz-badge--easy",
  medium: "quiz-badge--medium",
  hard: "quiz-badge--hard",
};

export default function QuizCard({
  questionText,
  optionA,
  optionB,
  optionC,
  optionD,
  questionNumber,
  totalQuestions,
  topic,
  difficulty,
  selectedAnswer,
  onAnswer,
}: QuizCardProps) {
  // Use local state only when no external selection is provided.
  const [localSelected, setLocalSelected] = useState<string | null>(
    null,
  );
  const selected =
    selectedAnswer !== undefined ? selectedAnswer : localSelected;

  const options: [string, string][] = [
    ["A", optionA],
    ["B", optionB],
    ["C", optionC],
    ["D", optionD],
  ];

  const handleClick = (letter: string) => {
    if (selectedAnswer === undefined) {
      // Uncontrolled: lock after first click.
      if (localSelected) return;
      setLocalSelected(letter);
    }
    onAnswer(letter);
  };

  return (
    <div className="quiz-card">
      {/* Header */}
      <div className="quiz-card__header">
        <span className="quiz-card__counter">
          Question {questionNumber} of {totalQuestions}
        </span>
        <div className="quiz-card__badges">
          <span className="quiz-badge">{topic}</span>
          <span className={`quiz-badge ${DIFFICULTY_STYLES[difficulty] ?? ""}`}>
            {difficulty}
          </span>
        </div>
      </div>

      {/* Question text */}
      <p className="quiz-card__question">{questionText}</p>

      {/* Options */}
      <div className="quiz-card__options">
        {options.map(([letter, text]) => {
          const isSelected = selected === letter;
          return (
            <button
              key={letter}
              type="button"
              disabled={!!selected}
              onClick={() => handleClick(letter)}
              className={`quiz-option ${isSelected ? "quiz-option--selected" : ""}`}
            >
              <span className="quiz-option__letter">{letter}</span>
              <span className="quiz-option__text">{text}</span>
            </button>
          );
        })}
      </div>

      {selected && (
        <p className="quiz-card__submitted">
          Answer submitted: <strong>{selected}</strong>
        </p>
      )}
    </div>
  );
}
