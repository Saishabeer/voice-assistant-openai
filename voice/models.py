from __future__ import annotations

from django.db import models
from django.utils import timezone


class Conversation(models.Model):
    """
    Stores the full session transcript and (optional) post-conversation analysis.
    A single upserted record is maintained per active session window.
    """
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity = models.DateTimeField(default=timezone.now)

    # Linkage
    session_id = models.CharField(max_length=128, blank=True, default="")

    # Transcript (interleaved: "User: ...\nAI: ...")
    conversation = models.TextField(blank=True, default="")

    # Analysis fields (all optional; populated when finalize=true)
    summary = models.TextField(blank=True, default="")
    satisfaction_rating = models.IntegerField(null=True, blank=True)
    satisfaction_label = models.CharField(max_length=64, blank=True, default="")
    user_behavior = models.TextField(blank=True, default="")
    conversation_topic = models.CharField(max_length=128, blank=True, default="")
    feedback_summary = models.TextField(blank=True, default="")
    analysis_timestamp = models.DateTimeField(null=True, blank=True)

    # Preserve the parsed structured JSON and the full raw API payload
    raw_json = models.JSONField(null=True, blank=True)
    raw_response = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-last_activity", "-id"]
        db_table = "voice_conversation"
        indexes = [
            models.Index(fields=["session_id"]),
            models.Index(fields=["last_activity"]),
        ]

    def __str__(self):
        ts = self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else "N/A"
        return f"Conversation #{self.pk} @ {ts}"