"""Copiloto chat endpoint (SDD §12.4).

POST /v1/copilot/chat
  - Authenticates via JWT (same _require_user as all other endpoints)
  - Resolves data context server-side from the verified token (never from body)
  - Builds a scoped system prompt that embeds only authorized zone data
  - Calls Claude (Haiku 4.5 by default; configurable via ANTHROPIC_MODEL_COPILOT)
  - Returns the assistant response

The authorization context (tenant_id, role, partner_id, site_ids) comes
exclusively from the JWT claim — the request body only carries the user's
question. A Partner cannot escalate scope by passing a different tenant_id
in the body; the server ignores any such attempt.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

import jwt

from cloud import config
from cloud.copilot.context import build_data_context
from cloud.copilot.prompt import build_system_prompt

log = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/copilot", tags=["copilot"])

_bearer = HTTPBearer()


# ── Auth ─────────────────────────────────────────────────────────────────────

def _require_user(
    creds: HTTPAuthorizationCredentials = Security(_bearer),
) -> dict:
    try:
        return jwt.decode(
            creds.credentials, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM]
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "token_expired")
    except jwt.PyJWTError:
        raise HTTPException(401, "invalid_token")


# ── Request / Response ────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str
    # No scope/tenant/role fields — those come from the JWT only


class ChatResponse(BaseModel):
    answer: str
    authorized_zone_count: int
    model: str


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, token: dict = Depends(_require_user)) -> ChatResponse:
    """Answer a natural language question within the user's authorized scope.

    Authorization context is derived exclusively from the verified JWT —
    the question is the only user-controlled input.
    """
    if not config.ANTHROPIC_API_KEY:
        raise HTTPException(503, "copilot_not_configured")
    if not body.question.strip():
        raise HTTPException(422, "question must not be empty")
    if len(body.question) > 2000:
        raise HTTPException(422, "question exceeds maximum length of 2000 characters")

    # Resolve context server-side from JWT + RLS
    ctx = build_data_context(token)
    system_prompt = build_system_prompt(ctx)

    try:
        import anthropic as _anthropic
        client = _anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=config.ANTHROPIC_MODEL_COPILOT,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": body.question}],
        )
        answer = response.content[0].text
    except Exception as exc:
        log.error("Copilot API call failed: %s", exc)
        raise HTTPException(502, "copilot_api_error")

    return ChatResponse(
        answer=answer,
        authorized_zone_count=len(ctx["authorized_zone_ids"]),
        model=config.ANTHROPIC_MODEL_COPILOT,
    )
