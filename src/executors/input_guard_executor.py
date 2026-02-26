"""
Certinator AI — Input Guard Executor

First node in the workflow graph.  Screens every user message
through the local regex-based safety layer before forwarding
to the CoordinatorExecutor.  Blocks prompt injections, harmful
content, and exam-integrity policy violations.

On detection the executor emits a polite refusal message and
terminates — the Coordinator is never reached.

On safe input the executor forwards the messages downstream
via ``ctx.send_message()``.
"""

import logging
from typing import List, Optional, Tuple

from agent_framework import (
    ChatMessage,
    Executor,
    WorkflowContext,
    handler,
)

import metrics
from executors import emit_response
from safety import (
    ContentSafetyResult,
    check_content_safety,
    detect_prompt_injection,
    validate_input,
)

logger = logging.getLogger(__name__)


class InputGuardExecutor(Executor):
    """Regex-based safety gate — screens user messages before LLM.

    Designed to sit as ``set_start_executor`` in the workflow
    graph so every inbound message passes through it.
    """

    def __init__(self, id: str = "input-guard-executor"):
        """Initialise the InputGuard executor.

        Parameters:
            id (str): Executor identifier in the workflow graph.
        """
        super().__init__(id=id)

    @handler
    async def handle(
        self,
        messages: List[ChatMessage],
        ctx: WorkflowContext[List[ChatMessage]],
    ) -> None:
        """Screen incoming messages and block or forward.

        Parameters:
            messages (list[ChatMessage]): Full conversation
                history from the client.
            ctx (WorkflowContext): Typed workflow context for
                forwarding or emitting responses.
        """
        # Extract the latest user message for scanning.
        user_text = self._latest_user_text(messages)

        if not user_text:
            # No user text to scan — forward as-is.
            await ctx.send_message(messages)
            return

        is_safe, refusal = validate_input(user_text)

        if is_safe:
            logger.debug("InputGuard: message passed safety checks.")
            await ctx.send_message(messages)
            return

        # ── Blocked path ──────────────────────────────────────
        reason, category = self._classify_block(user_text)
        logger.warning(
            "InputGuard BLOCKED — reason=%s, category=%s",
            reason,
            category,
        )
        metrics.safety_blocks.add(
            1,
            {"reason": reason, "category": category},
        )

        await emit_response(ctx, self.id, refusal)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _latest_user_text(
        messages: List[ChatMessage],
    ) -> str:
        """Extract plain text from the most recent user message.

        Parameters:
            messages (list[ChatMessage]): Conversation history.

        Returns:
            str: Concatenated text of the last user message, or
                empty string if none found.
        """
        for msg in reversed(messages):
            if getattr(msg, "role", None) and "user" in str(msg.role).lower():
                parts: List[str] = []
                for content in getattr(msg, "contents", []):
                    text = getattr(content, "text", None)
                    if isinstance(text, str) and text.strip():
                        parts.append(text)
                if parts:
                    return " ".join(parts)
        return ""

    @staticmethod
    def _classify_block(
        text: str,
    ) -> Tuple[str, str]:
        """Determine the block reason and category for metrics.

        Parameters:
            text (str): The user message that was blocked.

        Returns:
            tuple[str, str]: ``(reason, category)`` for the OTel
                counter attributes.
        """
        injection = detect_prompt_injection(text)
        if injection:
            return "prompt_injection", "injection"

        safety: ContentSafetyResult = check_content_safety(text)
        if not safety.is_safe:
            cat = safety.category or "unknown"
            if cat.startswith("policy:"):
                return "exam_policy", cat
            return "content_safety", cat

        return "unknown", "unknown"
