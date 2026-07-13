"""
Application configuration.

Everything intentional about the system is wired here. Per the spec, the
*only* external intelligence dependency that should be configurable is the
connection to Hermes — so the LLM provider, endpoint and model live here and
nowhere else. Business logic never reads these directly; it depends on the
adapter interfaces instead.
"""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Find the .env robustly. It normally lives at backend/.env (config.py is at
# backend/app/core/config.py -> parents[2] == backend/). We also check the
# project root and the current working directory, and tolerate the Windows
# "save as .env -> actually .env.txt" trap. The first existing file wins.
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_PROJECT_ROOT = _BACKEND_DIR.parent


def _discover_env_file() -> Path:
    candidates = [
        _BACKEND_DIR / ".env",
        _BACKEND_DIR / ".env.txt",      # Explorer hides extensions; common trap
        _PROJECT_ROOT / ".env",
        Path.cwd() / ".env",
    ]
    for c in candidates:
        if c.exists():
            return c
    return _BACKEND_DIR / ".env"  # default (may not exist yet)


_ENV_FILE = _discover_env_file()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore"
    )

    # --- App ---
    app_name: str = "Project Governance Brain"
    environment: Literal["dev", "prod", "test"] = "dev"
    api_prefix: str = ""

    # --- Storage (structured) ---
    # Defaults to SQLite so the project runs with zero infrastructure.
    # Point at Postgres in production, e.g.
    #   postgresql+psycopg2://user:pass@db:5432/governance
    database_url: str = "sqlite:///./governance_brain.db"

    # --- Vector memory ---
    # The vector backend GBrain uses. "local" is an in-process numpy store so
    # the system runs offline; swap to qdrant / chroma / pgvector in prod.
    vector_backend: Literal["local", "qdrant", "chroma", "pgvector"] = "local"
    vector_dim: int = 256
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "transcript_chunks"

    # --- Hermes (reasoning) — the ONLY configurable intelligence dependency ---
    # provider chooses which HermesClient adapter is constructed.
    #   local  -> deterministic, dependency-free reasoning (good for dev/CI)
    #   hermes -> the real installed Hermes service over HTTP
    #   openai -> any OpenAI-compatible Chat Completions endpoint
    #   ollama -> a local Ollama server
    hermes_provider: Literal[
        "local", "hermes", "hermes_cli", "hermes_gateway", "hermes_api", "openai", "ollama"
    ] = "local"
    hermes_base_url: str = "http://localhost:8088"
    hermes_api_key: str = ""
    hermes_model: str = "hermes-default"
    hermes_timeout_seconds: float = 60.0

    # Hermes API Server gateway (the recommended integration). Run
    # `hermes gateway setup`, enable the "API Server" platform, and fill these:
    #   url            base URL the gateway listens on
    #   path           the chat/message endpoint
    #   api_key        bearer token if the gateway requires one
    #   message_field  request JSON field that carries the user's message
    #   response_field dot-path to the reply in the response JSON (e.g. data.reply)
    hermes_gateway_url: str = "http://localhost:8765"
    hermes_gateway_path: str = "/chat"
    hermes_gateway_api_key: str = ""
    hermes_gateway_message_field: str = "message"
    hermes_gateway_response_field: str = "response"

    # CLI provider: run a locally-installed Hermes executable as a subprocess.
    #   hermes_cli_path      path to the .exe (or a Windows .lnk shortcut)
    #   hermes_cli_args      arg template; "{prompt}" is replaced when not stdin
    #   hermes_cli_use_stdin pipe the prompt to stdin (True) or pass as arg
    hermes_cli_path: str = ""
    hermes_cli_args: str = ""
    hermes_cli_use_stdin: bool = True

    # Agentic mode: when True, the user's question is sent to Hermes verbatim and
    # Hermes does its own retrieval (its gbrain) and tools (composio mail, etc.).
    # The app does NOT add RAG context or intercept mail. Auto-applies to the
    # 'hermes' and 'hermes_cli' providers; set False to force app-side RAG.
    hermes_agentic: bool = True

    # --- Microsoft 365 (Outlook mail + Teams) via Microsoft Graph ---
    # All secrets come from the environment / .env — never hard-coded.
    # Create an Azure AD app registration and grant application permissions
    # Mail.Read, Mail.Send, Chat.ReadWrite (admin consent), then fill these in.
    graph_tenant_id: str = ""
    graph_client_id: str = ""
    graph_client_secret: str = ""
    # Mailbox the app acts on (UPN/email), e.g. "you@contoso.com".
    graph_default_user: str = ""

    @property
    def graph_enabled(self) -> bool:
        return bool(
            self.graph_tenant_id
            and self.graph_client_id
            and self.graph_client_secret
            and self.graph_default_user
        )

    # --- Composio (managed Gmail / Outlook / Teams / Calendar tools) ---
    # The API key comes from the environment / .env — never hard-coded.
    # Get it from the Composio dashboard. The entity id groups a user's
    # connected accounts ("default" unless you created a custom entity).
    composio_api_key: str = ""
    composio_entity_id: str = "default"
    # Action slugs are resolved live against Composio. These are sensible
    # defaults; if your dashboard shows different names, override here (or
    # discover them at runtime via GET /comms/actions?app=<app>).
    composio_gmail_fetch: str = "GMAIL_FETCH_EMAILS"
    composio_gmail_send: str = "GMAIL_SEND_EMAIL"
    composio_gcal_events: str = "GOOGLECALENDAR_EVENTS_LIST"
    composio_outlook_fetch: str = "OUTLOOK_LIST_MESSAGES"
    composio_outlook_send: str = "OUTLOOK_OUTLOOK_SEND_EMAIL"
    composio_outlook_events: str = "OUTLOOK_LIST_EVENTS"

    @property
    def composio_enabled(self) -> bool:
        return bool(self.composio_api_key)

    # --- Generated reports folder (for "email this report via Hermes") ---
    # PDFs are written here so Hermes can attach them when emailing. Default is
    # ~/governance-reports.
    reports_dir: str = ""
    # `hermes send` target prefix for email — it uses "<platform>:<dest>", e.g.
    # "email:you@example.com". Override if your Hermes uses a different scheme.
    hermes_email_to_prefix: str = "email:"

    # --- gbrain (Hermes memory) ingest folder ---
    # When you click "Save to gbrain", the meeting is written as a file here and
    # Hermes ingests it (put_page) into its store at ~/.gbrain. Default is
    # ~/gbrain-feed (on Windows: C:\Users\<you>\gbrain-feed) — the folder gbrain
    # already watches. Override if yours differs.
    gbrain_feed_dir: str = ""

    # --- GStack Review Skill ---
    gstack_dir: str = ""

    # --- CORS ---
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor used as a FastAPI dependency."""
    return Settings()
