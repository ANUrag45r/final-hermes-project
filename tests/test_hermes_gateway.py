"""Tests for the Hermes API Server gateway adapter."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from app.services.hermes.hermes_service import HermesGatewayClient, _extract_reply


def test_extract_reply_common_shapes():
    assert _extract_reply({"response": "hi"}) == "hi"
    assert _extract_reply({"answer": "yo"}) == "yo"
    assert _extract_reply({"data": {"reply": "deep"}}, "data.reply") == "deep"
    assert _extract_reply(
        {"choices": [{"message": {"content": "openai-style"}}]}
    ) == "openai-style"
    assert _extract_reply("plain string") == "plain string"


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        msg = body.get("message", "")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"response": f"echo: {msg}"}).encode())

    def log_message(self, *args):
        pass  # silence


def test_gateway_client_round_trip():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        client = HermesGatewayClient(
            url=f"http://127.0.0.1:{port}",
            path="/chat",
            api_key="",
            message_field="message",
            response_field="response",
            timeout=10,
        )
        out = client.generate("give my last 3 mails")
        assert out == "echo: give my last 3 mails"
    finally:
        server.shutdown()


def test_gateway_provider_is_agentic():
    import os

    os.environ["HERMES_PROVIDER"] = "hermes_gateway"
    from app.core.config import Settings
    from app.services.hermes.hermes_service import build_hermes_service

    svc = build_hermes_service(Settings())
    assert svc.agentic is True
    os.environ.pop("HERMES_PROVIDER", None)
