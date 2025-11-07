# Views: start realtime session, save conversation, import conversation from JSON, and save analysis on finalize.
from __future__ import annotations

import json
import logging
import os
from datetime import timedelta, datetime
from datetime import timezone as dt_timezone

import httpx
from django.conf import settings
from django.contrib.auth import login as auth_login
from django.contrib.auth.forms import UserCreationForm
from django.http import (
    HttpRequest,
    HttpResponseBadRequest,
    HttpResponseServerError,
    JsonResponse,
    Http404,
)
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from . import constants as C
from .models import Conversation  # file://C:/Users/saish/Desktop/voice%20assist/voice/models.py#Conversation
from .services.analysis import analyze_conversation_via_openai  # file://C:/Users/saish/Desktop/voice%20assist/voice/services/analysis.py#analyze_conversation_via_openai
from .serializers import SaveConversationSerializer, ConversationResponseSerializer  # file://C:/Users/saish/Desktop/voice%20assist/voice/serializers.py#SaveConversationSerializer

logger = logging.getLogger(__name__)


def index(request: HttpRequest):
    return render(request, "voice/index.html")


def signup_view(request: HttpRequest):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            return redirect("index")
    else:
        form = UserCreationForm()
    return render(request, "registration/signup.html", {"form": form})


@require_GET
def realtime_session(request: HttpRequest):
    # Enforce authentication for realtime session API
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=401)
    api_key = getattr(settings, "OPENAI_API_KEY", None) or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not configured")
        return HttpResponseServerError("OPENAI_API_KEY not configured")

    model = os.environ.get("OPENAI_REALTIME_MODEL", C.DEFAULT_REALTIME_MODEL)
    voice = os.environ.get("OPENAI_REALTIME_VOICE", C.DEFAULT_VOICE)
    transcribe_model = os.environ.get("TRANSCRIBE_MODEL", C.DEFAULT_TRANSCRIBE_MODEL)

    instructions = f"{C.RISHI_SYSTEM_INSTRUCTION}\n\n{C.TOOL_DIRECTIVE}\n\nAlways respond only in English. Do not switch languages."

    tools = [
        {
            "type": "function",
            "name": "finalize_conversation",
            "description": "Persist final state when the user is ready to end the conversation. The client will end the call only when confirmed=true.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Why the session is finishing (e.g., 'purchase completed', 'user said bye')."},
                    "confirmed": {"type": "boolean", "description": "Set to true only if the user explicitly confirmed they want to end now."},
                },
                "required": ["reason", "confirmed"],
                "additionalProperties": False,
            },
        }
    ]

    payload = {
        "model": model,
        "modalities": C.DEFAULT_MODALITIES,
        "voice": voice,
        "instructions": instructions,
        "turn_detection": {"type": "server_vad", "silence_duration_ms": 800},
        "input_audio_transcription": {"model": transcribe_model},
        "tools": tools,
        "tool_choice": "auto",
    }

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "OpenAI-Beta": C.OPENAI_BETA_HEADER_VALUE,
        }
        url = C.get_realtime_session_url()
        with httpx.Client(timeout=20) as client:
            resp = client.post(url, headers=headers, json=payload)
        if resp.status_code != 200:
            logger.error("OpenAI session error (%s): %s", resp.status_code, resp.text)
            return HttpResponseServerError("Failed to create session")
        return JsonResponse(resp.json())
    except Exception:
        logger.exception("Session creation failed")
        return HttpResponseServerError("Session creation failed")


    


def _simple_local_analysis(text: str) -> dict:
    t = (text or "").strip()
    short = t[:200] + ("..." if len(t) > 200 else "")
    return {
        "summary": short,
        "satisfaction_level": {"rating": 3, "label": "Neutral"},
        "user_behavior": "",
        "conversation_topic": "",
        "feedback_summary": "",
        "timestamp": datetime.now(dt_timezone.utc).isoformat(),
        "analysis_engine": "local",
    }


def _sync_finalize_conversation(convo: Conversation) -> bool:
    try:
        parsed, raw_payload = analyze_conversation_via_openai(convo.conversation)
    except Exception as exc:
        logger.warning(
            "Sync analysis failed, using local fallback (convo_id=%s): %s",
            convo.id,
            exc,
        )
        parsed = _simple_local_analysis(convo.conversation)
        raw_payload = {
            "engine": "local",
            "error": str(exc),
            "note": "OpenAI request failed; using local fallback.",
        }

    ts_str = parsed.get("timestamp") or ""
    try:
        ts_dt = (
            datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if ts_str
            else datetime.now(dt_timezone.utc)
        )
    except Exception:
        ts_dt = datetime.now(dt_timezone.utc)

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

    try:
        convo.save(
            update_fields=[
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
            ]
        )
        logger.info("Sync finalize persisted analysis (convo_id=%s)", convo.id)
        return True
    except Exception:
        logger.exception(
            "Failed to persist sync analysis to DB (convo_id=%s)",
            convo.id,
        )
        return False


