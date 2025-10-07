# voice/views.py
import os

import httpx

from django.conf import settings
from django.http import JsonResponse, HttpResponseServerError
from django.shortcuts import render

def index(request):
    return render(request, "voice/index.html")

def realtime_session(request):
    """
    Creates a short-lived OpenAI Realtime session token for the browser WebRTC connection.
    Enables Whisper transcription for live input transcripts.
    """
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        return HttpResponseServerError("OPENAI_API_KEY not configured")

    # Choose a current realtime model; adjust as OpenAI updates model names.
    model = os.environ.get("OPENAI_REALTIME_MODEL", "gpt-4o-realtime-preview")

    payload = {
        "model": model,
        # Enable audio output and text so we can hear and display AI responses
        "modalities": ["text", "audio"],
        # Enable Whisper transcription for live input speech
        "input_audio_transcription": {"model": "whisper-1"},
        # Choose a voice for AI speech
        "voice": os.environ.get("OPENAI_REALTIME_VOICE", "verse"),
        # Optional: server-side voice activity detection (auto turn-taking)
        "turn_detection": {"type": "server_vad", "silence_duration_ms": 800},
        # Optional: system instructions
        "instructions": os.environ.get("ASSISTANT_INSTRUCTIONS", "You are a helpful real-time voice assistant."),
    }

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "OpenAI-Beta": "realtime=v1",
        }
        with httpx.Client(timeout=15) as client:
            resp = client.post("https://api.openai.com/v1/realtime/sessions", headers=headers, json=payload)
        if resp.status_code != 200:
            return HttpResponseServerError(f"OpenAI session error: {resp.text}")
        data = resp.json()
        # data contains client_secret.value (ephemeral key), id, expires_at, etc.
        return JsonResponse(data)
    except Exception as e:
        return HttpResponseServerError(f"Session creation failed: {e}")
