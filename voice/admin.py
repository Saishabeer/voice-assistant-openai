# Clean admin: show transcript, analysis fields, and JSON payloads.
from django.contrib import admin
from .models import Conversation


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    @admin.display(description="Conversation (preview)")
    def short_conversation(self, obj: Conversation):
        text = (obj.conversation or "").replace("\n", " ")
        return (text[:120] + "…") if len(text) > 120 else text

    list_display = (
        "id",
        "created_at",
        "updated_at",
        "last_activity",
        "session_id",
        "satisfaction_rating",
        "satisfaction_label",
        "conversation_topic",
        "short_conversation",
    )
    list_filter = ("created_at", "last_activity", "satisfaction_rating", "satisfaction_label")
    search_fields = ("session_id", "conversation", "summary", "conversation_topic", "satisfaction_label")
    ordering = ("-last_activity",)
    readonly_fields = ("created_at", "updated_at", "last_activity", "raw_json", "raw_response")
    fields = (
        "session_id",
        "conversation",
        "summary",
        ("satisfaction_rating", "satisfaction_label"),
        "user_behavior",
        "conversation_topic",
        "feedback_summary",
        "analysis_timestamp",
        "raw_json",
        "raw_response",
        "created_at",
        "updated_at",
        "last_activity",
    )