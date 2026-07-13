"""
Hermes reasoning layer.

`HermesService` is the adapter façade the rest of the app talks to. It owns a
`HermesClient` chosen by configuration and a `PromptBuilder`. This is the ONLY
place that knows how to reach an LLM, and it NEVER stores memory.

Providers (selected via Settings.hermes_provider):
  - local      : deterministic, dependency-free reasoning over RAGContext
  - hermes     : the real installed Hermes service over HTTP
  - hermes_cli : a locally-installed Hermes command-line tool (subprocess)
  - openai     : any OpenAI-compatible /v1/chat/completions endpoint
  - ollama     : a local Ollama server

To support a new LLM, add a HermesClient subclass and register it in
`build_hermes_service`. No business logic elsewhere changes.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod

import httpx

from app.core.config import Settings
from app.schemas.chat_schema import RAGContext
from app.services.hermes.prompt_builder import SYSTEM_PROMPT, PromptBuilder
from app.utils.logger import get_logger

logger = get_logger("hermes")

# Strips ANSI CSI/OSC escape sequences and TUI box-drawing/spinner noise so the
# plain answer text can be recovered from an interactive agent's output.
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*\x07")
_BOX_CHARS = "─━│┃┄┅┆┇┈┉┊┋┌┐└┘├┤┬┴┼╭╮╯╰═║╔╗╚╝╠╣╦╩╬▌▐░▒▓█⚕⚡💻┊"


def _clean_terminal_output(text: str) -> str:
    text = _ANSI_RE.sub("", text)
    lines = []
    for line in text.splitlines():
        stripped = line.strip().strip(_BOX_CHARS).strip()
        if not stripped or _is_chrome(stripped):
            continue
        if _is_decorative(stripped):
            continue
        lines.append(stripped)
    return "\n".join(lines).strip()


def _is_decorative(line: str) -> bool:
    """Drop lines that are mostly box-drawing or mojibake border runs.

    Hermes prints long horizontal rule lines; if they were mis-decoded on the
    way in they can show up as runs like 'â€"â€"â€"'. Either way they carry no
    content, so a line that's overwhelmingly box/border noise is dropped.
    """
    noise = set(_BOX_CHARS) | set("â€™ Â\x80\x99\x9c\x9d")
    non_space = [c for c in line if not c.isspace()]
    if not non_space:
        return True
    noisy = sum(1 for c in non_space if c in noise)
    return noisy / len(non_space) > 0.6


def _is_chrome(line: str) -> bool:
    """True for Hermes TUI scaffolding lines that aren't part of the answer."""
    low = line.lower()
    if line in {"Hermes", "⚕ Hermes"}:
        return True
    if "│" in line:  # the bottom status bar (model, token usage, timers)
        return True
    return (
        low.startswith("initializing agent")
        or low.startswith("$ ")
        or "preparing terminal" in low
        or "preparing mcp" in low
        or low.startswith("the active mcp servers")
    )


# --------------------------------------------------------------------------- #
# Client adapters                                                             #
# --------------------------------------------------------------------------- #
class HermesClient(ABC):
    """Transport adapter. Given a prompt, return generated text."""

    @abstractmethod
    def generate(self, prompt: str, system: str = SYSTEM_PROMPT) -> str: ...


