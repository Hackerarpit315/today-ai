from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
JS = (FRONTEND / "app.js").read_text(encoding="utf-8")
HTML = (FRONTEND / "index.html").read_text(encoding="utf-8")
CSS = (FRONTEND / "styles.css").read_text(encoding="utf-8")
client = TestClient(app, raise_server_exceptions=False)


def test_ui_loads():
    response = client.get("/")
    assert response.status_code == 200
    assert "JARVIS" in response.text


def test_ui_has_text_input_and_send_control():
    assert 'id="input"' in HTML
    assert 'id="send"' in HTML
    assert 'id="form"' in HTML


def test_ui_has_response_area_and_states():
    assert 'id="chat"' in HTML
    for state in ("IDLE", "LISTENING", "PROCESSING", "RESPONDING", "SPEAKING", "ERROR"):
        assert state in JS


def test_ui_has_clear_and_speech_controls():
    assert 'id="clear"' in HTML
    assert 'id="mic"' in HTML
    assert 'id="stop-speech"' in HTML


def test_ui_posts_to_existing_assistant_endpoint():
    assert 'fetch("/api/assistant"' in JS
    assert 'method: "POST"' in JS
    assert 'current_datetime: new Date().toISOString()' in JS


def test_ui_does_not_create_second_assistant_endpoint():
    assert JS.count('fetch("/api/assistant"') == 1
    assert "/api/ui/message" not in JS


def test_ui_handles_validation_backend_unavailable_and_server_errors():
    assert "422" in JS
    assert "Backend unavailable or network connection failed." in JS
    assert "temporarily unavailable" in JS


def test_ui_handles_security_and_permission_outcomes():
    assert "Security policy blocked this request." in JS
    assert "Permission is required" in JS
    assert "403" in JS and "409" in JS


def test_ui_has_browser_stt_with_unsupported_fallback():
    assert "SpeechRecognition" in JS
    assert "webkitSpeechRecognition" in JS
    assert "not supported by this browser" in JS


def test_ui_handles_microphone_permission_denial():
    assert '"not-allowed"' in JS
    assert "Microphone permission was denied" in JS


def test_ui_places_transcript_in_text_input():
    assert "input.value = transcript.trim()" in JS
    assert "instance.onresult" in JS


def test_ui_uses_same_send_path_after_voice_transcript():
    assert "form.requestSubmit()" in JS
    assert 'fetch("/api/assistant"' in JS


def test_ui_has_browser_tts_and_stop_behavior():
    assert "speechSynthesis" in JS
    assert "SpeechSynthesisUtterance" in JS
    assert "speechSynthesis.cancel()" in JS
    assert "stopSpeaking" in JS


def test_ui_never_speaks_sensitive_text():
    assert "looksSensitive(text)" in JS
    assert "if (looksSensitive(answer))" in JS
    assert "if (!text || looksSensitive(text)) return false" in JS


def test_frontend_contains_no_api_keys_or_secret_values():
    forbidden = ("OPENAI_API_KEY", "OPENROUTER_API_KEY", "sk-", "Authorization: Bearer")
    assert not any(value in JS for value in forbidden)
    assert not any(value in HTML for value in forbidden)


def test_frontend_does_not_import_backend_security_or_execution_services():
    forbidden = ("permission_service", "security_service", "action_service", "execution_service", "eval(", "exec(")
    assert not any(value in JS for value in forbidden)


def test_ui_is_keyboard_accessible():
    assert 'aria-label="Start voice input"' in HTML
    assert 'aria-label="Stop speaking"' in HTML
    assert 'aria-label="Clear conversation"' in HTML
    assert "focus-visible" in CSS


def test_ui_is_mobile_friendly():
    assert "@media (max-width: 640px)" in CSS
    assert "viewport" in HTML


def test_existing_assistant_api_contract_remains_available():
    response = client.post(
        "/api/assistant",
        json={"content": "hello", "current_datetime": "2026-09-25T12:00:00+05:30"},
    )
    assert response.status_code == 200
    assert set(response.json()) == {"request_id", "status", "current_stage", "pipeline", "errors"}


def test_frontend_does_not_render_raw_pipeline_debug_data():
    assert "JSON.stringify(body.pipeline)" not in JS
    assert "JSON.stringify(body)" not in JS


def test_frontend_script_is_loaded_deferred():
    assert '<script src="app.js" defer></script>' in HTML
