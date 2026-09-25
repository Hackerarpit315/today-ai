# Module 15 — JARVIS UI / Voice Layer

Module 15 is the user-facing presentation layer for Today AI. It refines the existing M15 UI/voice scaffolding rather than creating a duplicate subsystem.

## Existing implementation found

Before refinement, the project already contained:
- `frontend/index.html`, `frontend/styles.css`, `frontend/app.js`
- UI/conversation schemas and service under `app/schemas/ui.py` and `app/services/ui_service.py`
- voice provider interfaces and mock providers under `app/services/voice/`
- a public `POST /api/assistant` endpoint backed by the existing orchestrator

The old frontend was only a placeholder: it displayed a mock response and the microphone button explicitly said voice was not connected. M15 now uses the real assistant endpoint and browser-native voice APIs.

## Architecture

```text
User
  ↓
JARVIS UI
  ├─ typed text
  └─ browser Speech Recognition → transcript
           ↓
      POST /api/assistant
           ↓
      existing backend pipeline
           ↓
      safe AssistantResponse envelope
           ↓
      JARVIS UI
           ↓
      optional browser Speech Synthesis
```

The current `/api/assistant` contract exposes the existing integration pipeline. It is currently the public M1→M8/LLM integration boundary; M9–M14 remain authoritative modules but are not globally inserted into that endpoint by M15. M15 does not invent a second security/action pipeline or claim that they are already executed through `/api/assistant`.

## UI

Plain HTML/CSS/JavaScript only. No frontend framework, build system, CDN, or external service is required.

Features:
- text input and Send
- assistant response area
- Processing/Error states
- Clear conversation
- mobile/desktop responsive layout
- keyboard submission and visible focus states
- readable connection/assistant/voice status

## Voice input

Uses browser-native Web Speech API when available:
- `SpeechRecognition` / `webkitSpeechRecognition`
- transcript is placed into the same text input
- the same `POST /api/assistant` path is used for voice and typed requests
- microphone denial and unsupported browsers are handled gracefully
- tests do not require a real microphone

## Voice output

Uses browser-native `SpeechSynthesis` / `SpeechSynthesisUtterance`:
- speaks only the safe user-facing response assembled by the UI
- cancels previous speech before starting a new utterance
- provides a Stop Speaking control
- silently skips TTS when unavailable
- blocks text matching obvious credential/token patterns from being spoken

## Backend/security boundary

The frontend never contains API keys or credentials and never authorizes or executes actions. Backend authorization/security remains authoritative. HTTP security/permission outcomes are displayed as safe user-facing messages when returned by a backend implementation.

The frontend does not directly import or reproduce Permission, Security, Action, or Execution logic.

## Static serving

`app/main.py` has one minimal M15 change: it mounts the local `frontend/` directory at `/` after the existing API routes. This allows the same FastAPI origin to serve the UI and receive `/api/assistant` requests without adding CORS or another web service.

## Limitations

- Browser Speech Recognition support varies by browser/platform and may require microphone permission.
- Browser Speech Synthesis voices vary by operating system/browser.
- The current `/api/assistant` response is a structured pipeline envelope, not a dedicated natural-language answer field. M15 therefore renders a concise safe summary from existing pipeline fields instead of creating a second AI response pipeline.
- No real microphone/speaker dependency is used by tests.
