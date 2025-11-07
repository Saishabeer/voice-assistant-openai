from __future__ import annotations

from typing import Any, Dict
from datetime import timedelta

from django.utils import timezone
from .models import Conversation
from .services.convo import build_conversation_text

from rest_framework import serializers


class SaveConversationSerializer(serializers.Serializer):
    session_id = serializers.CharField(required=False, allow_blank=True, max_length=128)
    conversation_id = serializers.IntegerField(required=False)
    user_text = serializers.CharField(required=False, allow_blank=True, max_length=20000)
    ai_text = serializers.CharField(required=False, allow_blank=True, max_length=20000)
    user_name = serializers.CharField(required=False, allow_blank=True, max_length=128)  # NEW
    finalize = serializers.BooleanField(required=False, default=False)
    confirmed = serializers.BooleanField(required=False, default=False)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=200)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        # finalize is honored only if confirmed=True; view handles that logic
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> Conversation:
        request = self.context.get("request") if hasattr(self, "context") else None
        session_id = (validated_data.get("session_id") or "").strip()
        provided_id = validated_data.get("conversation_id")
        user_text = (validated_data.get("user_text") or "")
        ai_text = (validated_data.get("ai_text") or "")
        user_name = (validated_data.get("user_name") or "").strip()

        if not user_name and request and getattr(request, "user", None) and request.user.is_authenticated:
            user_name = request.user.username

        conversation_text = build_conversation_text(user_text, ai_text)
        now = timezone.now()

        convo: Conversation | None = None
        if provided_id:
            try:
                convo = Conversation.objects.get(pk=int(provided_id))
            except Exception:
                convo = None
        if not convo and session_id:
            cutoff = timezone.now() - timedelta(minutes=45)
            convo = (
                Conversation.objects
                .filter(session_id=session_id, last_activity__gte=cutoff)
                .order_by("-last_activity", "-id")
                .first()
            )

        created = False
        if not convo:
            convo = Conversation(
                session_id=session_id,
                user_name=user_name,
                conversation=conversation_text,
                last_activity=now,
            )
            convo.save()
            created = True

        if not created:
            if conversation_text:
                convo.conversation = conversation_text
            if user_name and user_name != (convo.user_name or ""):
                convo.user_name = user_name
            convo.last_activity = now
            convo.save(update_fields=["conversation", "last_activity", "user_name", "updated_at"])

        return convo

class ConversationResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    id = serializers.IntegerField()
    session_id = serializers.CharField(allow_blank=True)
    user_name = serializers.CharField(allow_blank=True, required=False)
    created_at = serializers.CharField()
    updated_at = serializers.CharField()
    last_activity = serializers.CharField()
    finalized = serializers.BooleanField()
    summary = serializers.CharField(allow_blank=True, required=False)
    satisfaction_rating = serializers.IntegerField(allow_null=True, required=False)
    satisfaction_label = serializers.CharField(allow_blank=True, required=False)
    conversation_topic = serializers.CharField(allow_blank=True, required=False)
    analysis_timestamp = serializers.CharField(allow_null=True, required=False)