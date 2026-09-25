(() => {
  "use strict";

  const chat = document.querySelector("#chat");
  const form = document.querySelector("#form");
  const input = document.querySelector("#input");
  const send = document.querySelector("#send");
  const mic = document.querySelector("#mic");
  const stopSpeech = document.querySelector("#stop-speech");
  const clear = document.querySelector("#clear");
  const errorBox = document.querySelector("#error");
  const status = document.querySelector("#status");
  const connection = document.querySelector("#connection");
  const assistant = document.querySelector("#assistant");
  const voice = document.querySelector("#voice");

  const STATES = Object.freeze({
    IDLE: "IDLE",
    LISTENING: "LISTENING",
    PROCESSING: "PROCESSING",
    RESPONDING: "RESPONDING",
    SPEAKING: "SPEAKING",
    ERROR: "ERROR",
  });

  let currentState = STATES.IDLE;
  let recognition = null;
  let listening = false;

  function setState(next) {
    currentState = next;
    status.textContent = next;
    assistant.textContent = next === STATES.PROCESSING ? "PROCESSING" : next;
    voice.textContent = next === STATES.LISTENING ? "LISTENING" : next === STATES.SPEAKING ? "SPEAKING" : "IDLE";
    connection.textContent = next === STATES.ERROR ? "CHECK BACKEND" : "READY";
    mic.setAttribute("aria-label", next === STATES.LISTENING ? "Stop voice input" : "Start voice input");
  }

  function showError(message) {
    errorBox.hidden = false;
    errorBox.textContent = message;
    setState(STATES.ERROR);
  }

  function clearError() {
    errorBox.hidden = true;
    errorBox.textContent = "";
  }

  function bubble(text, role, metaText = "") {
    const wrapper = document.createElement("div");
    wrapper.className = `bubble ${role}`;
    wrapper.textContent = text;
    if (metaText) {
      const meta = document.createElement("div");
      meta.className = "meta";
      meta.textContent = metaText;
      wrapper.appendChild(meta);
    }
    chat.appendChild(wrapper);
    chat.scrollTop = chat.scrollHeight;
  }

  function looksSensitive(text) {
    return /(?:password|passwd|pwd|otp|api[_ -]?key|apikey|access[_ -]?token|refresh[_ -]?token|client[_ -]?secret)\s*[:=]\s*\S+|bearer\s+[A-Za-z0-9._~-]+|-----BEGIN [A-Z ]*PRIVATE KEY-----/i.test(text);
  }

  function safeResponseText(body) {
    if (!body || typeof body !== "object") return "The backend returned an invalid response.";
    if (body.status === "success") {
      const today = body.pipeline && body.pipeline.today;
      const goal = body.pipeline && body.pipeline.intent && body.pipeline.intent.goal;
      if (today && today.next_task && today.next_task.title) {
        return `Request processed.\nGoal: ${goal || "your request"}\nNext step: ${today.next_task.title}`;
      }
      if (goal) return `Request processed.\nGoal: ${goal}`;
      return "Request processed successfully.";
    }
    const firstError = Array.isArray(body.errors) ? body.errors[0] : null;
    if (firstError && typeof firstError.message === "string") return firstError.message;
    return "The request could not be completed safely.";
  }

  function errorMessage(statusCode, body) {
    const code = body && typeof body.error === "string" ? body.error : "";
    if (statusCode === 403 || code.includes("security")) return "Security policy blocked this request.";
    if (statusCode === 409 || code.includes("permission")) return "Permission is required before this request can continue.";
    if (statusCode === 422) return "Please check the request and try again.";
    if (statusCode >= 500) return "Today AI is temporarily unavailable.";
    return "The request could not be completed.";
  }

  async function sendToAssistant(text) {
    clearError();
    setState(STATES.PROCESSING);
    send.disabled = true;
    mic.disabled = true;
    try {
      const response = await fetch("/api/assistant", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: text, current_datetime: new Date().toISOString() }),
      });
      let body = null;
      try { body = await response.json(); } catch (_) { body = null; }
      if (!response.ok) throw Object.assign(new Error(errorMessage(response.status, body)), { userMessage: errorMessage(response.status, body) });
      const answer = safeResponseText(body);
      if (looksSensitive(answer)) throw new Error("The response was withheld because it matched a sensitive-data pattern.");
      setState(STATES.RESPONDING);
      bubble(answer, "assistant", body && body.current_stage ? `Stage: ${body.current_stage}` : "");
      speak(answer);
      if (currentState !== STATES.SPEAKING) setState(STATES.IDLE);
    } catch (err) {
      const message = err && err.name === "TypeError" ? "Backend unavailable or network connection failed." : (err.userMessage || err.message || "Request failed.");
      showError(message);
    } finally {
      send.disabled = false;
      mic.disabled = false;
    }
  }

  function speak(text) {
    if (!("speechSynthesis" in window)) return false;
    if (!text || looksSensitive(text)) return false;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.onstart = () => setState(STATES.SPEAKING);
    utterance.onend = () => setState(STATES.IDLE);
    utterance.onerror = () => setState(STATES.IDLE);
    window.speechSynthesis.speak(utterance);
    return true;
  }

  function stopSpeaking() {
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    if (currentState === STATES.SPEAKING) setState(STATES.IDLE);
  }

  function setupRecognition() {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) return null;
    const instance = new Recognition();
    instance.lang = document.documentElement.lang === "hi" ? "hi-IN" : "en-IN";
    instance.interimResults = true;
    instance.continuous = false;
    instance.onstart = () => { listening = true; setState(STATES.LISTENING); clearError(); };
    instance.onresult = (event) => {
      let transcript = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) transcript += event.results[i][0].transcript;
      input.value = transcript.trim();
    };
    instance.onerror = (event) => {
      listening = false;
      if (event.error === "not-allowed" || event.error === "service-not-allowed") showError("Microphone permission was denied. Allow microphone access and try again.");
      else if (event.error === "no-speech") showError("No speech was detected. Try again.");
      else showError("Voice input failed. You can type your request instead.");
    };
    instance.onend = () => { listening = false; if (currentState === STATES.LISTENING) setState(STATES.IDLE); };
    return instance;
  }

  mic.addEventListener("click", () => {
    if (!recognition) {
      recognition = setupRecognition();
      if (!recognition) { showError("Voice input is not supported by this browser. You can type your request instead."); return; }
    }
    if (listening) recognition.stop();
    else { try { recognition.start(); } catch (_) { showError("Voice input could not be started. Try again."); } }
  });

  stopSpeech.addEventListener("click", stopSpeaking);
  clear.addEventListener("click", () => {
    stopSpeaking();
    chat.innerHTML = "";
    bubble("Conversation cleared. JARVIS is ready.", "assistant");
    clearError();
    setState(STATES.IDLE);
    input.focus();
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = input.value.trim();
    if (!text || send.disabled) return;
    if (looksSensitive(text)) { showError("Sensitive credentials or tokens should not be entered here."); return; }
    bubble(text, "user");
    input.value = "";
    sendToAssistant(text);
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  stopSpeech.disabled = !("speechSynthesis" in window);
  setState(STATES.IDLE);
})();
