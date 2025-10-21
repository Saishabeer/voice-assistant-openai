// Helper to finalize a conversation: triggers backend analysis and storage.
// Use this when the tool_call finalize_conversation is received or end-of-convo is detected.
async function finalizeConversation({ sessionId, userText = "", aiText = "", conversationId = null, reason = "" }) {
  const payload = {
    session_id: sessionId || "",
    user_text: userText || "",
    ai_text: aiText || "",
    conversation_id: conversationId,
    finalize: true,
    reason: reason || "end_detected",
  };
  const res = await fetch("/save-conversation/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Finalize save failed: ${res.status} ${text}`);
  }
  return res.json();
}

// Example integration points (adapt into your existing app.js):
// - On function call: if name === "finalize_conversation", call finalizeConversation(...)
// - On end-of-conversation heuristic: call finalizeConversation(...) before stopping the session.