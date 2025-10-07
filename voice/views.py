from django.conf import settings
from django.http import JsonResponse, HttpResponseServerError
from django.shortcuts import render
import os
import httpx
import logging

from . import constants as C  # import centralized constants

logger = logging.getLogger(__name__)

def index(request):
    return render(request, "voice/index.html")


def realtime_session(request):
    """
    Creates an ephemeral OpenAI Realtime session for browser WebRTC.
    Config via env (overrides defaults in constants):
      - OPENAI_API_KEY
      - OPENAI_BASE_URL (default: https://api.openai.com)
      - OPENAI_REALTIME_MODEL (default: C.DEFAULT_REALTIME_MODEL)
      - OPENAI_REALTIME_VOICE (default: C.DEFAULT_VOICE)
      - TRANSCRIBE_MODEL (default: C.DEFAULT_TRANSCRIBE_MODEL)
      - ASSISTANT_INSTRUCTIONS (default: RISHI_SYSTEM_INSTRUCTION)
    """
    api_key = getattr(settings, "OPENAI_API_KEY", None) or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not configured")
        return HttpResponseServerError("OPENAI_API_KEY not configured")

    model = os.environ.get("OPENAI_REALTIME_MODEL", C.DEFAULT_REALTIME_MODEL)
    voice = os.environ.get("OPENAI_REALTIME_VOICE", C.DEFAULT_VOICE)
    transcribe_model = os.environ.get("TRANSCRIBE_MODEL", C.DEFAULT_TRANSCRIBE_MODEL)
    instructions = C.RISHI_SYSTEM_INSTRUCTION

    payload = {
        "model": model,
        "modalities": C.DEFAULT_MODALITIES,
        "voice": voice,
        # System/persona prompt must be top-level "instructions" for OpenAI Realtime
        "instructions": instructions,
        "turn_detection": {"type": "server_vad", "silence_duration_ms": 800},
        "input_audio_transcription": {"model": transcribe_model},
    }

    # Log what we are sending (partial preview, no secrets)
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
    except Exception as e:
        logger.exception("Session creation failed")
        return HttpResponseServerError(f"Session creation failed: {e}")
