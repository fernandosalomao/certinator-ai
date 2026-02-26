"use client";

import { CopilotKit } from "@copilotkit/react-core";
import type { CopilotKitCSSProperties } from "@copilotkit/react-ui";
import type { ReactNode } from "react";

/**
 * CopilotKit CSS-variable theme (V3 fix).
 *
 * Sets core colours via the official CSS-variable API so that we avoid
 * `!important` overrides in globals.css. CopilotKit reads these variables
 * from the nearest ancestor with [data-copilotkit] — wrapping with a plain
 * <div> is the recommended approach from the docs.
 *
 * @see https://docs.copilotkit.ai/custom-look-and-feel/customize-built-in-ui-components#css-variables-easiest
 */
const copilotTheme: CopilotKitCSSProperties = {
  "--copilot-kit-primary-color": "#6f87ff",
  "--copilot-kit-contrast-color": "#ffffff",
  "--copilot-kit-background-color": "transparent",
  "--copilot-kit-secondary-color": "#111a36",
  "--copilot-kit-secondary-contrast-color": "#e8eeff",
  "--copilot-kit-separator-color": "transparent",
  "--copilot-kit-muted-color": "#152040",
};

type CopilotKitProviderProps = {
  children: ReactNode;
};

export default function CopilotKitProvider({ children }: CopilotKitProviderProps) {
  return (
    <div style={copilotTheme}>
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
    </div>
  );
}
