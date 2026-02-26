import {
  CopilotRuntime,
  ExperimentalEmptyAdapter,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
import { HttpAgent } from "@ag-ui/client";
import { NextRequest, NextResponse } from "next/server";

// 1. You can use any service adapter here for multi-agent support. We use
//    the empty adapter since we're only using one agent.
const serviceAdapter = new ExperimentalEmptyAdapter();

const agentHost = process.env.AGUI_HOST ?? "127.0.0.1";
const agentPort = process.env.AGUI_PORT ?? "8000";
const agentUrl = `http://${agentHost}:${agentPort}/`;

// 2. Create the CopilotRuntime instance and utilize the Microsoft Agent Framework
//    AG-UI integration to setup the connection.
const runtime = new CopilotRuntime({
  agents: {
    my_agent: new HttpAgent({ url: agentUrl }),
  },
});

/**
 * Construct a structured JSON error response (G15 — Frontend Error Resilience).
 * Returns a consistent shape so the frontend can display actionable messages
 * instead of an opaque HTTP 500 error.
 */
function errorResponse(
  status: number,
  error: string,
  message: string,
): NextResponse {
  return NextResponse.json(
    { error, message, timestamp: new Date().toISOString() },
    { status },
  );
}

// 3. Build a Next.js API route that handles the CopilotKit runtime requests.
export const POST = async (req: NextRequest) => {
  try {
    const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
      runtime,
      serviceAdapter,
      endpoint: "/api/copilotkit",
    });

    return await handleRequest(req);
  } catch (err: unknown) {
    const message =
      err instanceof Error ? err.message : "Unknown error";

    console.error("[CopilotKit API] Unhandled error:", err);

    // Network / fetch errors reaching the backend agent
    if (
      err instanceof TypeError &&
      /fetch|network|ECONNREFUSED/i.test(message)
    ) {
      return errorResponse(
        502,
        "backend_unavailable",
        "The AI backend is not reachable. Please ensure the server is running and try again.",
      );
    }

    // Request aborted (e.g. client closed the connection)
    if (
      (err instanceof DOMException && err.name === "AbortError") ||
      /abort/i.test(message)
    ) {
      return errorResponse(
        504,
        "request_timeout",
        "The request was cancelled or timed out. Please try again.",
      );
    }

    // Generic fallback
    return errorResponse(
      500,
      "internal_server_error",
      "The AI service encountered an error. Please try again.",
    );
  }
};