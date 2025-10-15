# Removes the unused BehaviorAnalysis model; keeps Conversation with satisfaction_indicator and structured JSON.
from django.db import models
from django.utils import timezone

class Conversation(models.Model):
    # Timestamp for when the conversation record was created.
    created_at = models.DateTimeField(auto_now_add=True)
    # Timestamp for when the conversation record was last updated.
    updated_at = models.DateTimeField(auto_now=True)
    # Tracks most recent activity time (e.g., last message).
    last_activity = models.DateTimeField(default=timezone.now)
    # The unique ID of the OpenAI Realtime session, for cross-referencing.
    session_id = models.CharField(max_length=128, blank=True, default="")
    # Single-column, human-readable interleaved conversation.
    conversation = models.TextField(blank=True, default="")
    # Legacy separate transcripts (kept for compatibility and analytics if needed).
    user_transcript = models.TextField(blank=True, default="")
    ai_transcript = models.TextField(blank=True, default="")
    # A short, AI-generated summary of the conversation.
    summary = models.TextField(blank=True, default="")
    # Combined satisfaction indicator, e.g., "5 - Wow! Great experience"
    satisfaction_indicator = models.CharField(max_length=120, blank=True, default="")
    # Functional structured JSON schema capturing key fields
    structured = models.JSONField(null=True, blank=True)
    # Lifecycle/state to keep one row per active session
    is_closed = models.BooleanField(default=False)
    ended_reason = models.CharField(max_length=128, blank=True, default="")
    autosave_count = models.IntegerField(default=0)

    def __str__(self):
        """String representation of the model, used in the Django admin UI."""
        ts = self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else "N/A"
        return f"Conversation #{self.pk} @ {ts}"