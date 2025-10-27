// Continue the conversation explicitly (mirror of finalize.js, but no finalize).
// Posts a snapshot and emits a convo:state event with state='active'.
async function continueConversation({ sessionId, userText = "", aiText = "", conversationId = null, reason = "continue" }) {
  const base = {
    session_id: sessionId || "",
    user_text: userText || "",
    ai_text: aiText || "",
    conversation_id: conversationId,
    finalize: false,
    confirmed: false,
  };

  try {
    const res = await fetch("/save-conversation/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(base),
      keepalive: true,
    });
    // Inform listeners that we're continuing
    try { window.dispatchEvent(new CustomEvent("convo:state", { detail: { state: "active" } })); } catch (_) {}
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Continue save failed: ${res.status} ${text}`);
    }
    return await res.json();
  } catch (e) {
    // Still emit state event so UI stays consistent
    try { window.dispatchEvent(new CustomEvent("convo:state", { detail: { state: "active" } })); } catch (_) {}
    return { status: "error", error: String(e) };
  }
}