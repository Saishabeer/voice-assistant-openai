# Updates _structured_schema to require all properties; everything else unchanged.
# Upserts into one open row per session, re-analyzes only when needed, and supports “close” to finalize the conversation.
"""Persist a single satisfaction_indicator (e.g., '5 - Wow! Great experience') and keep autosave behavior."""
from __future__ import annotations

import json
import logging
import os
from typing import Dict, List, Tuple
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

from . import constants as C  # Centralized constants and defaults
from .models import Conversation

logger = logging.getLogger(__name__)


def index(request: HttpRequest):
    return render(request, "voice/index.html")


@require_GET
def realtime_session(request: HttpRequest):
    """
    Mint an ephemeral realtime session with OpenAI for the browser.
    """
    api_key = getattr(settings, "OPENAI_API_KEY", None) or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not configured")
        return HttpResponseServerError("OPENAI_API_KEY not configured")

    model = os.environ.get("OPENAI_REALTIME_MODEL", C.DEFAULT_REALTIME_MODEL)
    voice = os.environ.get("OPENAI_REALTIME_VOICE", C.DEFAULT_VOICE)
    transcribe_model = os.environ.get("TRANSCRIBE_MODEL", C.DEFAULT_TRANSCRIBE_MODEL)

    # Base system instruction (persona) plus tool usage directive
    base_instructions = C.RISHI_SYSTEM_INSTRUCTION
    tool_directive = """
When the user indicates they are ready to end (e.g., “purchase completed”, “order confirmed”, “that's all”, “I’m done”, “no thanks”, “bye”, “goodbye”, “end the conversation”), call the function finalize_conversation with:
- reason: a short phrase capturing why the session is ending (e.g., “purchase completed”, “user ended”, “no more questions”).
Do not end the call automatically; after the tool call completes, provide a brief closing line and allow the user to end manually.
""".strip()
    instructions = f"{base_instructions}\n\n{tool_directive}"

    tools = [
        {
            "type": "function",
            "name": "finalize_conversation",
            "description": "Persist final state when the user is ready to end the conversation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Why the session is finishing"},
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

    logger.info(
        "Realtime session create | model=%s voice=%s stt=%s base=%s tools=%d",
        model, voice, transcribe_model, C.OPENAI_BASE_URL, len(tools),
    )

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


def _split_turns(text: str) -> List[str]:
    """Split a multi-line transcript into simple per-line turns."""
    if not text:
        return []
    lines = [ln.strip() for ln in text.split("\n")]
    return [ln for ln in lines if ln]


def _build_conversation_text(user_text: str, ai_text: str) -> str:
    """Build a single readable conversation column by interleaving user and AI turns."""
    u_turns = _split_turns(user_text)
    a_turns = _split_turns(ai_text)
    parts: List[str] = []
    n = max(len(u_turns), len(a_turns))
    for i in range(n):
        if i < len(u_turns):
            parts.append(f"User: {u_turns[i]}")
        if i < len(a_turns):
            parts.append(f"AI: {a_turns[i]}")
    return "\n".join(parts)


def _score_to_label(score) -> str:
    mapping = {1: "very bad", 2: "bad", 3: "good", 4: "happy", 5: "excellent"}
    try:
        return mapping.get(int(score), "")
    except Exception:
        return ""


def _format_satisfaction_indicator(score, label: str) -> str:
    """Build a single indicator string, e.g., "5 - Wow! Great experience"."""
    score_int = None
    try:
        score_int = int(score) if score is not None else None
    except Exception:
        score_int = None
    phrases = {
        5: "Wow! Great experience",
        4: "Happy",
        3: "Good",
        2: "Bad",
        1: "Very bad",
    }
    if score_int:
        phrase = phrases.get(score_int) or (label or _score_to_label(score_int)) or ""
        return f"{score_int} - {phrase}".strip(" -")
    return (label or "").strip()


def _heuristic_structured(user_text: str, user_identifier: str, timestamp_iso: str) -> Dict:
    """Fallback structured summary if OpenAI is unavailable."""
    lt = (user_text or "").lower()
    polite = any(p in lt for p in ["please", "thank", "sorry"])
    urgent = any(p in lt for p in ["urgent", "asap", "now", "immediately"])
    hesitant = any(p in lt for p in ["um", "uh", "maybe", "i guess"])
    negative = any(p in lt for p in ["hate", "angry", "annoyed", "frustrated", "upset"])
    risk = any(p in lt for p in ["suicide", "kill myself", "hurt myself", "terror", "threat"])
    sentiment = "negative" if negative else "neutral"
    mood = "stressed" if urgent else ("hesitant" if hesitant else ("polite" if polite else "neutral"))
    behavior = []
    if polite: behavior.append("polite")
    if urgent: behavior.append("urgent")
    if hesitant: behavior.append("hesitant")
    if negative: behavior.append("frustrated")
    return {
        "user": user_identifier or "anonymous",
        "timestamp": timestamp_iso,
        "satisfaction": {"score": None, "label": ""},
        "sentiment": sentiment,
        "mood": mood,
        "behavior": behavior,
        "risk_flags": ["potential_self_harm" if risk else "none"] if risk else [],
        "summary": "Heuristic analysis only (no model available).",
    }


def _structured_schema(name: str = "ConversationInsights") -> Dict:
    """JSON Schema used for strict structured output from the model."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "user": {"type": "string", "description": "User identifier or 'anonymous'"},
                    "timestamp": {"type": "string", "format": "date-time"},
                    "satisfaction": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "score": {"type": "integer", "minimum": 1, "maximum": 5},
                            "label": {"type": "string", "enum": ["very bad", "bad", "good", "happy", "excellent"]},
                        },
                        "required": ["score", "label"],
                    },
                    "sentiment": {"type": "string", "enum": ["very negative", "negative", "neutral", "positive", "very positive"]},
                    "mood": {"type": "string"},
                    "behavior": {"type": "array", "items": {"type": "string"}},
                    "risk_flags": {"type": "array", "items": {"type": "string"}},
                    "summary": {"type": "string"},
                },
                # IMPORTANT: With strict=true, required must include every key in properties.
                "required": ["user", "timestamp", "satisfaction", "sentiment", "mood", "behavior", "risk_flags", "summary"],
            },
        },
    }


def _analyze_conversation_structured(
    user_text: str,
    ai_text: str,
    user_identifier: str,
    timestamp_iso: str,
) -> Dict:
    """Ask the AI to return a strictly-typed structured summary following our schema."""
    api_key = getattr(settings, "OPENAI_API_KEY", None) or os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("OPENAI_SUMMARY_MODEL", C.DEFAULT_SUMMARY_MODEL)
    if not api_key:
        logger.warning("OPENAI_API_KEY missing; using heuristic structured summary")
        return _heuristic_structured(user_text, user_identifier, timestamp_iso)

    system_prompt = (
        "Given the user's transcript and the assistant's reply text, produce a structured analysis. "
        "Use the provided JSON schema strictly. Be concise and evidence-based."
    )
    user_payload_text = (
        f"User identifier: {user_identifier or 'anonymous'}\n"
        f"Conversation time (server): {timestamp_iso}\n\n"
        f"User Transcript:\n{user_text}\n\nAssistant Transcript:\n{ai_text}"
    )

    payload = {
        "model": model,
        "response_format": _structured_schema(),
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_payload_text},
        ],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    url = C.get_chat_completions_url()

    try:
        with httpx.Client(timeout=40) as client:
            resp = client.post(url, headers=headers, json=payload)
        if resp.status_code != 200:
            logger.error("Structured analysis API error (%s): %s", resp.status_code, resp.text)
            return _heuristic_structured(user_text, user_identifier, timestamp_iso)

        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        try:
            structured = json.loads(content) if content else {}
        except Exception:
            start, end = content.find("{"), content.rfind("}")
            structured = json.loads(content[start : end + 1]) if start != -1 and end != -1 else {}

        if not isinstance(structured, dict) or "satisfaction" not in structured:
            return _heuristic_structured(user_text, user_identifier, timestamp_iso)
        return structured
    except Exception:
        logger.exception("Structured analysis generation failed")
        return _heuristic_structured(user_text, user_identifier, timestamp_iso)


def _extract_satisfaction(structured: Dict) -> Tuple[int | None, str]:
    """Pull score/label from structured JSON safely."""
    try:
        sat = structured.get("satisfaction") or {}
        score = sat.get("score")
        label = sat.get("label") or _score_to_label(score)
        return score, label
    except Exception:
        return None, ""


def _content_changed(old_text: str, new_text: str) -> bool:
    """Cheap check to decide whether to recompute analysis."""
    if not old_text and new_text:
        return True
    if not new_text:
        return False
    # Recompute if length difference is meaningful or new_text not contained in old_text
    return abs(len(new_text) - len(old_text)) > 40 or new_text not in old_text


def _find_open_conversation(session_id: str) -> Conversation | None:
    """Find the most recent open conversation for a session in the last 45 minutes."""
    if not session_id:
        return None
    cutoff = timezone.now() - timedelta(minutes=45)
    try:
        return (
            Conversation.objects
            .filter(session_id=session_id, is_closed=False, last_activity__gte=cutoff)
            .order_by("-last_activity", "-id")
            .first()
        )
    except Exception:
        return None


@csrf_exempt
@require_POST
def save_conversation(request: HttpRequest):
    """
    Upsert conversation and derived analysis.
    Request JSON:
      { session_id, user_text, ai_text, conversation_id?, autosave?: bool, reason?: str, close?: bool }
    Response JSON:
      { status: 'ok', id, session_id, is_closed, satisfaction_indicator, created_at }
    """
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    user_text = (data.get("user_text") or "").strip()
    ai_text = (data.get("ai_text") or "").strip()
    session_id = (data.get("session_id") or "").strip()
    provided_id = data.get("conversation_id")
    autosave = bool(data.get("autosave"))
    close_flag = bool(data.get("close"))
    end_reason = (data.get("reason") or "").strip()

    conversation_text = _build_conversation_text(user_text, ai_text)
    now = timezone.now()

    # Upsert target: by provided id, else find open by session, else create new
    convo: Conversation | None = None
    if provided_id:
        try:
            convo = Conversation.objects.get(pk=int(provided_id))
        except Exception:
            convo = None
    if not convo:
        convo = _find_open_conversation(session_id)

    created = False
    if not convo:
        convo = Conversation(
            session_id=session_id,
            conversation=conversation_text,
            user_transcript=user_text,
            ai_transcript=ai_text,
            last_activity=now,
        )
        created = True

    # Merge/Update fields
    content_changed = _content_changed(convo.conversation or "", conversation_text or "")
    convo.conversation = conversation_text or convo.conversation
    convo.user_transcript = user_text or convo.user_transcript
    convo.ai_transcript = ai_text or convo.ai_transcript
    convo.last_activity = now
    if autosave:
        try:
            convo.autosave_count = (convo.autosave_count or 0) + 1
        except Exception:
            convo.autosave_count = 1

    # Close if requested (tool/user ended)
    if close_flag:
        convo.is_closed = True
        if end_reason:
            convo.ended_reason = end_reason

    # Run analysis only when needed
    if created or close_flag or content_changed:
        user_identifier = session_id or "anonymous"
        timestamp_iso = (convo.created_at or now).isoformat()
        structured = _analyze_conversation_structured(user_text, ai_text, user_identifier, timestamp_iso)
        convo.structured = structured
        try:
            convo.summary = (structured.get("summary") or "").strip() if isinstance(structured, dict) else convo.summary
            score, label = _extract_satisfaction(structured if isinstance(structured, dict) else {})
            convo.satisfaction_indicator = _format_satisfaction_indicator(score, label) or convo.satisfaction_indicator
        except Exception:
            logger.warning("Failed to derive fields from structured analysis")

    # Persist
    save_fields = [
        "conversation", "user_transcript", "ai_transcript",
        "last_activity", "autosave_count", "is_closed", "ended_reason",
        "structured", "summary", "satisfaction_indicator",
    ]
    try:
        if created:
            convo.save()
        else:
            convo.save(update_fields=save_fields)
    except Exception:
        logger.exception("Failed saving conversation row")
        return HttpResponseServerError("Failed to save conversation")

    logger.info(
        "Conversation upserted | id=%s session=%s closed=%s autosaves=%s changed=%s",
        convo.id, convo.session_id, convo.is_closed, convo.autosave_count, content_changed
    )

    return JsonResponse({
        "status": "ok",
        "id": convo.id,
        "session_id": convo.session_id,
        "is_closed": convo.is_closed,
        "satisfaction_indicator": convo.satisfaction_indicator or "",
        "created_at": (convo.created_at or now).isoformat(),
    })
