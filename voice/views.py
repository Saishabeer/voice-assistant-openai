from django.conf import settings
from django.http import JsonResponse, HttpResponseServerError, HttpResponseBadRequest
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
import os
import json
import httpx
import logging

from . import constants as C  # centralized constants
from .models import Conversation

logger = logging.getLogger(__name__)

def index(request):
    return render(request, "voice/index.html")


def realtime_session(request):
    """
    Creates an ephemeral OpenAI Realtime session for browser WebRTC.
    Uses Rishi persona from constants (no env override).
    """
    # 1) API Key Validation
    api_key = getattr(settings, "OPENAI_API_KEY", None) or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not configured")
        return HttpResponseServerError("OPENAI_API_KEY not configured")

    # 2) Load Configuration
    model = os.environ.get("OPENAI_REALTIME_MODEL", C.DEFAULT_REALTIME_MODEL)
    voice = os.environ.get("OPENAI_REALTIME_VOICE", C.DEFAULT_VOICE)
    transcribe_model = os.environ.get("TRANSCRIBE_MODEL", C.DEFAULT_TRANSCRIBE_MODEL)

    # Always use the Rishi persona (do not read ASSISTANT_INSTRUCTIONS from env)
    instructions = C.RISHI_SYSTEM_INSTRUCTION

    # 3) Construct Payload
    payload = {
        "model": model,
        "modalities": C.DEFAULT_MODALITIES,
        "voice": voice,
        "instructions": instructions,  # persona prompt at top-level
        "turn_detection": {"type": "server_vad", "silence_duration_ms": 800},
        "input_audio_transcription": {"model": transcribe_model},
    }

    # 4) Log details
    preview = (instructions or "")[:120].replace("\n", " ")
    logger.info(
        "Creating Realtime session | model=%s | voice=%s | stt=%s | base=%s | instructions_len=%d | preview='%s...'",
        model, voice, transcribe_model, C.OPENAI_BASE_URL, len(instructions or ""), preview
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
        data = resp.json()
        logger.info("Realtime session created | id=%s | expires_at=%s", data.get("id"), data.get("expires_at"))
        return JsonResponse(data)
    except Exception:
        logger.exception("Session creation failed")
        return HttpResponseServerError("Session creation failed")


def _summarize_conversation_with_openai(user_text: str, ai_text: str) -> dict:
    """
    Calls OpenAI Chat Completions to produce a compact JSON summary and satisfaction score (1-5).
    Returns dict: {"summary": str, "satisfaction_score": int, "reasoning": str}
    """
    api_key = getattr(settings, "OPENAI_API_KEY", None) or os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("OPENAI_SUMMARY_MODEL", C.DEFAULT_SUMMARY_MODEL)
    if not api_key:
        logger.warning("OPENAI_API_KEY missing for summary; skipping")
        return {}

    system_prompt = (
        "You are a conversation analyst. Given a user and assistant transcript, produce:\n"
        "1) a concise 2–3 sentence summary (business-focused)\n"
        "2) a user satisfaction_score from 1 (very dissatisfied) to 5 (very satisfied)\n"
        "3) a brief reasoning (one sentence)\n\n"
        "Return ONLY a strictly valid JSON object with keys exactly: "
        '{"summary": "...", "satisfaction_score": 1-5, "reasoning": "..."}'
    )

    user_payload_text = f"User Transcript:\n{user_text}\n\nAssistant Transcript:\n{ai_text}"

    payload = {
        "model": model,
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_payload_text},
        ],
    }

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    url = C.get_chat_completions_url()

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(url, headers=headers, json=payload)
        if resp.status_code != 200:
            logger.error("Summary API error (%s): %s", resp.status_code, resp.text)
            return {}
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        result = {}
        if isinstance(content, str) and content.strip():
            try:
                result = json.loads(content)
            except Exception:
                start = content.find("{")
                end = content.rfind("}")
                if start != -1 and end != -1 and end > start:
                    try:
                        result = json.loads(content[start : end + 1])
                    except Exception:
                        logger.warning("Failed to parse summary JSON: %s", content)
                        result = {}
        if not isinstance(result, dict) or "summary" not in result:
            logger.warning("Summary response missing required keys: %s", result)
            return {}
        return result
    except Exception:
        logger.exception("Summary generation failed")
        return {}


@csrf_exempt
def save_conversation(request):
    """
    POST endpoint to store the final conversation transcripts and generate a short summary.

    Expected JSON:
    {
      "session_id": "optional-string",
      "user_text": "full user transcript",
      "ai_text": "full assistant transcript"
    }
    """
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    # Entry logging
    try:
        raw = request.body.decode("utf-8")
        logger.info("save_conversation called | raw_len=%d", len(raw))
        data = json.loads(raw) if raw else {}
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    user_text = data.get("user_text", "") or ""
    ai_text = data.get("ai_text", "") or ""
    session_id = data.get("session_id", "") or ""

    logger.info(
        "save_conversation payload | session_id='%s' | user_len=%d | ai_len=%d",
        session_id, len(user_text), len(ai_text)
    )

    # 1) Store conversation
    convo = Conversation.objects.create(
        session_id=session_id,
        user_transcript=user_text,
        ai_transcript=ai_text,
    )

    # 2) Summarize and score
    summary_obj = _summarize_conversation_with_openai(user_text, ai_text)
    summary = summary_obj.get("summary", "")
    satisfaction = summary_obj.get("satisfaction_score", None)
    if summary or satisfaction is not None:
        try:
            convo.summary = summary
            convo.satisfaction_score = int(satisfaction) if satisfaction is not None else None
            convo.save(update_fields=["summary", "satisfaction_score"])
        except Exception:
            logger.warning("Failed to set satisfaction score to int: %s", satisfaction)

    # 3) Print to terminal
    print("\n===== Conversation Saved =====")
    print(f"ID: {convo.id} | Session: {convo.session_id} | Created: {convo.created_at}")
    print("---- User Transcript ----")
    print(user_text)
    print("---- AI Transcript ----")
    print(ai_text)
    if summary or satisfaction is not None:
        print("---- Summary ----")
        print(summary or "(empty)")
        print("---- Satisfaction (1-5) ----")
        print(satisfaction if satisfaction is not None else "(n/a)")
    print("==============================\n")

    logger.info(
        "Conversation saved | id=%s | session_id=%s | user_len=%d | ai_len=%d | satisfaction=%s",
        convo.id, convo.session_id, len(user_text), len(ai_text), str(satisfaction),
    )

    return JsonResponse({"ok": True, "id": convo.id, "summary": summary, "satisfaction_score": satisfaction})
