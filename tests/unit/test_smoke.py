"""Smoke tests: the package imports, config loads, enums resolve, the CLI runs."""

from __future__ import annotations

from typer.testing import CliRunner

from downlow import __version__
from downlow.cli.app import app
from downlow.config.models import ModelConfig
from downlow.config.settings import Settings
from downlow.domain.enums import RunStatus, SpeakerRole, StageStatus, VoiceSource


def test_version_is_set() -> None:
    assert __version__


def test_settings_load_defaults() -> None:
    s = Settings(anthropic_api_key=None, elevenlabs_api_key=None)
    assert s.summary_model == "claude-sonnet-4-6"
    assert s.max_workers >= 1


def test_model_config_defaults() -> None:
    mc = ModelConfig(id="claude-sonnet-4-6")
    assert mc.max_tokens > 0
    assert mc.effort


def test_enums() -> None:
    assert StageStatus.SUCCEEDED == "succeeded"
    assert RunStatus.PENDING == "pending"
    assert SpeakerRole.HOST == "host"
    assert VoiceSource.CLONED == "cloned"


def test_cli_version() -> None:
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout
