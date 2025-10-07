# voice/consumers.py
import os
import base64
import tempfile
import json
import httpx
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

OPENAI_API_KEY = settings.OPENAI_API_KEY

# Map common audio MIME types to file extensions
MIME_EXTENSIONS = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/oga": ".oga",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/mp4": ".mp4",
    "audio/m4a": ".m4a",
    "video/mp4": ".mp4",
    "audio/flac": ".flac",
    "audio/mpga": ".mpga",
}

class AudioConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        await self.send(text_data=json.dumps({"type": "info", "message": "websocket connected"}))

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return

        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({"type": "error", "message": "Invalid JSON"}))
            return

        message_type = data.get("type")
        if message_type in ("final", "chunk"):  # prefer "final" from frontend
            b64 = data.get("audio_base64")
            mime = data.get("mime") or "audio/webm"
            language = data.get("language") or "en"

            transcript = await self._transcribe_audio(b64, mime, language)
            await self.send(text_data=json.dumps({"type": "transcript", "text": transcript}))
        else:
            await self.send(text_data=json.dumps({"type": "error", "message": f"Unknown message type: {message_type}"}))

    async def _transcribe_audio(self, b64_data_url: str, mime: str, language: str):
        if not OPENAI_API_KEY or "your_key_here" in OPENAI_API_KEY:
            return "[error] OpenAI API key is not configured."

        if not b64_data_url:
            return "[error] No audio data received."

        # Strip "data:...;base64," prefix if present
        header_sep = b64_data_url.find(",")
        if header_sep != -1:
            b64 = b64_data_url[header_sep + 1 :]
        else:
            b64 = b64_data_url

        try:
            audio_bytes = base64.b64decode(b64)
        except (TypeError, ValueError) as e:
            return f"[error] Invalid base64 data: {e}"

        # Clean MIME (drop any codec parameters)
        clean_mime = (mime or "").split(";")[0].strip().lower() or "audio/webm"
        file_extension = MIME_EXTENSIONS.get(clean_mime, ".webm")

        temp_filename = ""
        try:
            # Write to a temp file
            with tempfile.NamedTemporaryFile(mode="wb", suffix=file_extension, delete=False) as temp_file:
                temp_file.write(audio_bytes)
                temp_filename = temp_file.name

            async with httpx.AsyncClient(timeout=60) as client:
                url = "https://api.openai.com/v1/audio/transcriptions"
                headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
                data = {"model": "whisper-1", "language": language}

                with open(temp_filename, "rb") as f:
                    files = {"file": (f"audio{file_extension}", f, clean_mime)}
                    resp = await client.post(url, headers=headers, files=files, data=data)

            if resp.status_code == 200:
                try:
                    return resp.json().get("text", "")
                except Exception:
                    return "[error] Unable to parse transcription response."
            else:
                # Provide clearer error feedback
                try:
                    details = resp.json()
                except Exception:
                    details = {"raw": resp.text}
                return f"[transcription error {resp.status_code}] {details}"
        except Exception as e:
            return f"[error] During processing: {str(e)}"
        finally:
            if temp_filename and os.path.exists(temp_filename):
                try:
                    os.remove(temp_filename)
                except Exception:
                    pass
