# Show lifecycle fields to inspect open vs. closed conversations and autosave behavior.
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
        "session_id",
        "is_closed",
        "autosave_count",
        "short_conversation",
        "satisfaction_indicator",
        "structured_keys",
    )
    search_fields = ("session_id", "conversation", "summary", "satisfaction_indicator")
    list_filter = ("created_at", "is_closed")