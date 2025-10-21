# OpenAI-powered post-conversation analysis. Produces strict JSON (no manual heuristics).
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

import httpx
from django.conf import settings
from voice.constants import get_responses_url  # reuse endpoint from constants

# Default model can be overridden via env
DEFAULT_SUMMARY_MODEL = os.environ.get("OPENAI_SUMMARY_MODEL", "gpt-4o-mini")


def _get_api_key() -> str:
    key = getattr(settings, "OPENAI_API_KEY", None) or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not configured")
    return key


def _build_json_schema() -> Dict[str, Any]:
    # Strict schema based on your specification
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


def analyze_conversation_via_openai(conversation_text: str, model: str | None = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Calls OpenAI Responses API with a strict json_schema to get structured analysis.
    Returns (parsed_json, raw_api_response) as Python dicts.
    No manual heuristics are applied to derive satisfaction/behavior.
    """
    if not conversation_text or not conversation_text.strip():
        raise ValueError("Empty conversation text provided for analysis")

    api_key = _get_api_key()
    model = model or DEFAULT_SUMMARY_MODEL

    system_prompt = (
        "You are a post-conversation analysis agent. "
        "Given the full chat transcript between the user and the assistant, "
        "produce ONLY a JSON object conforming to the provided JSON schema. "
        "Do not add extra commentary."
    )

    json_schema = _build_json_schema()

    url = get_responses_url()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        # No Beta header needed for Responses API; keep it minimal to avoid 4xx surprises.
    }
    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Transcript:\n{conversation_text}"},
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
        raise RuntimeError("Failed to extract JSON from OpenAI response")

    try:
        parsed = json.loads(parsed_json_str)
    except Exception as ex:
        raise RuntimeError(f"Failed to parse JSON from OpenAI response: {ex}")

    if not parsed.get("timestamp"):
        parsed["timestamp"] = datetime.now(timezone.utc).isoformat()

    return parsed, data