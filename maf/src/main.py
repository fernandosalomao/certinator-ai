from __future__ import annotations

import os

import uvicorn
from agent import create_agent
from agent_framework_ag_ui import add_agent_framework_fastapi_endpoint
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()
my_agent = create_agent()


app = FastAPI(title="CopilotKit + Microsoft Agent Framework (Python)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

add_agent_framework_fastapi_endpoint(
    app=app,
    agent=my_agent,
    path="/",
)


if __name__ == "__main__":
    host = os.getenv("AGENT_HOST", "0.0.0.0")
    port = int(os.getenv("AGENT_PORT", "8000"))
    uvicorn.run("main:app", host=host, port=port, reload=True)
