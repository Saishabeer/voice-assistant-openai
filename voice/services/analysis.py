# OpenAI-powered post-conversation analysis. Produces strict JSON (no manual heuristics).
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

import httpx
from django.conf import settings
from voice import constants as C  # centralized defaults and endpoints

def _get_api_key() -> str:
    key = getattr(settings, "OPENAI_API_KEY", None) or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not configured")
    return key


def _build_json_schema() -> Dict[str, Any]:
    # Strict schema based on your specification (unchanged)
    return {
        "name": "summarize_conversation",
        "schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "A concise and clear summary of the entire conversation."},
                "satisfaction_level": {
                    "type": "object",
                    "description": "A structured satisfaction analysis based on tone, engagement, and sentiment.",
                    "properties": {
                        "rating": {"type": "integer", "enum": [1, 2, 3, 4, 5], "description": "1=Very Poor, 5=Excellent"},
                        "label": {"type": "string", "description": "Text label e.g., 'Excellent Service'"},
                    },
                    "required": ["rating", "label"],
                },
                "user_behavior": {"type": "string", "description": "Tone/behavior: curiosity, frustration, focus, etc."},
                "conversation_topic": {"type": "string", "description": "Main topic/category of the conversation."},
                "feedback_summary": {"type": "string", "description": "Reasoning behind the satisfaction level and sentiment."},
                "timestamp": {"type": "string", "description": "ISO 8601 UTC timestamp when the summary was generated."},
            },
            "required": [
                "summary",
                "satisfaction_level",
                "user_behavior",
                "conversation_topic",
                "feedback_summary",
                "timestamp",
            ],
            "additionalProperties": False,
        },
        "strict": True,
    }


def _ensure_timestamp(obj: Dict[str, Any]) -> None:
    if not obj.get("timestamp"):
        obj["timestamp"] = datetime.now(timezone.utc).isoformat()


def _responses_request(api_key: str, model: str, transcript: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Attempt 1: Use OpenAI Responses API with json_schema (preferred).
    Returns (parsed_json, raw_api_response). Raises on any error.
    """
    system_prompt = (
        "You are a post-conversation analysis agent. "
        "Given the full chat transcript between the user and the assistant, "
        "produce ONLY a JSON object conforming to the provided JSON schema. "
        "Do not add extra commentary."
    )

    json_schema = _build_json_schema()
    url = C.get_responses_url()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "OpenAI-Beta": C.RESPONSES_BETA_HEADER,
    }
    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Transcript:\n{transcript}"},
        ],
        "response_format": {"type": "json_schema", "json_schema": json_schema},
    }

    with httpx.Client(timeout=60) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    # Extract JSON text from Responses API
    parsed_json_str = None
    try:
        outputs = data.get("output", [])
        if outputs and "content" in outputs[0] and outputs[0]["content"]:
            piece = outputs[0]["content"][0]
            parsed_json_str = piece.get("text")
    except Exception:
        parsed_json_str = None

    if not parsed_json_str:
        parsed_json_str = data.get("output_text")

    if not parsed_json_str:
        raise RuntimeError("Failed to extract JSON from OpenAI Responses result")

    parsed = json.loads(parsed_json_str)
    _ensure_timestamp(parsed)
    return parsed, data


def _chat_completions_fallback(api_key: str, model: str, transcript: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Attempt 2: Use Chat Completions with a strict instruction to output JSON only.
    Returns (parsed_json, raw_api_response). Raises on any error.
    """
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    system = "You produce strictly formatted JSON responses matching the required keys. No extra text."
    user = (
        "Given the transcript, produce a compact JSON object with keys:\n"
        "- summary (string)\n"
        "- satisfaction_level: { rating (1..5 integer), label (string) }\n"
        "- user_behavior (string)\n"
        "- conversation_topic (string)\n"
        "- feedback_summary (string)\n"
        "- timestamp (ISO 8601 UTC string)\n"
        "Return ONLY JSON without code fences or commentary.\n\n"
        f"Transcript:\n{transcript}"
    )
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
    }

    with httpx.Client(timeout=60) as client:
        resp = client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body)
        resp.raise_for_status()
        raw = resp.json()

    content = raw["choices"][0]["message"]["content"]
    parsed = json.loads(content) if content.strip().startswith("{") else json.loads(content[content.find("{"):content.rfind("}") + 1])
    _ensure_timestamp(parsed)
    return parsed, raw


def _local_fallback(transcript: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Attempt 3: Local, last-resort fallback so your pipeline always persists raw_json/raw_response.
    """
    summary = (transcript or "").strip()
    summary = summary[:200] + ("..." if len(summary) > 200 else "")
    parsed = {
        "summary": summary,
        "satisfaction_level": {"rating": 3, "label": "Neutral"},
        "user_behavior": "",
        "conversation_topic": "",
        "feedback_summary": "",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "analysis_engine": "local",
    }
    raw_payload = {
        "engine": "local",
        "note": "OpenAI unavailable or returned an error; using local fallback.",
        "transcript_len": len(transcript or ""),
    }
    return parsed, raw_payload


def analyze_conversation_via_openai(conversation_text: str, model: str | None = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Analyze conversation and ALWAYS return (parsed_json, raw_payload) without raising to the caller.
    Order of attempts:
      1) OpenAI Responses API with your json_schema (_build_json_schema).
      2) Chat Completions with a strict JSON instruction.
      3) Local fallback, guaranteeing raw_json/raw_response are populated.
    """
    transcript = (conversation_text or "").strip()
    api_key = (getattr(settings, "OPENAI_API_KEY", None) or os.environ.get("OPENAI_API_KEY", "")).strip()
    model = (model or C.DEFAULT_SUMMARY_MODEL).strip() or "gpt-4o-mini"

    if not transcript:
        # Empty transcript → short-circuit to local fallback
        return _local_fallback(transcript)

    if not api_key:
        # No key → local fallback
        return _local_fallback(transcript)

    # Attempt 1: Responses API
    try:
        return _responses_request(api_key, model, transcript)
    except Exception as e1:
        # Attempt 2: Chat Completions fallback
        try:
            parsed, raw = _chat_completions_fallback(api_key, model, transcript)
            # Mark engine so you know which path succeeded
            parsed["analysis_engine"] = f"openai:chat:{model}"
            return parsed, raw
        except Exception as e2:
            # Attempt 3: Local fallback with error details captured in raw payload
            parsed, raw = _local_fallback(transcript)
            raw.update({"errors": {"responses_api": str(e1), "chat_completions": str(e2)}})
            return parsed, raw