# Reusable helpers to split and format transcripts into a readable single column.
from typing import List


def split_turns(text: str) -> List[str]:
    if not text:
        return []
    lines = [ln.strip() for ln in text.split("\n")]
    return [ln for ln in lines if ln]


def build_conversation_text(user_text: str, ai_text: str) -> str:
    u_turns = split_turns(user_text)
    a_turns = split_turns(ai_text)
    parts: List[str] = []
    n = max(len(u_turns), len(a_turns))
    for i in range(n):
        if i < len(u_turns):
            parts.append(f"User: {u_turns[i]}")
        if i < len(a_turns):
            parts.append(f"AI: {a_turns[i]}")
    return "\n".join(parts)