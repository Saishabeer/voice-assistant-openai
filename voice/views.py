from django.conf import settings
from django.http import JsonResponse, HttpResponseServerError
from django.shortcuts import render
import os
import httpx

from . import constants as C  # import centralized constants


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
        return HttpResponseServerError("OPENAI_API_KEY not configured")

    model = os.environ.get("OPENAI_REALTIME_MODEL", C.DEFAULT_REALTIME_MODEL)
    voice = os.environ.get("OPENAI_REALTIME_VOICE", C.DEFAULT_VOICE)
    transcribe_model = os.environ.get("TRANSCRIBE_MODEL", C.DEFAULT_TRANSCRIBE_MODEL)
    instructions = os.environ.get("ASSISTANT_INSTRUCTIONS", C.RISHI_SYSTEM_INSTRUCTION)

    payload = {
        "model": model,
        "modalities": C.DEFAULT_MODALITIES,
        "voice": voice,
        "instructions": instructions,
        "turn_detection": {"type": "server_vad", "silence_duration_ms": 800},
        "input_audio_transcription": {"model": transcribe_model},
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
            return HttpResponseServerError(f"OpenAI session error: {resp.text}")
        return JsonResponse(resp.json())
    except Exception as e:
        return HttpResponseServerError(f"Session creation failed: {e}")
