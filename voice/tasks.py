from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from django.db import transaction
from celery import shared_task

from .models import Conversation  # file://C:/Users/saish/Desktop/voice%20assist/voice/models.py#Conversation
from .services.analysis import analyze_conversation_via_openai  # file://C:/Users/saish/Desktop/voice%20assist/voice/services/analysis.py#analyze_conversation_via_openai

logger = logging.getLogger(__name__)


def _simple_local_analysis(text: str) -> dict[str, Any]:
    t = (text or "").strip()
    short = t[:200] + ("..." if len(t) > 200 else "")
    return {
        "summary": short,
        "satisfaction_level": {"rating": 3, "label": "Neutral"},
        "user_behavior": "",
        "conversation_topic": "",
        "feedback_summary": "",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "analysis_engine": "local",
    }


@shared_task(bind=True, name="voice.analyze_and_store_conversation", autoretry_for=(Exception,), retry_backoff=2, retry_kwargs={"max_retries": 3})
def analyze_and_store_conversation(self, conversation_pk: int) -> int:
    """
    Celery task: compute summary/satisfaction for a Conversation and persist it.
    Returns the conversation primary key on success.
    """
    convo = Conversation.objects.get(pk=conversation_pk)
    transcript = convo.conversation or ""

    try:
        parsed, raw_payload = analyze_conversation_via_openai(transcript)
        engine = parsed.get("analysis_engine", "openai")
        logger.info("Celery analysis engine=%s (convo_id=%s)", engine, convo.id)
    except Exception as e:
        logger.warning("Celery analysis failed, using local fallback (convo_id=%s): %s", convo.id, e)
        parsed = _simple_local_analysis(transcript)
        raw_payload = {"engine": "local", "error": str(e), "note": "OpenAI request failed; using local fallback."}

    ts_str = parsed.get("timestamp") or ""
    try:
        ts_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00")) if ts_str else datetime.now(timezone.utc)
    except Exception:
        ts_dt = datetime.now(timezone.utc)

    level = parsed.get("satisfaction_level") or {}
    rating = level.get("rating")
    label = level.get("label") or ""

    convo.summary = parsed.get("summary", "") or ""
    convo.satisfaction_rating = int(rating) if rating is not None else None
    convo.satisfaction_label = str(label)
    convo.user_behavior = parsed.get("user_behavior", "") or ""
    convo.conversation_topic = parsed.get("conversation_topic", "") or ""
    convo.feedback_summary = parsed.get("feedback_summary", "") or ""
    convo.analysis_timestamp = ts_dt
    convo.raw_json = parsed
    convo.raw_response = raw_payload

    with transaction.atomic():
        locked_convo = Conversation.objects.select_for_update().get(pk=conversation_pk)
        locked_convo.summary = convo.summary
        locked_convo.satisfaction_rating = convo.satisfaction_rating
        locked_convo.satisfaction_label = convo.satisfaction_label
        locked_convo.user_behavior = convo.user_behavior
        locked_convo.conversation_topic = convo.conversation_topic
        locked_convo.feedback_summary = convo.feedback_summary
        locked_convo.analysis_timestamp = convo.analysis_timestamp
        locked_convo.raw_json = convo.raw_json
        locked_convo.raw_response = convo.raw_response

        locked_convo.save(update_fields=[
            "summary",
            "satisfaction_rating",
            "satisfaction_label",
            "user_behavior",
            "conversation_topic",
            "feedback_summary",
            "analysis_timestamp",
            "raw_json",
            "raw_response",
            "updated_at",
        ])

    logger.info("Celery: saved summary/satisfaction (convo_id=%s)", convo.id)
    return convo.pk