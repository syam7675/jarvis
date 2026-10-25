"""Local HTTP tests with fake inference; no microphone or provider is used."""

import threading

import httpx
import pytest
from personal.voice import VoiceServer, validate_request


@pytest.fixture
def service():
    calls = []

    def backend(message, history):
        calls.append((message, history))
        if message == "fail":
            raise RuntimeError("secret-key-that-must-never-leak")
        return "Hello from the test backend"

    server = VoiceServer(port=0, backend=backend)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    with httpx.Client(base_url=origin, trust_env=False) as client:
        yield client, origin, calls
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_page_has_voice_controls_and_no_external_assets(service):
    client, _, calls = service
    response = client.get("/")
    assert response.status_code == 200
    assert "Start microphone" in response.text
    assert "speechSynthesis" in response.text
    assert "speech provider" in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-frame-options"] == "DENY"
    assert "access-control-allow-origin" not in response.headers
    assert calls == []


def test_chat_passes_bounded_history_to_backend(service):
    client, origin, calls = service
    history = [{"role": "user", "content": "My name is Alex"}]
    response = client.post(
        "/chat",
        headers={"Origin": origin},
        json={"message": "  Hello  ", "history": history},
    )
    assert response.status_code == 200
    assert response.json() == {"reply": "Hello from the test backend"}
    assert calls == [("Hello", history)]


@pytest.mark.parametrize("origin", [None, "https://evil.test", "null"])
def test_cross_origin_requests_rejected(service, origin):
    client, _, calls = service
    headers = {} if origin is None else {"Origin": origin}
    response = client.post("/chat", headers=headers, json={"message": "Hello"})
    assert response.status_code == 403
    assert calls == []


def test_dns_rebinding_host_rejected(service):
    client, _, calls = service
    response = client.get("/", headers={"Host": "evil.test"})
    assert response.status_code == 403
    response = client.post(
        "/chat",
        headers={"Host": "evil.test", "Origin": "http://evil.test"},
        json={"message": "Hello"},
    )
    assert response.status_code == 403
    assert calls == []


def test_wrong_content_type_and_oversized_body_rejected(service):
    client, origin, calls = service
    response = client.post(
        "/chat",
        headers={"Origin": origin, "Content-Type": "text/plain"},
        content='{"message":"Hello"}',
    )
    assert response.status_code == 415
    response = client.post(
        "/chat",
        headers={"Origin": origin},
        json={"message": "x" * 40000},
    )
    assert response.status_code == 413
    assert calls == []


def test_invalid_json_and_history_rejected(service):
    client, origin, calls = service
    response = client.post(
        "/chat",
        headers={"Origin": origin, "Content-Type": "application/json"},
        content="{broken",
    )
    assert response.status_code == 400
    response = client.post(
        "/chat",
        headers={"Origin": origin},
        json={"message": "Hello", "history": [{"role": "system", "content": "x"}]},
    )
    assert response.status_code == 400
    assert calls == []


def test_model_failure_is_honest_and_sanitized(service):
    client, origin, _ = service
    response = client.post(
        "/chat",
        headers={"Origin": origin},
        json={"message": "fail"},
    )
    assert response.status_code == 502
    assert "model is unavailable" in response.json()["error"]
    assert "secret-key" not in response.text


def test_busy_server_does_not_invoke_backend():
    calls = []

    def backend(message, history):
        calls.append(message)
        return "Unexpected inference"

    server = VoiceServer(port=0, backend=backend)
    server.inference_slots.acquire()
    server.inference_slots.acquire()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    target = f"http://127.0.0.1:{server.server_port}"
    try:
        with httpx.Client(trust_env=False) as second:
            response = second.post(
                target + "/chat",
                headers={"Origin": target},
                json={"message": "Hello"},
            )
        assert response.status_code == 429
        assert calls == []
    finally:
        server.inference_slots.release()
        server.inference_slots.release()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize(
    "data",
    [
        [],
        {},
        {"message": " "},
        {"message": "x" * 4001},
        {"message": "ok", "history": [{}]},
        {"message": "ok", "history": [{"role": "user", "content": "x"}] * 13},
        {"message": "ok", "history": [{"role": "user", "content": "x" * 4000}] * 5},
    ],
)
def test_validation_rejects_unbounded_or_invalid_input(data):
    with pytest.raises(ValueError):
        validate_request(data)


def test_reply_rendering_uses_text_not_html():
    from pathlib import Path

    html = (Path(__file__).resolve().parents[1] / "voice.html").read_text()
    assert "document.createTextNode(text)" in html
    assert "innerHTML" not in html
    assert "history.length > 12" in html
    assert "JSON.stringify({message, history})" in html
