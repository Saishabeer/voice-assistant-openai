# Minimal, indexed Conversation model with only the fields you requested.
from django.db import models
from django.utils import timezone


class Conversation(models.Model):
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity = models.DateTimeField(default=timezone.now)

    # Linkage
    session_id = models.CharField(max_length=128, blank=True, default="")

    # Human-readable transcript (interleaved: "User: ...\nAI: ...")
    conversation = models.TextField(blank=True, default="")

    # Derived fields
    summary = models.TextField(blank=True, default="")
    # Single satisfaction text like "5 - Wow! Great experience"
    satisfaction_indicator = models.CharField(max_length=120, blank=True, default="")
    # Structured JSON insights (sentiment, mood, etc.)
    structured = models.JSONField(null=True, blank=True)

    class Meta:
        # Show most active first
        ordering = ["-last_activity", "-id"]
        indexes = [
            models.Index(fields=["session_id"]),
            models.Index(fields=["-last_activity"]),
        ]

    def __str__(self):
        ts = self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else "N/A"
        return f"Conversation #{self.pk} @ {ts}"