# Clean admin: show only the important fields and a preview of the transcript.
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
        "short_conversation",
    )
    list_filter = ("created_at", "last_activity")
    search_fields = ("session_id", "conversation")
    readonly_fields = ("created_at", "updated_at", "last_activity")
    fields = (
        "session_id",
        "conversation",
        "created_at",
        "updated_at",
        "last_activity",
    )