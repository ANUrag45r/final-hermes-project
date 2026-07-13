"""
Hermes Agent control panel — connects to the local Hermes via its CLI.

Mirrors how `hermes-control-interface` talks to Hermes: it shells out to the
`hermes` binary (no special API, no credentials). This service is deliberately
limited to a small ALLOWLIST of read-only commands (status, sessions, profiles,
insights, logs, mcp) so the panel can never be used as an arbitrary browser
shell. Command templates are overridable in case your Hermes build names a
subcommand differently.
"""
from __future__ import annotations

import shlex
import shutil
import subprocess

from app.core.config import Settings
from app.services.hermes.hermes_service import _clean_terminal_output
from app.utils.logger import get_logger

logger = get_logger("hermes.control")

# action -> default CLI arguments (after the hermes executable).
_DEFAULT_COMMANDS: dict[str, list[str]] = {
    "status": ["status"],
    "sessions": ["sessions", "list"],
    "profiles": ["profile", "list"],
    "insights": ["insights", "--days", "7"],
    "logs": ["logs", "--lines", "100"],
    "mcp": ["mcp", "list"],
}


class HermesControlError(RuntimeError):
    pass


class HermesControlService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def actions(self) -> list[str]:
        return list(_DEFAULT_COMMANDS.keys())

    def _resolve_exe(self) -> str:
        path = self.settings.hermes_cli_path or "hermes"
        resolved = shutil.which(path) or path
        return resolved

    def available(self) -> bool:
        """True if a hermes executable can be located."""
        path = self.settings.hermes_cli_path or "hermes"
        return bool(shutil.which(path)) or bool(self.settings.hermes_cli_path)

    def run(self, action: str, timeout: float = 30.0) -> dict:
        if action not in _DEFAULT_COMMANDS:
            raise HermesControlError(
                f"Unknown action '{action}'. Allowed: {', '.join(self.actions)}"
            )
        return self._exec(_DEFAULT_COMMANDS[action], action=action, timeout=timeout)

    def chat(self, message: str, timeout: float = 180.0) -> dict:
        """Send a free-form message straight to the Hermes CLI.

        Runs `hermes chat -q "<message>" --yolo` and returns the agent's output.
        `--yolo` bypasses interactive tool-approval prompts so the headless call
        can't hang waiting for input. The message is passed as a single argv
        element (no shell), so there's no shell-injection surface.
        """
        message = (message or "").strip()
        if not message:
            raise HermesControlError("Empty message.")
        return self._exec(
            ["chat", "-q", message, "--yolo"], action="chat", timeout=timeout
        )

    def save_to_gbrain(
        self, meeting_id: str, title: str, transcript: str, timeout: float = 240.0
    ) -> dict:
        """Persist a meeting into gbrain (Hermes memory at ~/.gbrain).

        gbrain ingests *files* (chunk -> embed -> FTS5 -> entity graph) and
        keeps the result in ~/.gbrain. So we:
          1. write the meeting to a real file in the gbrain feed folder
             (default ~/gbrain-feed, configurable via GBRAIN_FEED_DIR), and
          2. tell Hermes to ingest that exact file via put_page, so it lands in
             ~/.gbrain and becomes searchable.
        The file is the source of truth on disk; gbrain's own DB/vectors are the
        indexed copy. Writing a file also means no command-line length cap.
        """
        from pathlib import Path

        transcript = (transcript or "").strip()
        if not transcript:
            raise HermesControlError("This meeting has no transcript to save.")

        feed_dir = Path(
            self.settings.gbrain_feed_dir or (Path.home() / "gbrain-feed")
        )
        # Avoid "meeting-meeting-1001" when the ID already starts with "meeting-".
        bare_id = meeting_id
        if bare_id.lower().startswith("meeting-"):
            bare_id = bare_id[len("meeting-"):]
        slug = f"meeting-{bare_id}"
        try:
            feed_dir.mkdir(parents=True, exist_ok=True)
            file_path = feed_dir / f"{slug}.txt"
            file_path.write_text(
                f"# {title}\nmeeting_id: {meeting_id}\nslug: {slug}\n\n{transcript}\n",
                encoding="utf-8",
            )
        except OSError as exc:
            raise HermesControlError(
                f"Could not write to the gbrain feed folder '{feed_dir}': {exc}. "
                f"Set GBRAIN_FEED_DIR in backend/.env to a writable folder."
            ) from exc

        prompt = (
            f"Ingest the file at '{file_path}' into gbrain now by calling "
            f"put_page with slug/title '{slug}'. Read the file's contents as the "
            "page body and actually call the tool so gbrain indexes it (chunks, "
            "embeddings, FTS5, entity graph). After it is stored, reply with the "
            "page slug and a one-line confirmation."
        )
        try:
            res = self._exec(
                ["chat", "-q", prompt, "--yolo"],
                action="save_to_gbrain",
                timeout=timeout,
            )
        except HermesControlError as exc:
            # The file is on disk in the watch folder; gbrain can still pick it
            # up on its next sync even though the direct ingest call failed.
            return {
                "action": "save_to_gbrain",
                "command": f"write {file_path.name} + put_page {slug}",
                "exit_code": 1,
                "ok": False,
                "file": str(file_path),
                "slug": slug,
                "output": (
                    f"Wrote {file_path}. Hermes ingest could not run ({exc}). "
                    f"The file is in your gbrain feed folder, so gbrain may "
                    f"ingest it on its next sync. Ensure `hermes` is on PATH "
                    f"(HERMES_CLI_PATH)."
                ),
            }
        res["command"] = f"write {file_path.name} + put_page {slug}"
        res["file"] = str(file_path)
        res["slug"] = slug
        return res

    def email_file(
        self,
        to: str,
        subject: str,
        body: str,
        file_path: str,
        timeout: float = 240.0,
    ) -> dict:
        """Email a file as an attachment using `hermes send` (MEDIA: syntax).

        Composio's Gmail tool sends via API and can't attach a local disk file,
        so we use Hermes's native outbound `send` command, which runs locally
        and attaches the file directly via `MEDIA:<path>`. The recipient target
        uses the configurable scheme prefix (default "email:").
        """
        to = (to or "").strip()
        if not to:
            raise HermesControlError("No recipient email address.")
        target = f"{self.settings.hermes_email_to_prefix}{to}"
        # Subject as first line, body, then the attachment directive.
        message = f"{subject}\n\n{body}\n\nMEDIA:{file_path}"
        res = self._exec(
            ["send", "--to", target, message], action="email", timeout=timeout
        )
        res["command"] = f"hermes send --to {target} (email report to {to})"
        res["to"] = to
        return res

    def _exec(self, args: list[str], action: str, timeout: float) -> dict:
        exe = self._resolve_exe()
        cmd = [exe, *args]
        logger.info("Hermes control: %s", " ".join(cmd[:3]) + (" …" if len(cmd) > 3 else ""))
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise HermesControlError(
                f"Hermes executable not found at '{exe}'. Set HERMES_CLI_PATH "
                f"in backend/.env to your hermes binary."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise HermesControlError(
                f"`hermes {args[0]}` timed out after {timeout:.0f}s."
            ) from exc
        out = _clean_terminal_output(proc.stdout or "")
        err = _clean_terminal_output(proc.stderr or "")
        # for chat, don't leak the full message back into the command label
        label = "hermes chat -q …" if action == "chat" else "hermes " + " ".join(args)
        return {
            "action": action,
            "command": label,
            "exit_code": proc.returncode,
            "output": out or err or "(no output)",
            "ok": proc.returncode == 0,
        }
