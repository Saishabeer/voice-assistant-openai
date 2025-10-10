from django.contrib import admin
from .models import Conversation


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "session_id", "satisfaction_score", "satisfaction_label")
    search_fields = ("session_id", "user_transcript", "ai_transcript", "summary")
    list_filter = ("created_at", "satisfaction_score", "satisfaction_label")