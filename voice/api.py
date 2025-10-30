from __future__ import annotations

from typing import List, Dict, Any
from datetime import timedelta as dt_timedelta

from django.http import JsonResponse, HttpRequest, Http404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import Conversation  # file://C:/Users/saish/Desktop/voice%20assist/voice/models.py#Conversation


def _derive_title_and_snippet(conversation_text: str, summary: str) -> Dict[str, str]:
    title = (summary or "").strip()
    text = (conversation_text or "").strip()
    if not title:
        first_line = ""
        for ln in text.splitlines():
            ln = ln.strip()
            if ln:
                first_line = ln
                break
        title = (first_line[:80] + ("…" if len(first_line) > 80 else "")) or "Untitled conversation"
    snippet_src = summary or text
    snippet = (snippet_src[:120] + ("…" if len(snippet_src) > 120 else "")) if snippet_src else ""
    return {"title": title, "snippet": snippet}


@require_GET
def conversations_json(request: HttpRequest) -> JsonResponse:
    """
    GET /conversations/?limit=20[&days=30][&session_id=...][&user_name=...]
    If user_name is omitted and the user is authenticated, default to request.user.username.
    """
    try:
        limit = max(1, min(100, int(request.GET.get("limit", "20"))))
    except ValueError:
        limit = 20
    try:
        days = max(1, min(365, int(request.GET.get("days", "30"))))
    except ValueError:
        days = 30

    session_id = (request.GET.get("session_id") or "").strip()
    user_name = (request.GET.get("user_name") or "").strip()

    # Default to the logged-in username for convenience
    if not user_name and getattr(request, "user", None) and request.user.is_authenticated:
        user_name = request.user.username

    since = timezone.now() - dt_timedelta(days=days)
    qs = Conversation.objects.filter(last_activity__gte=since).order_by("-last_activity", "-id")
    if session_id:
        qs = qs.filter(session_id=session_id)
    if user_name:
        qs = qs.filter(user_name=user_name)

    items: List[Dict[str, Any]] = []
    for convo in qs[:limit]:
        meta = _derive_title_and_snippet(convo.conversation or "", convo.summary or "")
        items.append({
            "id": convo.id,
            "title": meta["title"],
            "snippet": meta["snippet"],
            "last_activity": (convo.last_activity or convo.updated_at or convo.created_at).isoformat(),
            "session_id": convo.session_id or "",
            "user_name": convo.user_name or "",
        })
    return JsonResponse({"items": items}, status=200)


@require_GET
def conversation_detail_json(request: HttpRequest, pk: int) -> JsonResponse:
    """
    GET /conversations/<id>/
    """
    try:
        convo = Conversation.objects.get(pk=pk)
    except Conversation.DoesNotExist:
        raise Http404("Conversation not found")

    data = {
        "id": convo.id,
        "session_id": convo.session_id or "",
        "user_name": convo.user_name or "",
        "last_activity": (convo.last_activity or convo.updated_at or convo.created_at).isoformat(),
        "summary": convo.summary or "",
        "satisfaction_rating": convo.satisfaction_rating,
        "satisfaction_label": convo.satisfaction_label or "",
        "conversation": convo.conversation or "",
        "analysis_timestamp": convo.analysis_timestamp.isoformat() if convo.analysis_timestamp else None,
    }
    return JsonResponse(data, status=200)


@require_POST
def conversation_delete_json(request: HttpRequest, pk: int) -> JsonResponse:
    """
    POST /conversations/<id>/delete/
    Requires login. Allows deletion if the conversation belongs to the user (matches user_name),
    or the user is staff/superuser. If user_name is blank, allow staff/superuser only.
    """
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=401)

    try:
        convo = Conversation.objects.get(pk=pk)
    except Conversation.DoesNotExist:
        raise Http404("Conversation not found")

    owner = (convo.user_name or "").strip()
    if owner:
        if owner != user.username and not (user.is_staff or user.is_superuser):
            return JsonResponse({"error": "Forbidden"}, status=403)
    else:
        if not (user.is_staff or user.is_superuser):
            return JsonResponse({"error": "Forbidden"}, status=403)

    convo.delete()
    return JsonResponse({"status": "ok"}, status=200)