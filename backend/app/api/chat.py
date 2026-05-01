"""
SafetyChat API Router
=====================
Provides two endpoints:

  POST /api/v1/chat/          – single-turn or multi-turn chat
  GET  /api/v1/chat/tools     – list available tool definitions (for docs)
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.chat_service import run_chat, TOOLS

router = APIRouter(prefix="/chat", tags=["SafetyChat"])
logger = logging.getLogger(__name__)


# ── Request / Response schemas ────────────────────────────────────────────────


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(
        ...,
        min_length=1,
        description=(
            "Conversation history. The last message should have role='user'. "
            "Pass previous turns to maintain context across multiple exchanges."
        ),
    )


class ChatResponse(BaseModel):
    reply: str = Field(..., description="Assistant response text.")
    model: str = Field(..., description="OpenAI model that generated the response.")


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/", response_model=ChatResponse, summary="Chat with SafetyChat")
def chat(request: ChatRequest) -> ChatResponse:
    """
    Send a message (or conversation history) to SafetyChat.

    The assistant will automatically call VTTSI data tools as needed to
    ground its response in live safety index data.

    **Example request body:**
    ```json
    {
      "messages": [
        {"role": "user", "content": "Which intersection has the highest risk right now?"}
      ]
    }
    ```
    """
    messages = [m.model_dump() for m in request.messages]

    try:
        reply = run_chat(messages)
    except ValueError as exc:
        # Missing API key or configuration error
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        # openai package missing or API failure
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"SafetyChat error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="SafetyChat encountered an internal error.") from exc

    from ..core.config import settings

    return ChatResponse(reply=reply, model=settings.OPENAI_MODEL)


@router.get("/tools", summary="List SafetyChat tool definitions")
def list_tools() -> dict:
    """
    Return the tool definitions available to the SafetyChat LLM.
    Useful for documentation and debugging.
    """
    return {"tools": TOOLS}
