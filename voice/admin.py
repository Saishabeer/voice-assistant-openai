# Clean admin: show only the important fields and a preview of the transcript.
from django.contrib import admin
from .models import Conversation


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    @admin.display(description="Conversation (preview)")
    def short_conversation(self, obj: Conversation):
        text = (obj.conversation or "").replace("\n", " ")
        return (text[:120] + "…") if len(text) > 120 else text

    @admin.display(description="Structured keys")
    def structured_keys(self, obj: Conversation):
        if not obj.structured:
            return ""
        if isinstance(obj.structured, dict):
            return ", ".join(list(obj.structured.keys())[:6])
        return type(obj.structured).__name__

    list_display = (
        "id",
        "created_at",
        "updated_at",
        "last_activity",
        "session_id",
        "short_conversation",
        "satisfaction_indicator",
        "structured_keys",
    )
    list_filter = ("created_at",)
    search_fields = ("session_id", "conversation", "summary", "satisfaction_indicator")
    readonly_fields = ("created_at", "updated_at", "last_activity")
    fields = (
        "session_id",
        "conversation",
        "summary",
        "satisfaction_indicator",
        "structured",
        "created_at",
        "updated_at",
        "last_activity",
    )