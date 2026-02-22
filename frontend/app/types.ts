/**
 * Certinator AI — Shared TypeScript types
 *
 * Mirrors the Pydantic models in `src/executors/models.py` so that
 * CopilotKit shared-state hooks and HITL components stay type-safe.
 */

// ---------------------------------------------------------------------------
// Practice Question
// ---------------------------------------------------------------------------

export type PracticeQuestion = {
  question_number: number;
  question_text: string;
  options: Record<string, string>; // { A: "...", B: "...", C: "...", D: "..." }
  correct_answer: string;
  explanation: string;
  topic: string;
  difficulty: "easy" | "medium" | "hard";
};

// ---------------------------------------------------------------------------
// Quiz State (mirrors QuizState in models.py)
// ---------------------------------------------------------------------------

export type QuizState = {
  quiz_id: string;
  certification: string;
  questions: PracticeQuestion[];
  current_index: number;
  answers: string[];
  status: "in_progress" | "completed";
  topics: string[];
};

// ---------------------------------------------------------------------------
// Agent shared-state snapshot exposed via useCoAgent
// ---------------------------------------------------------------------------

export type CertinatorAgentState = {
  /** Active quiz session (set by PracticeQuizOrchestrator). */
  active_quiz_state?: QuizState;
  /** Current multi-step workflow progress for in-chat rendering. */
  workflow_progress?: WorkflowProgress;
  /** Post-study-plan context (set by PostStudyPlanHandler). */
  post_study_plan_context?: {
    certification: string;
    context: string;
  };
};

export type WorkflowProgress = {
  route: "study_plan" | "cert_info" | "practice" | "general";
  active_executor: string;
  message: string;
  current_step: number;
  total_steps: number;
  status: "in_progress" | "completed";
  updated_at: string;
  reasoning?: string;
};

// ---------------------------------------------------------------------------
// HITL parameter shapes (match useHumanInTheLoop parameter lists)
// ---------------------------------------------------------------------------

/** Args forwarded to the quiz-answer HITL component. */
export type QuizAnswerArgs = {
  questionText: string;
  optionA: string;
  optionB: string;
  optionC: string;
  optionD: string;
  questionNumber: number;
  totalQuestions: number;
  topic: string;
  difficulty: string;
};

/** Args forwarded to yes/no offer HITL components. */
export type OfferArgs = {
  message: string;
  certification: string;
};
