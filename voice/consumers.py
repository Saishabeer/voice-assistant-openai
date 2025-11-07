import logging
from channels.generic.websocket import JsonWebsocketConsumer
from django.conf import settings

logger = logging.getLogger(__name__)

class VoiceConsumer(JsonWebsocketConsumer):
    """
    WebSocket consumer for real-time voice/chat updates.
    Sends an initial AI greeting on connect when enabled.
    """

    def connect(self):
        self.accept()
        logger.info("Client connected to VoiceConsumer")
        # Send initial message if enabled
        if getattr(settings, "AI_INITIATES_CONVERSATION", True):
            self.send_initial_ai_greeting()

    def disconnect(self, code):
        logger.info("Client disconnected from VoiceConsumer code=%s", code)

    def receive_json(self, content, **kwargs):
        logger.debug("Received from client: %s", content)
        # Handle client messages/audio here if needed.

    def send_initial_ai_greeting(self):
        payload = {
            "type": "ai_message",
            "text": getattr(settings, "AI_WELCOME_MESSAGE", "Hello! How can I help you today?"),
            "speak": getattr(settings, "AI_WELCOME_SPEAK", True),
        }
        logger.info("Sending initial AI greeting")
        self.send_json(payload)