/**
 * Helper to finalize a conversation: triggers backend analysis and storage.
 * - If confirmed === true, finalizes.
 * - Else if confirmText is a short affirmative (e.g., 's', 'y', 'ok', 'okay', 'yes'), finalizes.
 * - Otherwise, performs a regular autosave (finalize=false).
 */
async function finalizeConversation({
  sessionId,
  userText = "",
  aiText = "",
  conversationId = null,
  reason = "",
  confirmed = false,
  confirmText = ""
}) {
  const base = {
    session_id: sessionId || "",
    user_text: userText || "",
    ai_text: aiText || "",
    conversation_id: conversationId,
  };

  // Derive confirmation from a short text when explicit flag is not provided
  if (!confirmed && confirmText) {
    const txt = String(confirmText).trim().toLowerCase();
    const YES_TOKENS = [
      "s", "y", "ok", "okay",
      "yes", "yeah", "yep", "yup", "sure", "confirm",
      "please end", "go ahead", "that's fine", "that is fine", "end now", "end it", "please close",
      "oui", "sí", "si", "haan", "affirmative", "indeed"
    ];
    confirmed = YES_TOKENS.some(tok => txt.includes(tok));
  }

  if (confirmed === true) {
    const res = await fetch("/save-conversation/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...base, finalize: true, confirmed: true, reason: reason || "end_confirmed" }),
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Finalize save failed: ${res.status} ${text}`);
    }
    // Expect server to include { finalized: true, id, ... }
    return await res.json();
  }

  // No confirmation → do not finalize; just autosave the transcript.
  const res = await fetch("/save-conversation/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...base, finalize: false, confirmed: false, reason: reason || "no_confirmation_autosave" }),
  });
  // Return a minimal, consistent shape
  if (res.ok) {
    let js = {};
    try { js = await res.json(); } catch (_) {}
    return { ok: true, ...js, finalized: false };
  }
  const text = await res.text();
  throw new Error(`Autosave (non-finalize) failed: ${res.status} ${text}`);
}

/**
 * Example integration points (adapt into your existing app.js):
 * - On function call: if name === "finalize_conversation", call finalizeConversation({ ..., confirmed: true })
 * - On end-of-conversation heuristic without explicit user confirmation: call finalizeConversation({ ..., confirmed: false }) to autosave only.
 */