def _extract_from_uploaded(raw: dict) -> dict:
    candidates = [raw]
    for key in ("data", "result", "response", "analysis", "payload"):
        if isinstance(raw.get(key), dict):
            candidates.append(raw[key])

    def first(paths, default=None):
        for c in candidates:
            for path in paths:
                cur = c
                ok = True
                for k in path:
                    if isinstance(cur, dict) and k in cur:
                        cur = cur[k]
                    else:
                        ok = False
                        break
                if ok and cur not in (None, "", [], {}):
                    return cur
        return default

    def to_int(v):
        try:
            return int(v)
        except Exception:
            return None

    return {
        "summary": first([("summary",)], ""),
        "satisfaction_rating": to_int(first([("satisfaction_level", "rating"), ("satisfaction_rating",)], None)),
        "satisfaction_label": first([("satisfaction_level", "label"), ("satisfaction_label",)], "") or "",
        "user_behavior": first([("user_behavior",), ("analysis", "user_behavior")], "") or "",
        "conversation_topic": first([("conversation_topic",), ("topic",), ("topics", 0)], "") or "",
        "feedback_summary": first([("feedback_summary",), ("feedback", "summary")], "") or "",
        "timestamp": first([("timestamp",)], ""),
        "transcript": first([("conversation",), ("transcript",), ("text",)], "") or "",
    }


@csrf_exempt
@require_POST
def save_conversation(request: HttpRequest):
    """
    Upsert conversation row (single record per active session).
    If finalize=true AND confirmed=true, enqueue a Celery task to persist summary/satisfaction/etc.
    Also updates user_name if provided (or defaults to the logged-in user).
    Fallback: if Celery enqueue fails, compute synchronously and persist within the request.
    """
    # Enforce authentication for save API
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=401)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    in_ser = SaveConversationSerializer(data=payload, context={"request": request})
    if not in_ser.is_valid():
        return JsonResponse(in_ser.errors, status=400)

    data = in_ser.validated_data
    finalize = bool(data.get("finalize", False))
    confirmed = bool(data.get("confirmed", False))
    reason = (data.get("reason") or "").strip().lower()
    session_id = (data.get("session_id") or "").strip()
    provided_id = data.get("conversation_id")
    logger.info(
        "save_conversation: finalize=%s confirmed=%s reason=%s session_id=%s provided_id=%s",
        finalize, confirmed, reason, session_id, provided_id,
    )

    # Persist conversation via serializer.create()
    try:
        convo: Conversation = in_ser.save()
    except Exception:
        logger.exception("Failed to save conversation transcript")
        return HttpResponseServerError("Failed to save conversation")

    now = timezone.now()

    did_finalize = False

    # Robust finalize decision: if client asks to finalize and either confirmed=True
    # OR the reason strongly indicates end-of-session (manual stop/close/channel closed),
    # then proceed with finalize to avoid losing analysis on edge disconnects.
    end_markers = ("manual_stop_finalize", "manual_stop", "channel_closed", "close", "end")
    finalize_requested = finalize and (confirmed or any(m in reason for m in end_markers))

    if finalize_requested:
        force_sync = getattr(settings, "VOICE_SYNC_FINALIZE", True)
        use_celery = getattr(settings, "VOICE_USE_CELERY_FINALIZE", False)

        sync_done = False
        if force_sync:
            sync_done = _sync_finalize_conversation(convo)
            did_finalize = did_finalize or sync_done

        if use_celery and not sync_done:
            try:
                from .tasks import analyze_and_store_conversation
                res = analyze_and_store_conversation.delay(convo.id)
                try:
                    task_id = getattr(res, "id", None) or getattr(res, "task_id", None)
                except Exception:
                    task_id = None
                logger.info("Queued Celery task for finalize (convo_id=%s, task_id=%s)", convo.id, task_id)
            except Exception as e:
                logger.warning(
                    "Celery enqueue failed, running sync finalize (convo_id=%s): %s",
                    convo.id,
                    e,
                )
                if not did_finalize:
                    did_finalize = _sync_finalize_conversation(convo)

    resp_payload = {
        "status": "ok",
        "id": convo.id,
        "session_id": convo.session_id,
        "user_name": convo.user_name,
        "created_at": (convo.created_at or now).isoformat(),
        "updated_at": (convo.updated_at or now).isoformat(),
        "last_activity": (convo.last_activity or now).isoformat(),
        "finalized": did_finalize,
        "summary": convo.summary,
        "satisfaction_rating": convo.satisfaction_rating,
        "satisfaction_label": convo.satisfaction_label,
        "conversation_topic": convo.conversation_topic,
        "analysis_timestamp": convo.analysis_timestamp.isoformat() if convo.analysis_timestamp else None,
    }
    out_ser = ConversationResponseSerializer(resp_payload)
    return JsonResponse(out_ser.data, status=200)

def _derive_title_and_snippet(conversation_text: str, summary: str) -> dict:
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
@login_required
def conversations_json(request: HttpRequest) -> JsonResponse:
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

    if not user_name and getattr(request, "user", None) and request.user.is_authenticated:
        user_name = request.user.username

    since = timezone.now() - timedelta(days=days)
    qs = Conversation.objects.filter(last_activity__gte=since).order_by("-last_activity", "-id")
    if session_id:
        qs = qs.filter(session_id=session_id)
    if user_name:
        qs = qs.filter(user_name=user_name)

    items = []
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
@login_required
def conversation_detail_json(request: HttpRequest, pk: int) -> JsonResponse:
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
@login_required
def conversation_delete_json(request: HttpRequest, pk: int) -> JsonResponse:
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
