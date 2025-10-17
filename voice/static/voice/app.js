
// Connectivity-hardened version: no optional chaining; binds after DOM ready.
// UI/logic unchanged: Start fetches /session/, begins WebRTC; Stop saves to /save-conversation/.
(function () {
  'use strict';

  function boot() {
    // DOM and state
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
    console.log("[app.js] UI loaded, binding handlers");

    // Feature detection
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      statusEl.textContent = "Microphone API not available in this browser.";
      console.error("getUserMedia not supported by this browser.");
      startBtn.disabled = true;
      return;
    }
    if (typeof RTCPeerConnection !== "function") {
      statusEl.textContent = "WebRTC not available in this browser.";
      console.error("RTCPeerConnection is not supported.");
      startBtn.disabled = true;
      return;
    }

    var pc = null, micStream = null, eventsDC = null;
    var sessionId = "", conversationId = null;
    var DEBUG_EVENTS = false;

    // Autosave and finalize controls
    var AUTO_SAVE_IDLE_MS = 8000;
    var MIN_SAVE_INTERVAL_MS = 10000;
    var autosaveTimer = null, dirty = false, lastSnapshot = "", lastSaveAt = 0, saving = false;
    var finalized = false;               // conversation closed on server
    var greetingPending = false;         // we sent/expect a closing message from the model
    var greetTimeoutHandle = null;       // fallback timer to stop if no response.completed arrives

    // Function-call buffering per-call id
    var fnArgBuffers = Object.create(null);

    // UI helpers
    function setStatus(t){ statusEl.textContent = t; }
    function clearEl(el){ el.textContent=""; el.classList.remove("muted"); }
    function append(el, t){ el.textContent += t; el.scrollTop = el.scrollHeight; }
    function appendLine(el, t){ append(el, (t||"") + "\n"); }
    function currentSnapshot(){ return (userEl.textContent||"") + "\n----\n" + (aiEl.textContent||""); }

    // Autosave helpers
    function markDirty(){ if (!finalized) { dirty = true; scheduleAutoSave(); } }
    function scheduleAutoSave(delayMs){
      var wait = (typeof delayMs === "number") ? delayMs : AUTO_SAVE_IDLE_MS;
      if (autosaveTimer) clearTimeout(autosaveTimer);
      autosaveTimer = setTimeout(function(){ tryAutoSave("idle"); }, wait);
    }

    // Send a short closing message via Realtime data channel; return true if sent
    function sendClosingMessage(_reason) {
      if (!eventsDC || eventsDC.readyState !== "open") return false;
      var text = "Thanks for spending your time with us. Your session is complete. Have a wonderful day!";
      try {
        eventsDC.send(JSON.stringify({
          type: "response.create",
          response: { instructions: text }
        }));
        return true;
      } catch (e) {
        console.warn("Failed to send closing message:", e);
        return false;
      }
    }

    // Prepare to stop after closing message plays (or timeout)
    function armGreetAndStopFallback() {
      if (greetTimeoutHandle) clearTimeout(greetTimeoutHandle);
      greetTimeoutHandle = setTimeout(function(){ stop({ skipSave: true }); }, 4000);
    }

    // End-of-convo heuristics (purchase complete or user exit intent)
    function checkEndOfConversation() {
      if (finalized) return;
      var txt = ((userEl.textContent || "") + "\n" + (aiEl.textContent || "")).toLowerCase();
      var purchaseSignals = ["purchase completed", "payment successful", "order confirmed", "checkout complete", "transaction id", "order number", "your receipt", "booking confirmed"];
      var endIntentSignals = ["bye", "goodbye", "that’s all", "thats all", "that's all", "thanks, that's all", "no thanks", "don't want to continue", "do not want to continue", "end the conversation", "stop now", "we are done", "that's it", "thats it"];
      var shouldEnd = purchaseSignals.some(function(s){ return txt.indexOf(s) !== -1; }) ||
                      endIntentSignals.some(function(s){ return txt.indexOf(s) !== -1; });
      if (shouldEnd) {
        (async function () {
          setStatus("Finalizing…");
          finalized = true;
          await saveConversation({ autosave: true, reason: "end_detected", close: true });
          greetingPending = sendClosingMessage("end_detected");
          if (greetingPending) armGreetAndStopFallback();
          else stop({ skipSave: true });
        })();
      }
    }

    // Data channel setup for OpenAI realtime events
    function attachEventChannel(dc){
      if (!dc) return;
      eventsDC = dc;
      eventsDC.onopen = function(){ setStatus("Connected."); };
      eventsDC.onclose = async function(){
        setStatus("Events channel closed.");
        await tryAutoSave("channel_closed");
      };
      eventsDC.onmessage = function(ev){
        var evt; try { evt = JSON.parse(ev.data); } catch (_e) { return; }
        if (DEBUG_EVENTS) console.log("oai-event:", evt);
        handleRealtimeEvent(evt);
      };
    }

    // Handle model tool/function call finalize_conversation
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
          (async function () {
            setStatus("Finalizing…");
            finalized = true;
            await saveConversation({ autosave: true, reason: reason, close: true });
            greetingPending = sendClosingMessage(reason);
            if (greetingPending) armGreetAndStopFallback();
            else stop({ skipSave: true });
          })();
        }
        return;
      }
    }

    // Router for realtime events (transcripts and model output)
    function handleRealtimeEvent(evt){
      var t = (evt && evt.type) || "";

      // Function/tool call routing
      if (t.indexOf("response.function_call") === 0 || t.indexOf("response.tool_call") === 0) {
        handleFunctionCallEvent(evt);
        return;
      }

      // When a closing message finishes, stop automatically
      if (greetingPending && (t === "response.completed" || t === "response.output_text.done")) {
        greetingPending = false;
        if (greetTimeoutHandle) { clearTimeout(greetTimeoutHandle); greetTimeoutHandle = null; }
        stop({ skipSave: true });
        return;
      }

      // User live transcription
      if (t.indexOf("transcription.delta") !== -1) {
        var textU = extractText(evt);
        if (textU) append(userEl, textU);
        markDirty();
        return;
      }
      if (t.indexOf("transcription.completed") !== -1) {
        appendLine(userEl, "");
        scheduleAutoSave(3000);
        checkEndOfConversation();
        return;
      }

      // Assistant text
      if (t === "response.output_text.delta" || (t.indexOf("response.") === 0 && t.indexOf(".delta") === t.length - 6)) {
        var textA = extractText(evt);
        if (textA) append(aiEl, textA);
        markDirty();
        return;
      }
      if (t === "response.output_text.done" || t === "response.completed") {
        appendLine(aiEl, "");
        scheduleAutoSave(3000);
        checkEndOfConversation();
        return;
      }
    }

    // Extract text from diverse event shapes
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

    // Start the session: mic + WebRTC to OpenAI
    async function start(){
      console.log("[app.js] Start clicked");
      startBtn.disabled = true; stopBtn.disabled = false;
      setStatus("Requesting microphone...");
      clearEl(userEl); clearEl(aiEl);
      if (autosaveTimer) clearTimeout(autosaveTimer);
      autosaveTimer = null; dirty = false; lastSnapshot = ""; lastSaveAt = 0; finalized = false;
      conversationId = null; greetingPending = false; if (greetTimeoutHandle) { clearTimeout(greetTimeoutHandle); greetTimeoutHandle = null; }

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
      } catch (e) {
        console.error(e);
        setStatus("Failed to create session.");
        startBtn.disabled=false; stopBtn.disabled=true;
        return;
      }

      var ephemeralKey = session.client_secret.value;
      var model = session.model || "gpt-4o-realtime-preview";

      setStatus("Starting WebRTC...");
      pc = new RTCPeerConnection({ iceServers: [{ urls: ["stun:stun.l.google.com:19302"] }] });
      pc.onconnectionstatechange = async function () {
        var st = pc.connectionState;
        if (st === "disconnected" || st === "failed" || st === "closed") await tryAutoSave("connection_state_" + st);
      };
      pc.ondatachannel = function (event) {
        if (event && event.channel && event.channel.label === "oai-events") attachEventChannel(event.channel);
      };
      var proactiveDC = pc.createDataChannel("oai-events"); attachEventChannel(proactiveDC);
      pc.ontrack = function (event) { var s = event && event.streams && event.streams[0]; if (s) aiAudio.srcObject = s; };

      if (micStream && micStream.getTracks) {
        micStream.getTracks().forEach(function (track) { try { pc.addTrack(track, micStream); } catch (_e) {} });
      }
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
      } catch (e) {
        console.error(e); setStatus("OpenAI SDP exchange failed."); await stop(); return;
      }

      await pc.setRemoteDescription({ type: "answer", sdp: answerSdp });
      setStatus("Live. Speak to your mic.");
    }

    // Save to backend (upsert single row using conversation_id)
    async function saveConversation(options){
      options = options || {};
      var user_text = userEl.textContent || "";
      var ai_text = aiEl.textContent || "";
      var payload = {
        session_id: sessionId || "",
        user_text: user_text, ai_text: ai_text,
        autosave: !!options.autosave,
        reason: options.reason || (options.autosave ? "autosave" : "manual"),
        close: !!options.close,
      };
      if (conversationId != null) payload.conversation_id = conversationId;

      var snap = currentSnapshot();
      if (!snap.trim()) return null;

      if (saving) return null;
      var now = Date.now();
      if (now - lastSaveAt < MIN_SAVE_INTERVAL_MS && options.autosave) return null;

      saving = true;
      try {
        var res = await fetch("/save-conversation/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          keepalive: true,
          body: JSON.stringify(payload),
        });
        var js = {}; try { js = await res.json(); } catch (_e) {}
        if (res.ok) {
          if (typeof js.id === "number") conversationId = js.id;
          lastSnapshot = snap; lastSaveAt = Date.now(); dirty = false;
        } else {
          console.warn("Save failed:", js);
        }
        return res.ok;
      } catch (e) {
        console.warn("Save failed:", e);
        scheduleAutoSave(4000);
        return null;
      } finally {
        saving = false;
      }
    }

    // Try autosave if dirty
    async function tryAutoSave(reason){
      reason = reason || "autosave";
      if (!dirty) return;
      await saveConversation({ autosave: true, reason: reason });
    }

    // Stop the call; optionally skip save if just finalized
    async function stop(options){
      options = options || {};
      var skipSave = !!options.skipSave;
      stopBtn.disabled = true; startBtn.disabled = false; setStatus("Stopping...");
      if (!skipSave) {
        await saveConversation({ autosave: true, reason: "manual_stop", close: !finalized });
      }
      try { if (eventsDC) eventsDC.close(); } catch (_e) {}
      try {
        if (pc) {
          try { pc.getSenders().forEach(function (s){ try { s.track && s.track.stop(); } catch (_e) {} }); } catch (_e) {}
          try { pc.getReceivers().forEach(function (r){ try { r.track && r.track.stop(); } catch (_e) {} }); } catch (_e) {}
          pc.close();
        }
      } catch (_e) {}
      try {
        if (micStream && micStream.getTracks) { micStream.getTracks().forEach(function (t){ try { t.stop(); } catch (_e) {} }); micStream = null; }
      } catch (_e) {}
      if (autosaveTimer) { clearTimeout(autosaveTimer); autosaveTimer = null; }
      if (greetTimeoutHandle) { clearTimeout(greetTimeoutHandle); greetTimeoutHandle = null; }
      pc = null; eventsDC = null; setStatus("Idle");
    }

    // Wire buttons
    startBtn.addEventListener("click", start);
    stopBtn.addEventListener("click", function(){ stop(); });

    // Best-effort save on page unload; close if not already finalized
    window.addEventListener("beforeunload", function () {
      try {
        var data = {
          session_id: sessionId || "",
          user_text: userEl.textContent || "",
          ai_text: aiEl.textContent || "",
          autosave: true,
          reason: "beforeunload",
          close: !finalized,
        };
        if (conversationId != null) data.conversation_id = conversationId;
        if (navigator.sendBeacon) {
          var blob = new Blob([JSON.stringify(data)], { type: "application/json" });
          navigator.sendBeacon("/save-conversation/", blob);
        }
      } catch (_e) {}
    });
  }

  // Ensure handlers bind after DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();