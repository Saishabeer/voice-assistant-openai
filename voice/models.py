from django.db import models

# Create your models here.

class Conversation(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    session_id = models.CharField(max_length=128, blank=True, default="")
    user_transcript = models.TextField(blank=True, default="")
    ai_transcript = models.TextField(blank=True, default="")
    summary = models.TextField(blank=True, default="")
    satisfaction_score = models.IntegerField(null=True, blank=True)

    def __str__(self):
        ts = self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else "N/A"
        return f"Conversation #{self.pk} @ {ts}"