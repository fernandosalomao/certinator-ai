import {
  CopilotRuntime,
  ExperimentalEmptyAdapter,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
import { HttpAgent } from "@ag-ui/client";
import { NextRequest } from "next/server";

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

// 3. Build a Next.js API route that handles the CopilotKit runtime requests.
export const POST = async (req: NextRequest) => {
  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime,
    serviceAdapter,
    endpoint: "/api/copilotkit",
  });

  return handleRequest(req);
};