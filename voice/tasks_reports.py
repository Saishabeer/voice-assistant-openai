from __future__ import annotations

import os
import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone


logger = logging.getLogger(__name__)


def _get_admin_recipients() -> list[str]:
    emails: list[str] = []
    # Prefer Django ADMINS if defined as [(name, email), ...]
    admins = getattr(settings, "ADMINS", None)
    if admins:
        try:
            emails = [e for _, e in admins if e]
        except Exception:
            pass
    if not emails:
        # Allow comma-separated env var ADMIN_EMAILS
        env_emails = os.environ.get("ADMIN_EMAILS", "").strip()
        if env_emails:
            emails = [s.strip() for s in env_emails.split(",") if s.strip()]
    return emails


def _label_to_bucket(label: str | None, rating: int | None) -> str:
    lb = (label or "").strip().lower()
    if lb in {"positive", "satisfied", "good", "great", "happy"}:
        return "satisfied"
    if lb in {"negative", "dissatisfied", "bad", "unhappy"}:
        return "dissatisfied"
    # Fall back to rating thresholds if label is not present/known
    if rating is not None:
        try:
            r = int(rating)
            if r >= 4:
                return "satisfied"
            if r <= 2:
                return "dissatisfied"
            return "neutral"
        except Exception:
            pass
    return "neutral"


@shared_task(name="voice.tasks_reports.send_admin_stats")
def send_admin_stats() -> dict:
    """
    Aggregates conversation stats for the last 30 minutes and emails the admins.
    Returns the counts for observability.
    """
    # Ensure Django apps are ready in the Celery worker process
    try:
        from django.apps import apps as dj_apps
        if not dj_apps.ready:
            import django as _django
            _django.setup()
        # Import ORM only after apps are ready
        from .models import Conversation  # local import
    except Exception as _e:
        logger.exception("Django not ready in worker; cannot compute stats: %s", _e)
        return {
            "created": 0,
            "analyzed": 0,
            "satisfied": 0,
            "dissatisfied": 0,
            "neutral": 0,
            "error": str(_e),
        }

    now = timezone.now()
    window_start = now - timedelta(minutes=0.005)

    # Chats created in the window
    created_count = Conversation.objects.filter(created_at__gte=window_start).count()

    # Analyzed in the window (finalized)
    analyzed_qs = Conversation.objects.filter(analysis_timestamp__gte=window_start)
    analyzed_count = analyzed_qs.count()

    satisfied = 0
    dissatisfied = 0
    neutral = 0
    try:
        for c in analyzed_qs.only(
            "satisfaction_label", "satisfaction_rating"
        ):
            bucket = _label_to_bucket(c.satisfaction_label, c.satisfaction_rating)
            if bucket == "satisfied":
                satisfied += 1
            elif bucket == "dissatisfied":
                dissatisfied += 1
            else:
                neutral += 1
    except Exception:
        logger.exception("Failed to bucket satisfaction stats")

    subject = "Voice Assistant: 30-min Stats"
    body = (
        f"Window: {window_start.isoformat()} → {now.isoformat()}\n"
        f"Chats created: {created_count}\n"
        f"Analyzed (finalized): {analyzed_count}\n"
        f"Satisfied: {satisfied}\n"
        f"Dissatisfied: {dissatisfied}\n"
        f"Neutral: {neutral}\n"
    )

    recipients = _get_admin_recipients()
    if not recipients:
        logger.warning("No admin recipients configured. Set settings.ADMINS or ADMIN_EMAILS env.")
    else:
        try:
            from_email = getattr(settings, "DEFAULT_FROM_EMAIL", os.environ.get("DEFAULT_FROM_EMAIL", "no-reply@example.com"))
            send_mail(subject, body, from_email, recipients, fail_silently=False)
            logger.info("Admin stats email sent to: %s", ", ".join(recipients))
        except Exception:
            logger.exception("Failed to send admin stats email")

    result = {
        "created": created_count,
        "analyzed": analyzed_count,
        "satisfied": satisfied,
        "dissatisfied": dissatisfied,
        "neutral": neutral,
        "window_start": window_start.isoformat(),
        "window_end": now.isoformat(),
    }
    logger.info("Admin stats computed: %s", result)
    return result
