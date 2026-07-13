"""Tests for the hermes_api provider (Hermes API server, OpenAI-compatible)."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from app.core.config import Settings
from app.services.hermes.hermes_service import build_hermes_service


class _OpenAIStub(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        user = body["messages"][-1]["content"]
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        payload = {
            "choices": [
                {"message": {"role": "assistant", "content": f"hermes says: {user}"}}
            ]
        }
        self.wfile.write(json.dumps(payload).encode())

    def log_message(self, *a):
        pass


def test_hermes_api_is_agentic():
    svc = build_hermes_service(Settings(hermes_provider="hermes_api"))
    assert svc.provider == "hermes_api"
    assert svc.agentic is True


def test_hermes_api_round_trip():
    server = HTTPServer(("127.0.0.1", 0), _OpenAIStub)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        svc = build_hermes_service(
            Settings(
                hermes_provider="hermes_api",
                hermes_base_url=f"http://127.0.0.1:{port}",
                hermes_api_key="secret",
                hermes_model="hermes-agent",
            )
        )
        # agentic passthrough sends the question verbatim
        out = svc.answer_raw("give my last 3 mails")
        assert out == "hermes says: give my last 3 mails"
    finally:
        server.shutdown()
