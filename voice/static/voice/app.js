
// Strict confirmation FSM with turn-index guard + explicit conversation state,
// NO-lockout window after a negative reply, robust confirmation-question detection,
// recent stop-intent tracking, proactive "continue" instruction on invalid finalize,
// and a safe finalize fallback.
// Accepts short YES tokens: 's', 'y', 'ok', 'okay' but only as (nearly) standalone replies.

(function () {
  'use strict';

  function boot() {
    var startBtn = document.getElementById("startBtn");
    var stopBtn  = document.getElementById("stopBtn");
    var statusEl = document.getElementById("status");
    var userEl   = document.getElementById("userTranscript");
    var aiEl     = document.getElementById("aiTranscript");
    var aiAudio  = document.getElementById("aiAudio");

    if (!startBtn || !stopBtn || !statusEl || !userEl || !aiEl || !aiAudio) {
      console.warn("[app.js] Realtime UI elements not found; check template IDs.");
      return;
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      statusEl.textContent = "Microphone API not available in this browser.";
      startBtn.disabled = true; return;
    }
    if (typeof RTCPeerConnection !== "function") {
      statusEl.textContent = "WebRTC not available in this browser.";
      startBtn.disabled = true; return;
    }

    var pc = null, micStream = null, eventsDC = null;
    var sessionId = "", conversationId = null;
    var AUTO_SAVE_IDLE_MS = 8000;
    var MIN_SAVE_INTERVAL_MS = 10000;
    var autosaveTimer = null, dirty = false, lastSnapshot = "", lastSaveAt = 0, saving = false;

    var finalized = false;
    var greetingPending = false, greetTimeoutHandle = null;
    var greeted = false; // ensure AI initiates only once per session

    // Force stop shortly after sending the closing message (don’t rely on model events)
    var STOP_AFTER_CLOSE_MS = 1200;

    // Conversation state and events
    var convoState = "active"; // 'active' | 'pending_confirm' | 'ended'
    function setConvoState(newState) {
      if (convoState === newState) return;
      convoState = newState;
      try { window.dispatchEvent(new CustomEvent("convo:state", { detail: { state: newState } })); } catch (_e) {}
      if (newState === "pending_confirm") setStatus("Awaiting user confirmation to end…");
      else if (newState === "ended") setStatus("Conversation ended.");
      else setStatus("Continuing…");
    }
    window.getConvoState = function () { return convoState; };

    // Confirmation FSM
    var confirmationRequested = false;
    var confirmationAskedAt = 0;
    var confirmationGranted = false;
    var CONFIRM_WINDOW_MS = 90 * 1000;
    var currentUserTurn = "";

    // Turn-index guard
    var turnIndex = 0;                  // increments on assistant/user turn completions
    var confirmAskedTurnIndex = -1;     // set at assistant confirmation ask
    var lastUserTurnIndex = -1;         // set at user turn completion

    // Finalize fallback (when YES but model doesn't call the tool)
    var finalizeFallbackTimer = null;
    var FINALIZE_FALLBACK_MS = 1800;    // small wait to let tool call arrive first

    // NO lockout: ignore finalize calls for a short period after a negative reply
    var rejectFinalizeUntilTs = 0;      // epoch ms; if Date.now() < this, ignore finalize

    // Recent stop-intent tracking
    var lastStopIntentTs = 0;
    var STOP_INTENT_WINDOW_MS = 20000;  // 20s window to allow YES even if exact confirm-question wasn’t detected

    var fnArgBuffers = Object.create(null);

    // Tokens (lowercase). We'll evaluate with helpers to avoid false positives.
    var YES_LONG_TOKENS = [
      "yes","yeah","yep","yup","confirm","please end","go ahead","that's fine","that is fine",
      "end now","sure","okay end","ok end","please close","end it","yes please","affirmative","indeed"
    ];
    var NO_TOKENS  = [
      "no","not yet","wait","hold on","continue","don't","do not","nope","cancel","not now","stop asking",
      "no thanks","no thank you","nah","never","please continue","keep going","no i don't","no i do not",
      "لا","нет","nein","இல்லை","లేదు","नहीं","não","non","ne","nej","nai"
    ];
    var SHORT_YES = ["s","y","ok","okay"];

    // Stop-intent tokens (user side)
    var STOP_TOKENS = [
      "stop","end","finish","we are done","we’re done","that's all","thats all","end the conversation","stop this","stop now","bye","goodbye"
    ];

    function setStatus(t){ statusEl.textContent = t; }
    function clearEl(el){ el.textContent=""; el.classList.remove("muted"); }
    function append(el, t){ el.textContent += t; el.scrollTop = el.scrollHeight; }
    function appendLine(el, t){ append(el, (t||"") + "\n"); }
    function currentSnapshot(){ return (userEl.textContent||"") + "\n----\n" + (aiEl.textContent||""); }

    function markDirty(){ if (!finalized) { dirty = true; scheduleAutoSave(); } }
    function scheduleAutoSave(delayMs){
      var wait = (typeof delayMs === "number") ? delayMs : AUTO_SAVE_IDLE_MS;
      if (autosaveTimer) clearTimeout(autosaveTimer);
      autosaveTimer = setTimeout(function(){ tryAutoSave("idle"); }, wait);
    }

    function sendClosingMessage(_reason) {
      if (!eventsDC || eventsDC.readyState !== "open") return false;
      var text = "Thank you for your patience and for using our service. Have a great day!";
      try {
        eventsDC.send(JSON.stringify({ type: "response.create", response: { instructions: text } }));
        return true;
      } catch (_e) { return false; }
    }
    function sendContinueInstruction() {
      if (!eventsDC || eventsDC.readyState !== "open") return;
      var text = "The user did not confirm ending. Continue assisting. Do NOT call finalize_conversation again unless the user explicitly confirms in their next turn. Always respond only in English.";
      try { eventsDC.send(JSON.stringify({ type: "response.create", response: { instructions: text } })); } catch (_e) {}
    }
    function forceStopSoon(){ setTimeout(function(){ stop({ skipSave: true }); }, STOP_AFTER_CLOSE_MS); }

    function cancelFinalizeFallback() {
      if (finalizeFallbackTimer) { clearTimeout(finalizeFallbackTimer); finalizeFallbackTimer = null; }
    }

    // Normalize and helpers for YES/NO detection
    function normalizeLetters(s) { return (s || "").toLowerCase().replace(/[^\p{L}]+/gu, " ").trim(); }

    function attachEventChannel(dc){
      if (!dc) return;
      eventsDC = dc;
      eventsDC.onopen = function(){
        setStatus("Connected.");
        // Proactively have the AI speak first once the data channel is open
        if (!greeted) {
          greeted = true;
          try {
            eventsDC.send(JSON.stringify({
              type: "response.create",
              response: {
                instructions: "Start with a brief, friendly greeting and ask how you can help the user. Keep it concise. Respond only in English and do not switch languages."
              }
            }));
          } catch (_e) {}
        }
      };
      eventsDC.onclose = async function(){ setStatus("Events channel closed."); await tryAutoSave("channel_closed"); };
      eventsDC.onmessage = function(ev){
        var evt;
        try { evt = JSON.parse(ev.data); } catch (_e) { return; }
        handleRealtimeEvent(evt);
      };
    }
    function isNegativeTurn(text) {
      var lc = (text || "").toLowerCase();
      return NO_TOKENS.some(function(tok){ return lc.indexOf(tok) !== -1; });
    }
    function isAffirmativeTurn(text) {
      var raw = text || "";
      var lc = raw.toLowerCase().trim();
      if (isNegativeTurn(lc)) return false;
      var lettersOnly = normalizeLetters(lc).replace(/\s+/g, "");
      if (lettersOnly.length <= 4 && SHORT_YES.indexOf(lettersOnly) !== -1) return true;
      return YES_LONG_TOKENS.some(function(tok){
        var re = new RegExp("(?:^|\\b)" + tok.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "(?:\\b|$)");
        return re.test(lc);
      });
    }
    function isStopIntent(text) {
      var lc = (text || "").toLowerCase();
      return STOP_TOKENS.some(function(tok){ return lc.indexOf(tok) !== -1; });
    }

    // Allow finalize if either:
    // A) Classic: assistant asked earlier + user YES in next turn within window
    // B) Fallback: recent user stop intent within window + explicit YES (no lockout)
    function hasFinalizePermission() {
      var now = Date.now();
      var classic = confirmationRequested && (now - confirmationAskedAt) <= CONFIRM_WINDOW_MS && (lastUserTurnIndex > confirmAskedTurnIndex) && confirmationGranted;
      var recentStop = (now - lastStopIntentTs) <= STOP_INTENT_WINDOW_MS;
      var fallback = recentStop && confirmationGranted && (now >= rejectFinalizeUntilTs);
      return classic || fallback;
    }

    // Client-driven finalize (fallback) — used when YES detected but no tool call arrives soon
    async function finalizeClientSide(reason) {
      if (!hasFinalizePermission()) {
        setConvoState("active");
        setStatus("Continuing (fallback blocked: no valid confirmation).");
        return;
      }

      setStatus("Finalizing…");
      finalized = true;
      var server = await saveConversation({ autosave: true, reason: reason || "user confirmed end", finalize: true, confirmed: true, close: true });
      var ok = !!(server && server.ok);
      if (!ok) {
        finalized = false;
        setConvoState("active");
        setStatus("Continuing (server did not finalize).");
        sendContinueInstruction();
        return;
      }

      setConvoState("ended");
      var sent = sendClosingMessage(reason || "user confirmed end");
      forceStopSoon();
      if (!sent) stop({ skipSave: true });
    }

    // Broadened: detect a variety of confirmation questions
    function maybeMarkConfirmationRequested(text) {
      if (!text) return;
      var lc = text.toLowerCase();
      if (lc.includes("are you sure") && (lc.includes("end") || lc.includes("finish") || lc.includes("close")) &&
          (lc.includes("conversation") || lc.includes("session") || lc.includes("call"))) {
        confirmationRequested = true;
        confirmationGranted = false;
        confirmationAskedAt = Date.now();
        confirmAskedTurnIndex = turnIndex; // assistant turn index
        setConvoState("pending_confirm");
      }
    }

    function maybeEvaluateUserConfirmation(turnText) {
      if (!turnText) return;

      // Track stop intent on every user turn
      if (isStopIntent(turnText)) {
        lastStopIntentTs = Date.now();
      }

      if (!confirmationRequested && !isStopIntent(turnText)) {
        // No confirmation context and no new stop intent → nothing to evaluate
        return;
      }

      if (isNegativeTurn(turnText)) {
        confirmationGranted = false;
        confirmationRequested = false; // reset; keep session open
        cancelFinalizeFallback();
        // Set a short NO-lockout window to ignore any finalize tool calls that might follow
        rejectFinalizeUntilTs = Date.now() + 6000; // 6 seconds lockout
        setConvoState("active");
        setStatus("Continuing (user declined to end).");
        sendContinueInstruction();
        return;
      }
      if (isAffirmativeTurn(turnText)) {
        confirmationGranted = true;
        setStatus("User confirmed to end.");
        cancelFinalizeFallback();
        // Arm fallback; will check hasFinalizePermission at fire time
        finalizeFallbackTimer = setTimeout(function () { finalizeClientSide("user confirmed end (fallback)"); }, FINALIZE_FALLBACK_MS);
        return;
      }
      // unclear → keep waiting (within window)
    }

    function handleFunctionCallEvent(evt) {
      var call = (evt && (evt.function_call || evt.tool_call)) || {};
      var id = call.id || (evt && evt.id) || "default";
      var name = call.name || (evt && evt.name) || "";

      if (evt && (evt.type === "response.function_call.arguments.delta" || evt.type === "response.tool_call.delta")) {
        var delta = evt.delta || evt.arguments_delta || "";
        if (!fnArgBuffers[id]) fnArgBuffers[id] = "";
        if (typeof delta === "string") fnArgBuffers[id] += delta;
        return;
      }

      if (evt && (evt.type === "response.function_call.arguments.done" || evt.type === "response.tool_call.completed")) {
        var buf = fnArgBuffers[id] || ""; delete fnArgBuffers[id];
        var args = {};
        try {
          var s = buf.indexOf("{"), e = buf.lastIndexOf("}");
          var jsonStr = (s !== -1 && e > s) ? buf.slice(s, e+1) : buf;
          args = JSON.parse(jsonStr);
        } catch (_e) {}
        var fnName = name || (evt && evt.name) || (call && call.name) || "";

        if (fnName === "finalize_conversation") {
          var reason = (args && typeof args.reason === "string" && args.reason) ? args.reason : "user ended";
          var confirmed = !!(args && args.confirmed === true);

          // Enforce NO-lockout: ignore finalize during the lockout window
          if (Date.now() < rejectFinalizeUntilTs) {
            setConvoState("active");
            setStatus("Continuing (finalize ignored during NO lockout).");
            sendContinueInstruction();
            return;
          }

          if (!(confirmed && hasFinalizePermission())) {
            setConvoState("active");
            setStatus("Continuing (no valid confirmation to end).");
            sendContinueInstruction();
            return;
          }

          // Valid tool finalize → cancel fallback
          cancelFinalizeFallback();

          (async function () {
            setStatus("Finalizing…");
            finalized = true;

            var server = await saveConversation({ autosave: true, reason: reason, finalize: true, confirmed: true, close: true });
            var ok = !!(server && server.ok);
            if (!ok) {
              finalized = false;
              setConvoState("active");
              setStatus("Continuing (server did not finalize).");
              sendContinueInstruction();
              return;
            }

            setConvoState("ended");
            var sent = sendClosingMessage(reason);
            forceStopSoon();
            if (!sent) stop({ skipSave: true });
          })();
        }
        return;
      }
    }

    function handleRealtimeEvent(evt){
      var t = (evt && evt.type) || "";

      if (t.indexOf("response.function_call") === 0 || t.indexOf("response.tool_call") === 0) {
        handleFunctionCallEvent(evt);
        return;
      }

      // Secondary safety (primary stop is forced shortly after closing message)
      if (greetingPending && (t === "response.completed" || t === "response.output_text.done")) {
        greetingPending = false;
        if (greetTimeoutHandle) { clearTimeout(greetTimeoutHandle); greetTimeoutHandle = null; }
        stop({ skipSave: true });
        return;
      }

      // User live transcription
      if (t.indexOf("transcription.delta") !== -1) {
        var textU = extractText(evt);
        if (textU) { append(userEl, textU); currentUserTurn += textU; }
        markDirty();
        return;
      }
      if (t.indexOf("transcription.completed") !== -1) {
        appendLine(userEl, "");
        turnIndex += 1;              // completed user turn
        lastUserTurnIndex = turnIndex;
        maybeEvaluateUserConfirmation(currentUserTurn);
        currentUserTurn = "";
        scheduleAutoSave(3000);
        return;
      }

      // Assistant text
      if (t === "response.output_text.delta" || (t.indexOf("response.") === 0 && t.indexOf(".delta") === t.length - 6)) {
        var textA = extractText(evt);
        if (textA) { append(aiEl, textA); maybeMarkConfirmationRequested(textA); }
        markDirty();
        return;
      }
      if (t === "response.output_text.done" || t === "response.completed") {
        appendLine(aiEl, "");
        turnIndex += 1;              // completed assistant turn
        scheduleAutoSave(3000);
        return;
      }
    }

    function extractText(evt){
      if (!evt || typeof evt !== "object") return null;
      if (typeof evt.delta === "string") return evt.delta;
      if (evt.delta && typeof evt.delta.text === "string") return evt.delta.text;
      if (typeof evt.text === "string") return evt.text;
      if (typeof evt.transcript === "string") return evt.transcript;
      if (typeof evt.message === "string") return evt.message;
      if (evt.output_text && Array.isArray(evt.output_text)) return evt.output_text.join("");
      return null;
    }

    async function start(){
      startBtn.disabled = true; stopBtn.disabled = false;
      setStatus("Requesting microphone...");
      clearEl(userEl); clearEl(aiEl);
      if (autosaveTimer) clearTimeout(autosaveTimer);
      autosaveTimer = null; dirty = false; lastSnapshot = ""; lastSaveAt = 0; finalized = false;
      conversationId = null; greetingPending = false; if (greetTimeoutHandle) { clearTimeout(greetTimeoutHandle); greetTimeoutHandle = null; }
      greeted = false; // reset proactive greeting for a brand new session
      setConvoState("active");

      try { micStream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
      catch (_e) { setStatus("Microphone access denied."); startBtn.disabled=false; stopBtn.disabled=true; return; }

      setStatus("Creating session...");
      var session;
      try {
        var r = await fetch("/session/");
        if (!r.ok) throw new Error(await r.text());
        session = await r.json();
        sessionId = (session && session.id) || "";
        if (!(session && session.client_secret && session.client_secret.value)) throw new Error("Invalid session payload");
      } catch (_e) {
        // Allow offline finalize path even if session creation fails
        setStatus("Failed to create session. You can still click Stop to finalize and save.");
        startBtn.disabled = false;
        stopBtn.disabled = false;
        return;
      }

      var ephemeralKey = session.client_secret.value;
      var model = session.model || "gpt-4o-realtime-preview";

      setStatus("Starting WebRTC...");
      pc = new RTCPeerConnection({ iceServers: [{ urls: ["stun:stun.l.google.com:19302"] }] });
      pc.onconnectionstatechange = async function () { var st = pc.connectionState; if (st === "disconnected" || st === "failed" || st === "closed") await tryAutoSave("connection_" + st); };
      pc.ondatachannel = function (event) { if (event && event.channel && event.channel.label === "oai-events") attachEventChannel(event.channel); };
      var proactiveDC = pc.createDataChannel("oai-events"); attachEventChannel(proactiveDC);
      pc.ontrack = function (event) { var s = event && event.streams && event.streams[0]; if (s) aiAudio.srcObject = s; };

      if (micStream && micStream.getTracks) micStream.getTracks().forEach(function (track) { try { pc.addTrack(track, micStream); } catch (_e) {} });
      try { pc.addTransceiver("audio", { direction: "recvonly" }); } catch (_e) {}

      var offer = await pc.createOffer(); await pc.setLocalDescription(offer);

      var answerSdp = "";
      try {
        var sdpResponse = await fetch("https://api.openai.com/v1/realtime?model=" + encodeURIComponent(model), {
          method: "POST",
          headers: {
            "Authorization": "Bearer " + ephemeralKey,
            "Content-Type": "application/sdp",
            "OpenAI-Beta": "realtime=v1",
          },
          body: offer.sdp,
        });
        if (!sdpResponse.ok) throw new Error(await sdpResponse.text());
        answerSdp = await sdpResponse.text();
      } catch (_e) { setStatus("OpenAI SDP exchange failed."); await stop(); return; }
      await pc.setRemoteDescription({ type: "answer", sdp: answerSdp });
      setStatus("Live. Speak to your mic.");
    }

    // Save to backend → returns { ok: boolean, data: object | null }
    async function saveConversation(options){
      options = options || {};
      var user_text = userEl.textContent || "";
      var ai_text = aiEl.textContent || "";
      var payload = {
        session_id: sessionId || "",
        user_text: user_text,
        ai_text: aiTextSanitized(ai_text),
        autosave: !!options.autosave,
        reason: options.reason || (options.autosave ? "autosave" : "manual"),
        close: !!options.close,
        finalize: !!options.finalize,
        confirmed: !!options.confirmed,
      };
      if (conversationId != null) payload.conversation_id = conversationId;

      var snap = currentSnapshot();
      if (!snap.trim()) return { ok: true, data: null }; // nothing to save is not an error
      var isFinalize = !!options.finalize;
      // Do not block finalize even if another save is in progress
      if (saving && !isFinalize) return { ok: false, data: null };
      var nowTs = Date.now();
      // Never throttle finalize requests by the autosave interval
      if (!isFinalize && options.autosave && (nowTs - lastSaveAt < MIN_SAVE_INTERVAL_MS)) return { ok: true, data: null };

      saving = true;
      try {
        var res = await fetch("/save-conversation/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          keepalive: true,
          body: JSON.stringify(payload),
        });
        var js = null; try { js = await res.json(); } catch (_e) {}
        if (res.ok) {
          if (js && typeof js.id === "number") conversationId = js.id;
          lastSnapshot = snap; lastSaveAt = Date.now(); dirty = false;
        }
        return { ok: res.ok, data: js };
      } catch (_e) {
        return { ok: false, data: null };
      } finally { saving = false; }
    }

    // sanitize AI text if needed (placeholder hook; keeps content as-is)
    function aiTextSanitized(t) { return t || ""; }

    async function tryAutoSave(reason){
      if (!dirty) return;
      await saveConversation({ autosave: true, reason: reason || "autosave", finalize: false, confirmed: false, close: false });
    }

    async function stop(options){
      options = options || {};
      var skipSave = !!options.skipSave;
      stopBtn.disabled = true; startBtn.disabled = false; setStatus("Stopping...");
      if (!skipSave) {
        var baseSave = await saveConversation({ autosave: true, reason: "manual_stop", finalize: false, confirmed: false, close: false });
        if (!finalized && baseSave && baseSave.ok) {
          var forcedFinalize = await saveConversation({
            autosave: true,
            reason: "manual_stop_finalize",
            finalize: true,
            confirmed: true,
            close: true,
          });
          if (forcedFinalize && forcedFinalize.ok) {
            finalized = true;
            setConvoState("ended");
          }
        }
      }
      try { if (eventsDC) eventsDC.close(); } catch (_e) {}
      try {
        if (pc) {
          try { pc.getSenders().forEach(function (s){ try { s.track && s.track.stop(); } catch (_e) {} }); } catch (_e) {}
          try { pc.getReceivers().forEach(function (r){ try { r.track && r.track.stop(); } catch (_e) {} }); } catch (_e) {}
          pc.close();
        }
      } catch (_e) {}
      try { if (micStream && micStream.getTracks) { micStream.getTracks().forEach(function (t){ try { t.stop(); } catch (_e) {} }); micStream = null; } } catch (_e) {}
      try { if (aiAudio) aiAudio.srcObject = null; } catch (_e) {}
      if (autosaveTimer) { clearTimeout(autosaveTimer); autosaveTimer = null; }
      if (greetTimeoutHandle) { clearTimeout(greetTimeoutHandle); greetTimeoutHandle = null; }
      cancelFinalizeFallback();
      rejectFinalizeUntilTs = 0;
      lastStopIntentTs = 0;
      eventsDC = null; pc = null; setStatus("Idle");
    }

    startBtn.addEventListener("click", start);
    stopBtn.addEventListener("click", function(){ stop(); });

    window.addEventListener("beforeunload", function () {
      try {
        var data = {
          session_id: sessionId || "",
          user_text: userEl.textContent || "",
          ai_text: aiEl.textContent || "",
          autosave: true,
          reason: "beforeunload",
          close: false,
          finalize: false,
          confirmed: false,
        };
        if (conversationId != null) data.conversation_id = conversationId;
        if (navigator.sendBeacon) {
          var blob = new Blob([JSON.stringify(data)], { type: "application/json" });
          navigator.sendBeacon("/save-conversation/", blob);
        }
      } catch (_e) {}
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();