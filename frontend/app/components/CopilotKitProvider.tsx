"use client";

import { CopilotKit } from "@copilotkit/react-core";
import type { ReactNode } from "react";

type CopilotKitProviderProps = {
  children: ReactNode;
};

export default function CopilotKitProvider({ children }: CopilotKitProviderProps) {
  return (
    <CopilotKit
      runtimeUrl="/api/copilotkit"
      agent="my_agent"
      showDevConsole={process.env.NODE_ENV === "development"}
      onError={(errorEvent) => {
        // Development error logging
        console.error("[CopilotKit Error]", {
          type: errorEvent.type,
          timestamp: new Date(errorEvent.timestamp).toISOString(),
          context: errorEvent.context,
          error: errorEvent.error,
        });
      }}
    >
      {children}
    </CopilotKit>
  );
}
