"""
Tests for the CLI Hermes adapter.

We can't run the user's real Hermes binary here, so we use the Python
interpreter as a stand-in "Hermes CLI" to prove the subprocess plumbing —
stdin delivery, argument delivery, and stdout capture — works end to end.
"""
import sys

from app.services.hermes.hermes_service import CliHermesClient


def test_cli_prompt_via_stdin():
    script = (
        "import sys; data=sys.stdin.read(); "
        "print('CLI_ANSWER:', data.strip().splitlines()[-1])"
    )
    client = CliHermesClient(
        path=sys.executable,
        args_template=f'-c "{script}"',
        use_stdin=True,
        timeout=30,
    )
    out = client.generate("What task was assigned to Bob?", system="SYSTEM")
    assert out.startswith("CLI_ANSWER:")
    assert "Bob" in out


def test_cli_prompt_via_arg():
    script = "import sys; print('GOT:', sys.argv[1])"
    client = CliHermesClient(
        path=sys.executable,
        args_template=f'-c "{script}" {{prompt}}',
        use_stdin=False,
        timeout=30,
    )
    out = client.generate("authentication status?", system="SYS")
    assert out.startswith("GOT:")
    assert "authentication" in out


def test_cli_missing_path_raises():
    client = CliHermesClient(path="", args_template="", use_stdin=True, timeout=5)
    try:
        client.generate("hi")
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "HERMES_CLI_PATH" in str(exc)


def test_resolve_executable_on_path():
    """A bare command name resolves to its full path (handles 'hermes')."""
    import os

    resolved = CliHermesClient._resolve_executable("python3")
    assert os.path.isfile(resolved), f"expected a real file, got {resolved!r}"


def test_terminal_output_is_cleaned():
    from app.services.hermes.hermes_service import _clean_terminal_output

    raw = (
        "\x1b[32mInitializing agent...\x1b[0m\n"
        "╭─ Hermes ─────────╮\n"
        "    Bob owns Authentication.\n"
        "╰──────────────────╯\n"
    )
    cleaned = _clean_terminal_output(raw)
    assert "Bob owns Authentication." in cleaned
    assert "\x1b" not in cleaned
    assert "╭" not in cleaned


def test_answer_raw_passthrough():
    from app.services.hermes.hermes_service import HermesService
    from app.services.hermes.prompt_builder import PromptBuilder

    script = "import sys; print('AGENT:', sys.stdin.read().strip())"
    client = CliHermesClient(
        path=sys.executable,
        args_template=f'-c "{script}"',
        use_stdin=True,
        timeout=30,
    )
    svc = HermesService("hermes_cli", PromptBuilder(), client=client, agentic=True)
    out = svc.answer_raw("give my last 3 mails")
    assert "AGENT:" in out
    assert "mails" in out


def test_agentic_chat_bypasses_mail_and_gbrain():
    """In agentic mode the question goes straight to Hermes; app-side mail and
    gbrain retrieval are not invoked."""
    from app.schemas.chat_schema import ChatRequest
    from app.services.chat.chat_service import ChatService

    class FakeHermes:
        provider = "hermes_cli"
        agentic = True

        def answer_raw(self, q):
            return f"HERMES_HANDLED: {q}"

    class BoomGBrain:
        def search(self, *a, **k):
            raise AssertionError("gbrain.search must not be called in agentic mode")

    class BoomMail:
        def handle(self, *a, **k):
            raise AssertionError("mail.handle must not be called in agentic mode")

    svc = ChatService(gbrain=BoomGBrain(), hermes=FakeHermes(), mail=BoomMail())
    resp = svc.ask(ChatRequest(query="fetch my last 3 mails"))
    assert resp.answer == "HERMES_HANDLED: fetch my last 3 mails"
    assert resp.provider == "hermes_cli"
