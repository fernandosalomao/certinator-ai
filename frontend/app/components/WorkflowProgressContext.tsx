"use client";

import { createContext, useContext, type ReactNode } from "react";
import type { WorkflowProgress as WorkflowProgressState } from "../types";

type WorkflowProgressContextType = {
  currentProgress: WorkflowProgressState | undefined;
};

const WorkflowProgressContext = createContext<WorkflowProgressContextType>({
  currentProgress: undefined,
});

export function WorkflowProgressProvider({
  children,
  currentProgress,
}: {
  children: ReactNode;
  currentProgress: WorkflowProgressState | undefined;
}) {
  return (
    <WorkflowProgressContext.Provider value={{ currentProgress }}>
      {children}
    </WorkflowProgressContext.Provider>
  );
}

export function useWorkflowProgress() {
  return useContext(WorkflowProgressContext);
}