class HttpHermesClient(HermesClient):
    """Talks to the real installed Hermes service."""

    def __init__(self, base_url: str, api_key: str, model: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def generate(self, prompt: str, system: str = SYSTEM_PROMPT) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {"model": self.model, "system": system, "prompt": prompt}
        resp = httpx.post(
            f"{self.base_url}/generate",
            json=payload,
            headers=headers,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        # Be tolerant of common response shapes.
        return (
            data.get("answer")
            or data.get("response")
            or data.get("text")
            or ""
        ).strip()


class OpenAICompatibleClient(HermesClient):
    """Any OpenAI-compatible Chat Completions endpoint (OpenAI, vLLM, etc.)."""

    def __init__(self, base_url: str, api_key: str, model: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def generate(self, prompt: str, system: str = SYSTEM_PROMPT) -> str:
        resp = httpx.post(
            f"{self.base_url}/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


class OllamaClient(HermesClient):
    """Local Ollama server."""

    def __init__(self, base_url: str, model: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def generate(self, prompt: str, system: str = SYSTEM_PROMPT) -> str:
        resp = httpx.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "system": system,
                "prompt": prompt,
                "stream": False,
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()


def _extract_reply(data, response_field: str = "") -> str:
    """Pull the assistant text out of a gateway JSON response.

    Tries the configured dot-path first (e.g. "data.reply"), then a set of
    common keys, then falls back to the raw value. Tolerant of unknown shapes.
    """
    if isinstance(data, str):
        return data.strip()

    def dig(obj, path):
        cur = obj
        for part in path.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return None
        return cur

    if response_field:
        val = dig(data, response_field)
        if isinstance(val, str) and val.strip():
            return val.strip()

    if isinstance(data, dict):
        for key in ("response", "answer", "text", "reply", "message", "content", "output"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
            # OpenAI-style nesting: choices[0].message.content
            if key == "message" and isinstance(val, dict):
                inner = val.get("content")
                if isinstance(inner, str) and inner.strip():
                    return inner.strip()
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            msg = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
            if isinstance(msg.get("content"), str):
                return msg["content"].strip()

    import json

    return json.dumps(data)[:2000]


class HermesGatewayClient(HermesClient):
    """
    Talks to the Hermes API Server gateway (`hermes gateway setup` -> API Server).

    This is the recommended integration: a real HTTP endpoint that returns JSON,
    so there's no terminal scraping and no per-request process spawn. The exact
    endpoint path, request field and response field are configurable so the
    client adapts to the gateway's actual contract.
    """

    def __init__(
        self,
        url: str,
        path: str,
        api_key: str,
        message_field: str,
        response_field: str,
        timeout: float,
    ) -> None:
        self.endpoint = url.rstrip("/") + "/" + path.lstrip("/")
        self.api_key = api_key
        self.message_field = message_field or "message"
        self.response_field = response_field
        self.timeout = timeout

    def generate(self, prompt: str, system: str = SYSTEM_PROMPT) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {self.message_field: prompt}
        logger.info("Calling Hermes gateway: %s", self.endpoint)
        resp = httpx.post(
            self.endpoint, json=payload, headers=headers, timeout=self.timeout
        )
        resp.raise_for_status()
        try:
            data = resp.json()
        except Exception:  # noqa: BLE001
            return resp.text.strip()
        return _clean_terminal_output(_extract_reply(data, self.response_field))


class CliHermesClient(HermesClient):
    """
    Runs a locally-installed Hermes command-line tool as a subprocess.

    The prompt is delivered either on stdin (default) or as a CLI argument, and
    the model's answer is read from stdout. This is the right adapter when your
    Hermes is an executable rather than an HTTP service.

    Windows .lnk shortcuts are resolved to their target executable so you can
    point straight at e.g. C:\\Users\\you\\Desktop\\Hermes.lnk.

    Config (Settings):
      hermes_cli_path      path to the executable or .lnk
      hermes_cli_args      arg template; a token equal to/containing "{prompt}"
                           is replaced by the full prompt (used when not stdin)
      hermes_cli_use_stdin True -> pipe the prompt to stdin (default)
    """

    def __init__(
        self, path: str, args_template: str, use_stdin: bool, timeout: float
    ) -> None:
        self.path = path
        self.args_template = args_template or ""
        self.use_stdin = use_stdin
        self.timeout = timeout

    def generate(self, prompt: str, system: str = SYSTEM_PROMPT) -> str:
        import shlex
        import subprocess

        if not self.path:
            raise RuntimeError(
                "HERMES_CLI_PATH is not set — point it at your Hermes executable."
            )

        full = f"{system}\n\n{prompt}" if system else prompt
        exe = self._resolve_executable(self.path)

        tokens = shlex.split(self.args_template) if self.args_template else []
        if self.use_stdin:
            cmd = [exe, *tokens]
            stdin_data: str | None = full
        else:
            # Substitute {prompt} as a single argv element (keeps spaces intact).
            cmd = [exe] + [
                (t.replace("{prompt}", full) if "{prompt}" in t else t) for t in tokens
            ]
            stdin_data = None

        logger.info("Invoking Hermes CLI: %s", exe)
        result = subprocess.run(
            cmd,
            input=stdin_data,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=self.timeout,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Hermes CLI exited {result.returncode}: "
                f"{(result.stderr or '').strip()[:300]}"
            )
        return _clean_terminal_output(result.stdout or "")

    @staticmethod
    def _resolve_executable(path: str) -> str:
        """Resolve to a runnable path.

        1) A Windows .lnk shortcut -> its target executable.
        2) A bare command like 'hermes' -> its full path on PATH (respecting
           PATHEXT on Windows, so hermes.exe / hermes.cmd are found).
        Otherwise return the path unchanged.
        """
        import os
        import shutil
        import sys

        if path.lower().endswith(".lnk") and sys.platform.startswith("win"):
            target = CliHermesClient._resolve_windows_shortcut(path)
            if target:
                path = target

        if not os.path.isfile(path):
            found = shutil.which(path)
            if found:
                return found
        return path

    @staticmethod
    def _resolve_windows_shortcut(path: str) -> str:
        import subprocess

        try:
            ps = (
                "$s=(New-Object -ComObject WScript.Shell)."
                f"CreateShortcut('{path}'); Write-Output $s.TargetPath"
            )
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                capture_output=True,
                text=True,
                timeout=10,
            )
            target = (out.stdout or "").strip()
            if target:
                logger.info("Resolved shortcut %s -> %s", path, target)
                return target
        except Exception as exc:  # noqa: BLE001
            logger.error("Could not resolve shortcut %s: %s", path, exc)
        return path


class LocalReasoner:
    """
    Deterministic, offline reasoning over RAGContext.

    Not an LLM — it composes a faithful answer from retrieved evidence so the
    full pipeline works with zero external dependencies. Good enough for dev,
    demos and CI; replace with a real provider for production-grade language.
    """

    def answer(self, question: str, context: RAGContext) -> str:
        if context.is_empty():
            return (
                "I don't have anything in memory about that yet. "
                "Try ingesting the relevant meeting first."
            )

        responsibilities = [
            f"{f.source} is responsible for {f.target}"
            for f in context.graph_facts
            if f.relation == "responsible_for"
        ]
        discussions = [
            f"{f.source} discussed {f.target}"
            for f in context.graph_facts
            if f.relation == "discusses"
        ]

        parts: list[str] = []
        if responsibilities:
            parts.append(". ".join(dict.fromkeys(responsibilities)) + ".")
        elif discussions:
            parts.append(". ".join(dict.fromkeys(discussions)) + ".")

        if context.vector_hits:
            top = context.vector_hits[0]
            speaker = f"{top.speaker}: " if top.speaker else ""
            parts.append(f"Relevant excerpt — {speaker}{top.content}")

        return "\n".join(parts) if parts else context.vector_hits[0].content


# --------------------------------------------------------------------------- #
# Service façade                                                              #
# --------------------------------------------------------------------------- #
class HermesService:
    def __init__(
        self,
        provider: str,
        prompt_builder: PromptBuilder,
        client: HermesClient | None = None,
        local_reasoner: LocalReasoner | None = None,
        agentic: bool = False,
    ) -> None:
        self.provider = provider
        self.prompt_builder = prompt_builder
        self.client = client
        self.local_reasoner = local_reasoner or LocalReasoner()
        # Agentic = Hermes does its own retrieval/tools; we pass the raw question.
        self.agentic = agentic

    def answer(self, question: str, context: RAGContext) -> str:
        """App-side RAG: build a grounded prompt from retrieved context."""
        if self.provider == "local" or self.client is None:
            return self.local_reasoner.answer(question, context)
        prompt = self.prompt_builder.build(question, context)
        logger.info("Calling Hermes provider=%s", self.provider)
        try:
            return self.client.generate(prompt)
        except Exception as exc:  # noqa: BLE001
            logger.error("Hermes call failed: %s — falling back to local", exc)
            return self.local_reasoner.answer(question, context)

    def answer_raw(self, question: str) -> str:
        """Agentic passthrough: hand the question to Hermes untouched so it can
        use its own memory (gbrain) and tools (e.g. composio mail)."""
        if self.client is None:
            return self.local_reasoner.answer(question, RAGContext(query=question))
        logger.info("Agentic Hermes passthrough provider=%s", self.provider)
        try:
            return self.client.generate(question, system="")
        except Exception as exc:  # noqa: BLE001
            logger.error("Hermes call failed: %s — falling back to local", exc)
            return self.local_reasoner.answer(question, RAGContext(query=question))


def build_hermes_service(settings: Settings) -> HermesService:
    """Factory selecting the configured reasoning provider."""
    pb = PromptBuilder()
    provider = settings.hermes_provider

    if provider == "local":
        return HermesService(provider, pb, client=None)
    if provider == "hermes":
        client = HttpHermesClient(
            settings.hermes_base_url,
            settings.hermes_api_key,
            settings.hermes_model,
            settings.hermes_timeout_seconds,
        )
    elif provider == "hermes_gateway":
        client = HermesGatewayClient(
            settings.hermes_gateway_url,
            settings.hermes_gateway_path,
            settings.hermes_gateway_api_key,
            settings.hermes_gateway_message_field,
            settings.hermes_gateway_response_field,
            settings.hermes_timeout_seconds,
        )
    elif provider == "openai":
        client = OpenAICompatibleClient(
            settings.hermes_base_url,
            settings.hermes_api_key,
            settings.hermes_model,
            settings.hermes_timeout_seconds,
        )
    elif provider == "hermes_api":
        # Hermes Agent's built-in API server: OpenAI-compatible /v1/chat/completions
        # on (default) http://127.0.0.1:8642. Same wire format as `openai`, but
        # it's a full agent (its own memory + tools), so we run it agentic.
        client = OpenAICompatibleClient(
            settings.hermes_base_url,
            settings.hermes_api_key,
            settings.hermes_model,
            settings.hermes_timeout_seconds,
        )
    elif provider == "ollama":
        client = OllamaClient(
            settings.hermes_base_url,
            settings.hermes_model,
            settings.hermes_timeout_seconds,
        )
    elif provider == "hermes_cli":
        client = CliHermesClient(
            settings.hermes_cli_path,
            settings.hermes_cli_args,
            settings.hermes_cli_use_stdin,
            settings.hermes_timeout_seconds,
        )
    else:
        raise ValueError(f"Unknown hermes provider: {provider}")

    # The real Hermes (CLI, HTTP, gateway or API server) is an agent with its
    # own memory + tools, so pass the question through verbatim when agentic.
    agentic = settings.hermes_agentic and provider in {
        "hermes",
        "hermes_cli",
        "hermes_gateway",
        "hermes_api",
    }
    return HermesService(provider, pb, client=client, agentic=agentic)
