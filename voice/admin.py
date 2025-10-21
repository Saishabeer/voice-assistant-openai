# Clean admin: show only the important fields and a preview of the transcript.
from django.contrib import admin
from .models import Conversation, ConversationAnalysis


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
        "short_conversation",
    )
    list_filter = ("created_at", "last_activity")
    search_fields = ("session_id", "conversation")
    ordering = ("-last_activity",)
    readonly_fields = ("created_at", "updated_at", "last_activity")
    fields = (
        "session_id",
        "conversation",
        "created_at",
        "updated_at",
        "last_activity",
    )


@admin.register(ConversationAnalysis)
class ConversationAnalysisAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "satisfaction_rating", "satisfaction_label", "analysis_timestamp", "created_at")
    list_filter = ("satisfaction_rating", "satisfaction_label")
    search_fields = ("conversation__session_id", "summary", "user_behavior", "conversation_topic")
    readonly_fields = ("raw_json", "raw_response")