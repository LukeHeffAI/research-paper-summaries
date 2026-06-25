"""Application settings — the single place the environment is read.

Replaces the legacy scattered ``os.getenv`` calls and module-level globals.
Secrets are optional at load time and validated where they are used (Phase 1),
so the package imports cleanly in CI and tests without real credentials.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings, sourced from the environment / ``.env``."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Secrets (validated at point of use in Phase 1) ---
    anthropic_api_key: str | None = None
    elevenlabs_api_key: str | None = None

    # --- Infra ---
    database_url: str = "sqlite:///./data/downlow.db"
    data_dir: Path = Path("./data")

    # --- Audio assets (F4) ---
    # Where the NARRATE mixer resolves music/sfx cue files. Defaults to the
    # committed repo ``assets/audio/`` (shipped placeholder intro/outro/sting/bed);
    # override (ASSETS_DIR) to a ``$DATA_DIR`` path for your own curated theme.
    assets_dir: Path = Path("./assets/audio")

    # --- Config file (typed application config: profiles + summary model) ---
    # The ONLY filesystem pointer Settings holds for the config-file layer; the
    # composition root passes this to ``config.profiles.load_config``. ``core``
    # never sees the path -- it receives the parsed, typed config.
    config_file: Path = Path("./config/downlow.toml")

    # --- Models (per-stage ModelConfig refinement arrives in Phase 1) ---
    summary_model: str = "claude-sonnet-4-6"
    narration_model: str = "claude-sonnet-4-6"

    # --- LLM transport (wired into the Anthropic adapter) ---
    # Worst-case wall-clock is request_timeout x (max_retries + 1) since the SDK
    # retries timeouts and connection errors too; keep request_timeout modest when
    # max_retries is high (batch runs). Defaults: 2 retries, 600s timeout.
    request_timeout: float = 600.0
    max_retries: int = 2

    # --- Concurrency ---
    max_workers: int = 4
