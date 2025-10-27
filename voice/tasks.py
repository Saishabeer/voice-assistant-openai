from __future__ import annotations

from typing import Any

import httpx
from celery import shared_task
from celery.utils.log import get_task_logger
from django.db import transaction
from django.utils import timezone

from .models import Conversation
from .services.analysis import analyze_conversation_via_openai

logger = get_task_logger(__name__)


@shared_task(
    bind=True,
    name="voice.analyze_and_store_conversation",
    autoretry_for=(httpx.HTTPError,),
    retry_backoff=2,
    retry_kwargs={"max_retries": 3},
)
def analyze_and_store_conversation(self, conversation_pk: int) -> int:
    """
    Single background step after a conversation ends:
    - Calls OpenAI once using your existing JSON schema (no changes to _build_json_schema).
    - Saves raw JSON to Conversation.raw_json and full API payload to Conversation.raw_response.
    - Updates derived fields (summary, satisfaction, etc.) from that JSON.
    """
    logger.info("Begin analysis for conversation_pk=%s", conversation_pk)

    # Lock the row for an atomic update during analysis persistence
    conv = Conversation.objects.select_for_update().get(pk=conversation_pk)
    transcript = conv.conversation or ""
    logger.info("Transcript length for pk=%s: %s chars", conversation_pk, len(transcript))

    parsed: dict[str, Any] | None = None
    raw_payload: dict[str, Any] | None = None

    try:
        # Uses your schema-driven Responses integration as-is
        parsed, raw_payload = analyze_conversation_via_openai(transcript)
        engine = (parsed or {}).get("analysis_engine") or "openai:responses"
        logger.info("Analysis completed for pk=%s using engine=%s", conversation_pk, engine)
    except Exception as e:
        # Ensure raw_response is always recorded even on failure
        logger.warning("Analysis exception for pk=%s: %s", conversation_pk, e)
        parsed = None
        raw_payload = {
            "engine": "openai_responses",
            "error": str(e),
            "note": "Analysis failed; raw_response recorded for debugging.",
        }

    with transaction.atomic():
        # Always persist the raw API payload for audit/debug
        if raw_payload:
            conv.raw_response = raw_payload

        # On success, store the parsed JSON and update derived fields
        if isinstance(parsed, dict):
            conv.raw_json = parsed
            conv.summary = parsed.get("summary", "") or conv.summary

            # satisfaction_level = {"rating": int (1-5), "label": str}
            sat = parsed.get("satisfaction_level") or {}
            if isinstance(sat, dict):
                rating = sat.get("rating")
                label = sat.get("label", "")
                conv.satisfaction_rating = rating if isinstance(rating, int) else conv.satisfaction_rating
                conv.satisfaction_label = label or conv.satisfaction_label

            conv.user_behavior = parsed.get("user_behavior", "") or conv.user_behavior
            conv.conversation_topic = parsed.get("conversation_topic", "") or conv.conversation_topic
            conv.feedback_summary = parsed.get("feedback_summary", "") or conv.feedback_summary
            conv.analysis_timestamp = timezone.now()

        conv.last_activity = timezone.now()
        conv.save()

    logger.info(
        "Stored conversation pk=%s summary_len=%s rating=%s label=%s",
        conv.pk,
        len(conv.summary or ""),
        conv.satisfaction_rating,
        conv.satisfaction_label,
    )
    return conv.pk