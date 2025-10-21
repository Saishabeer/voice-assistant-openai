from __future__ import annotations

from django.db import models
from django.utils import timezone


class Conversation(models.Model):
    """
    Stores the combined transcript for a browser session.
    A single upserted record is maintained per active session window.
    """
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity = models.DateTimeField(default=timezone.now)

    # Linkage
    session_id = models.CharField(max_length=128, blank=True, default="")

    # Human-readable transcript (interleaved: "User: ...\nAI: ...")
    conversation = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-last_activity", "-id"]
        db_table = "voice_conversation"
        indexes = [
            models.Index(fields=["session_id"]),
            # FIX: Index.fields must not include ordering; use the plain field name.
            models.Index(fields=["last_activity"]),
        ]

    def __str__(self):
        ts = self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else "N/A"
        return f"Conversation #{self.pk} @ {ts}"


class ConversationAnalysis(models.Model):
    """
    Stores the structured summary/satisfaction analysis for a conversation.
    Data is produced by OpenAI as strict JSON, no manual classification.
    """
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="analyses"
    )

    # Extracted structured fields
    summary = models.TextField()
    satisfaction_rating = models.IntegerField()
    satisfaction_label = models.CharField(max_length=64)
    user_behavior = models.TextField()
    conversation_topic = models.CharField(max_length=128)
    feedback_summary = models.TextField()
    analysis_timestamp = models.DateTimeField()

    # Preserve the parsed structured JSON and the full raw API payload
    raw_json = models.JSONField(null=True, blank=True)
    raw_response = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        db_table = "voice_conversation_analysis"
        indexes = [
            models.Index(fields=["conversation"]),
        ]

    def __str__(self) -> str:
        return f"ConversationAnalysis(conversation_id={self.conversation_id}, rating={self.satisfaction_rating})"