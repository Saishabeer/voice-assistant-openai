from __future__ import annotations

from typing import Any

from rest_framework import serializers


class SaveConversationSerializer(serializers.Serializer):
    session_id = serializers.CharField(required=False, allow_blank=True, max_length=128)
    conversation_id = serializers.IntegerField(required=False)
    user_text = serializers.CharField(required=False, allow_blank=True, max_length=20000)
    ai_text = serializers.CharField(required=False, allow_blank=True, max_length=20000)
    user_name = serializers.CharField(required=False, allow_blank=True, max_length=128)  # NEW
    finalize = serializers.BooleanField(required=False, default=False)
    confirmed = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        # finalize is honored only if confirmed=True; view handles that logic
        return attrs


class ConversationResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    id = serializers.IntegerField()
    session_id = serializers.CharField(allow_blank=True)
    user_name = serializers.CharField(allow_blank=True, required=False)  # NEW
    created_at = serializers.CharField()
    updated_at = serializers.CharField()
    last_activity = serializers.CharField()
    finalized = serializers.BooleanField()
    summary = serializers.CharField(allow_blank=True, required=False)
    satisfaction_rating = serializers.IntegerField(allow_null=True, required=False)
    satisfaction_label = serializers.CharField(allow_blank=True, required=False)
    conversation_topic = serializers.CharField(allow_blank=True, required=False)
    analysis_timestamp = serializers.CharField(allow_null=True, required=False)