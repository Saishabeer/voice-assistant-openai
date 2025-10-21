# Views: start realtime session, save conversation, and save analysis on finalize.
from __future__ import annotations

import json
import logging
import os
from datetime import timedelta, datetime, timezone

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
from .services.analysis import analyze_conversation_via_openai

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

    tool_directive = (
        "End-of-conversation policy:\n"
        "- When the user indicates they are ready to end (e.g., 'purchase completed', 'order confirmed', "
        "'that's all', 'we are done', 'no thanks', 'bye', 'end the conversation', 'stop now', 'that's it'), "
        "IMMEDIATELY call the tool finalize_conversation with a brief 'reason' summarizing their intent.\n"
        "- After calling the tool, do not ask further questions or continue the conversation. "
        "Stop producing any further content; the client will handle closing and will run a post-call summary."
    )
    instructions = f"{C.RISHI_SYSTEM_INSTRUCTION}\n\n{tool_directive}"

    tools = [
        {
            "type": "function",
            "name": "finalize_conversation",
            "description": "Persist final state when the user is ready to end the conversation. The client will end the call.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Why the session is finishing (e.g., 'purchase completed', 'user said bye')."
                    }
                },
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
            return HttpResponseServerError("Failed to create session")
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
    If finalize=true, run OpenAI analysis and store summary/satisfaction on the same Conversation row.
    """
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return HttpResponseServerError("Invalid JSON")

    user_text = (data.get("user_text") or "").strip()
    ai_text = (data.get("ai_text") or "").strip()
    session_id = (data.get("session_id") or "").strip()
    provided_id = data.get("conversation_id")
    finalize = bool(data.get("finalize", False))

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

    # Merge and update transcript
    convo.conversation = conversation_text or convo.conversation
    convo.last_activity = now

    # Persist transcript first
    try:
        if created:
            convo.save()
        else:
            convo.save(update_fields=["conversation", "last_activity", "updated_at"])
    except Exception:
        logger.exception("Failed to save conversation")
        return HttpResponseServerError("Failed to save conversation")

    # If finalize requested, call OpenAI to get structured JSON and store it on this row
    if finalize:
        try:
            parsed, raw_payload = analyze_conversation_via_openai(convo.conversation)
            ts_str = parsed.get("timestamp") or ""
            try:
                ts_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00")) if ts_str else datetime.now(timezone.utc)
            except Exception:
                ts_dt = datetime.now(timezone.utc)

            convo.summary = parsed.get("summary", "") or ""
            level = parsed.get("satisfaction_level") or {}
            convo.satisfaction_rating = int(level.get("rating")) if level.get("rating") is not None else None
            convo.satisfaction_label = str(level.get("label") or "")
            convo.user_behavior = parsed.get("user_behavior", "") or ""
            convo.conversation_topic = parsed.get("conversation_topic", "") or ""
            convo.feedback_summary = parsed.get("feedback_summary", "") or ""
            convo.analysis_timestamp = ts_dt
            convo.raw_json = parsed
            convo.raw_response = raw_payload
            convo.save(update_fields=[
                "summary",
                "satisfaction_rating",
                "satisfaction_label",
                "user_behavior",
                "conversation_topic",
                "feedback_summary",
                "analysis_timestamp",
                "raw_json",
                "raw_response",
                "updated_at",
            ])
            logger.info("Analysis saved on conversation | id=%s rating=%s", convo.id, convo.satisfaction_rating)
        except Exception:
            logger.exception("Failed to run/store conversation analysis")

    return JsonResponse({
        "status": "ok",
        "id": convo.id,
        "session_id": convo.session_id,
        "created_at": (convo.created_at or now).isoformat(),
        "updated_at": (convo.updated_at or now).isoformat(),
        "last_activity": (convo.last_activity or now).isoformat(),
        # Return analysis snapshot (may be empty if not finalized or if analysis failed)
        "summary": convo.summary,
        "satisfaction_rating": convo.satisfaction_rating,
        "satisfaction_label": convo.satisfaction_label,
        "conversation_topic": convo.conversation_topic,
        "analysis_timestamp": convo.analysis_timestamp.isoformat() if convo.analysis_timestamp else None,
    })
