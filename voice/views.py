# Save endpoint: only upsert core fields (session_id, conversation, timestamps); analysis removed.
from __future__ import annotations

import json
import logging
import os
from datetime import timedelta

import httpx
from django.conf import settings
from django.http import (
    HttpRequest,
    HttpResponseBadRequest,
    HttpResponseServerError,
    JsonResponse,
)
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from . import constants as C
from .models import Conversation
from .services.convo import build_conversation_text

logger = logging.getLogger(__name__)


def index(request: HttpRequest):
    """Serve the main page."""
    return render(request, "voice/index.html")


@require_GET
def realtime_session(request: HttpRequest):
    """Mint an ephemeral OpenAI Realtime session for the browser."""
    api_key = getattr(settings, "OPENAI_API_KEY", None) or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not configured")
        return HttpResponseServerError("OPENAI_API_KEY not configured")

    model = os.environ.get("OPENAI_REALTIME_MODEL", C.DEFAULT_REALTIME_MODEL)
    voice = os.environ.get("OPENAI_REALTIME_VOICE", C.DEFAULT_VOICE)
    transcribe_model = os.environ.get("TRANSCRIBE_MODEL", C.DEFAULT_TRANSCRIBE_MODEL)

    # Persona + when to trigger finalize tool (frontend handles greeting/stop)
    tool_directive = (
        "When the user indicates they are ready to end (e.g., 'purchase completed', 'order confirmed', "
        "'that's all', 'no thanks', 'bye', 'end the conversation'), call finalize_conversation with a short 'reason'."
    )
    instructions = f"{C.RISHI_SYSTEM_INSTRUCTION}\n\n{tool_directive}"

    tools = [
        {
            "type": "function",
            "name": "finalize_conversation",
            "description": "Persist final state when the user is ready to end the conversation.",
            "parameters": {
                "type": "object",
                "properties": {"reason": {"type": "string", "description": "Why the session is finishing"}},
                "required": ["reason"],
                "additionalProperties": False,
            },
        }
    ]

    payload = {
        "model": model,
        "modalities": C.DEFAULT_MODALITIES,
        "voice": voice,
        "instructions": instructions,
        "turn_detection": {"type": "server_vad", "silence_duration_ms": 800},
        "input_audio_transcription": {"model": transcribe_model},
        "tools": tools,
        "tool_choice": "auto",
    }

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "OpenAI-Beta": C.OPENAI_BETA_HEADER_VALUE,
        }
        url = C.get_realtime_session_url()
        with httpx.Client(timeout=20) as client:
            resp = client.post(url, headers=headers, json=payload)

        if resp.status_code != 200:
            logger.error("OpenAI session error (%s): %s", resp.status_code, resp.text)
            return HttpResponseServerError(f"OpenAI session error: {resp.text}")

        return JsonResponse(resp.json())
    except Exception:
        logger.exception("Session creation failed")
        return HttpResponseServerError("Session creation failed")


def _find_recent_conversation(session_id: str) -> Conversation | None:
    """Get the most recent conversation for this session in the last 45 minutes."""
    if not session_id:
        return None
    cutoff = timezone.now() - timedelta(minutes=45)
    try:
        return (
            Conversation.objects
            .filter(session_id=session_id, last_activity__gte=cutoff)
            .order_by("-last_activity", "-id")
            .first()
        )
    except Exception:
        return None


@csrf_exempt
@require_POST
def save_conversation(request: HttpRequest):
    """
    Upsert conversation row (single record per active session).

    Body:
      {
        "session_id": "...",
        "user_text": "...",
        "ai_text": "...",
        "conversation_id": 123?   # optional if known by the client
      }

    Returns:
      {
        "status": "ok",
        "id": <int>,
        "session_id": "...",
        "created_at": "...",
        "updated_at": "...",
        "last_activity": "..."
      }
    """
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    user_text = (data.get("user_text") or "").strip()
    ai_text = (data.get("ai_text") or "").strip()
    session_id = (data.get("session_id") or "").strip()
    provided_id = data.get("conversation_id")

    conversation_text = build_conversation_text(user_text, ai_text)
    now = timezone.now()

    # Target: explicit id > recent by session > new
    convo: Conversation | None = None
    if provided_id:
        try:
            convo = Conversation.objects.get(pk=int(provided_id))
        except Exception:
            convo = None
    if not convo:
        convo = _find_recent_conversation(session_id)

    created = False
    if not convo:
        convo = Conversation(
            session_id=session_id,
            conversation=conversation_text,
            last_activity=now,
        )
        created = True

    # Merge and update
    convo.conversation = conversation_text or convo.conversation
    convo.last_activity = now

    # Persist
    try:
        if created:
            convo.save()
        else:
            convo.save(update_fields=["conversation", "last_activity", "updated_at"])
    except Exception:
        logger.exception("Failed to save conversation")
        return HttpResponseServerError("Failed to save conversation")

    logger.info(
        "Conversation upserted | id=%s session=%s",
        convo.id, convo.session_id
    )

    return JsonResponse({
        "status": "ok",
        "id": convo.id,
        "session_id": convo.session_id,
        "created_at": (convo.created_at or now).isoformat(),
        "updated_at": (convo.updated_at or now).isoformat(),
        "last_activity": (convo.last_activity or now).isoformat(),
    })
