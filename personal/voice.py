"""Loopback browser voice chat: browser speech I/O, configured Jarvis inference.

Run ``python -m personal.voice`` and open the printed address on the same
machine. Speech recognition availability depends on the browser and may send
audio to its speech provider. The server receives text only. No telephone
call is made by this service.
"""

from __future__ import annotations

import argparse
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

MAX_BODY_BYTES = 32768
MAX_HISTORY = 12
MAX_TEXT_CHARS = 4000
MAX_HISTORY_CHARS = 16000


def chat_backend(message: str, history: list[dict[str, str]]) -> str:
    """Call the actual configured model. Keys stay in the Python process."""
    import copy

    from openjarvis import Jarvis
    from openjarvis.core.config import load_config

    config = copy.deepcopy(load_config())
    config.agent.context_from_memory = False
    config.skills.enabled = False
    conversation = json.dumps(
        [*history, {"role": "user", "content": message}], ensure_ascii=False
    )
    prompt = (
        "You are Jarvis, the user's conversational assistant. Reply naturally "
        "and concisely for spoken playback. The JSON below is the conversation "
        "transcript. Respond to the final user message. You have no external "
        "action tools: never claim to dial, send, or change files.\n\n" + conversation
    )
    with Jarvis(
        config=config,
        engine_key=os.getenv("JARVIS_ENGINE") or config.engine.default,
        model=os.getenv("JARVIS_MODEL") or None,
    ) as jarvis:
        result = jarvis.ask(prompt, context=False, temperature=0.5, max_tokens=1024)
    if not isinstance(result, str) or not result.strip():
        raise RuntimeError("Configured model returned no answer")
    return result


def validate_request(data: Any) -> tuple[str, list[dict[str, str]]]:
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object.")
    message = data.get("message")
    if (
        not isinstance(message, str)
        or not message.strip()
        or len(message) > MAX_TEXT_CHARS
    ):
        raise ValueError(f"Message must contain 1 to {MAX_TEXT_CHARS} characters.")
    history = data.get("history", [])
    if not isinstance(history, list) or len(history) > MAX_HISTORY:
        raise ValueError(f"History must contain at most {MAX_HISTORY} messages.")
    validated = []
    for item in history:
        if (
            not isinstance(item, dict)
            or item.get("role") not in ("user", "assistant")
            or not isinstance(item.get("content"), str)
            or not item["content"].strip()
            or len(item["content"]) > MAX_TEXT_CHARS
        ):
            raise ValueError("Invalid conversation history.")
        validated.append({"role": item["role"], "content": item["content"]})
    if sum(len(item["content"]) for item in validated) > MAX_HISTORY_CHARS:
        raise ValueError("Conversation history is too long.")
    return message.strip(), validated


class VoiceServer(ThreadingHTTPServer):
    """Bind only loopback, with a replaceable backend for offline tests."""

    daemon_threads = True

    def __init__(
        self,
        port: int = 8765,
        backend: Callable[[str, list[dict[str, str]]], str] = chat_backend,
    ):
        self.backend = backend
        self.inference_slots = threading.BoundedSemaphore(2)
        super().__init__(("127.0.0.1", port), VoiceHandler)


class VoiceHandler(BaseHTTPRequestHandler):
    server: VoiceServer

    def log_message(self, format: str, *args: Any) -> None:
        # Do not log prompts, responses, credentials, or exception details.
        pass

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(35)

    def _allowed_authorities(self) -> set[str]:
        port = self.server.server_port
        return {f"127.0.0.1:{port}", f"localhost:{port}"}

    def _host_allowed(self) -> bool:
        return self.headers.get("Host", "") in self._allowed_authorities()

    def _respond(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        )
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, data: dict[str, Any]) -> None:
        self._respond(
            status,
            json.dumps(data).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def do_GET(self) -> None:
        if not self._host_allowed():
            self._json(403, {"error": "Only loopback Host addresses are allowed."})
            return
        if self.path != "/":
            self._json(404, {"error": "Not found."})
            return
        html = Path(__file__).with_suffix(".html").read_bytes()
        self._respond(200, html, "text/html; charset=utf-8")

    def do_POST(self) -> None:
        host = self.headers.get("Host", "")
        if not self._host_allowed() or self.headers.get("Origin") != f"http://{host}":
            self._json(403, {"error": "A same-origin loopback request is required."})
            return
        if self.path != "/chat":
            self._json(404, {"error": "Not found."})
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != (
            "application/json"
        ):
            self._json(415, {"error": "Use application/json."})
            return
        if self.headers.get("Transfer-Encoding"):
            self._json(400, {"error": "Chunked requests are unsupported."})
            return
        try:
            size = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self._json(411, {"error": "Content-Length is required."})
            return
        if size <= 0 or size > MAX_BODY_BYTES:
            self._json(413, {"error": "Request body is too large or empty."})
            return
        try:
            raw = self.rfile.read(size)
            if len(raw) != size:
                raise ValueError("Incomplete request body.")
            message, history = validate_request(json.loads(raw))
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"error": "Invalid message or conversation history."})
            return
        if not self.server.inference_slots.acquire(blocking=False):
            self._json(429, {"error": "Jarvis is busy. Try again shortly."})
            return
        try:
            answer = self.server.backend(message, history)
            if not isinstance(answer, str) or not answer.strip():
                raise RuntimeError("Model returned no answer")
            self._json(200, {"reply": answer[:MAX_TEXT_CHARS]})
        except Exception:
            self._json(
                502,
                {
                    "error": "The configured model is unavailable. "
                    "Check Jarvis engine, model, and secure provider settings."
                },
            )
        finally:
            self.server.inference_slots.release()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("Port must be between 0 and 65535.")
    with VoiceServer(args.port) as server:
        print(f"Jarvis voice chat: http://127.0.0.1:{server.server_port}", flush=True)
        print("Local browser required; speech recognition may use its provider.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
