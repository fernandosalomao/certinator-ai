"""Quick HITL flow test — sends a quiz request, captures
the request_info tool call, then simulates the frontend
answer with a role:tool message."""

import json
import sys

import requests

BASE = "http://127.0.0.1:8000/"
TIMEOUT = 120


def send_and_collect(payload: dict) -> list[dict]:
    """POST to the AG-UI endpoint, collect SSE events."""
    resp = requests.post(
        BASE,
        json=payload,
        stream=True,
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    events = []
    for line in resp.iter_lines():
        if not line:
            continue
        decoded = line.decode()
        if decoded.startswith("data: "):
            raw = decoded[6:]
            try:
                events.append(json.loads(raw))
            except json.JSONDecodeError:
                pass
    return events


def main():
    # --- Step 1: trigger the quiz ---------------------------------
    print("=== Step 1: request quiz ===")
    payload1 = {
        "messages": [
            {
                "role": "user",
                "content": ("Start a 3-question practice quiz for AZ-900"),
            },
        ],
        "threadId": "test-thread-hitl",
        "runId": "run-1",
    }
    events1 = send_and_collect(payload1)
    print(f"Got {len(events1)} events")
    for e in events1:
        t = e.get("type", "")
        print(f"  {t}", end="")
        if t == "TOOL_CALL_START":
            print(
                f"  name={e.get('toolCallName')} id={e.get('toolCallId')}",
                end="",
            )
        print()

    # Find tool_call_id for request_info
    tool_call_id = None
    for e in events1:
        if (
            e.get("type") == "TOOL_CALL_START"
            and e.get("toolCallName") == "request_info"
        ):
            tool_call_id = e["toolCallId"]
            break

    if not tool_call_id:
        print("ERROR: no request_info tool call found!")
        sys.exit(1)

    print(f"\ntool_call_id = {tool_call_id}")

    # --- Step 2: send the answer back -----------------------------
    print("\n=== Step 2: submit quiz answers ===")
    answer_payload = json.dumps({"answers": {"1": "B", "2": "A", "3": "C"}})

    payload2 = {
        "messages": [
            # CopilotKit always replays the full history
            {
                "role": "user",
                "content": ("Start a 3-question practice quiz for AZ-900"),
            },
            # The tool call from the assistant
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": tool_call_id,
                        "type": "function",
                        "function": {
                            "name": "request_info",
                            "arguments": "{}",
                        },
                    },
                ],
            },
            # The user's answer (role: tool)
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": answer_payload,
            },
        ],
        "threadId": "test-thread-hitl",
        "runId": "run-2",
    }

    events2 = send_and_collect(payload2)
    print(f"Got {len(events2)} events")
    for e in events2:
        t = e.get("type", "")
        print(f"  {t}", end="")
        if t == "TEXT_MESSAGE_CONTENT":
            delta = e.get("delta", "")
            print(f"  delta={delta[:80]!r}", end="")
        if t == "RUN_ERROR":
            print(f"  message={e.get('message', '')!r}", end="")
        print()


if __name__ == "__main__":
    main()
