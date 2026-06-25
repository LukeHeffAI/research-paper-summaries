"""Unit tests for the [report] config parsing (F3): title_mode validation.

A typo in ``[report].title_mode`` must error at config-parse time rather than
silently falling through to the templated branch at render time.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from downlow.config.profiles import ConfigError, ReportConfig, load_config

_MINIMAL_PROFILES = """\
[profile]
active_research = "r"
active_output = "o"

[research.r]
research_field = "ML"
research_topic = "t"
research_focus = "f"

[output.o]
document_type = "Literature Review"
"""


def _write_config(tmp_path: Path, report_section: str) -> Path:
    path = tmp_path / "downlow.toml"
    path.write_text(_MINIMAL_PROFILES + report_section, encoding="utf-8")
    return path


def test_load_config_accepts_valid_title_modes(tmp_path: Path) -> None:
    for mode in ("templated", "llm"):
        cfg = load_config(_write_config(tmp_path, f'\n[report]\ntitle_mode = "{mode}"\n'))
        assert cfg.report.title_mode == mode


def test_load_config_defaults_title_mode_when_absent(tmp_path: Path) -> None:
    cfg = load_config(_write_config(tmp_path, ""))  # no [report] section
    assert cfg.report.title_mode == "templated"


def test_load_config_rejects_bad_title_mode(tmp_path: Path) -> None:
    path = _write_config(tmp_path, '\n[report]\ntitle_mode = "templatd"\n')  # typo
    with pytest.raises(ConfigError, match="title_mode"):
        load_config(path)


def test_report_config_model_rejects_bad_title_mode() -> None:
    # The model itself is typed Literal, so a bad value fails validation directly.
    with pytest.raises(ValidationError):
        ReportConfig(title_mode="nonsense")  # type: ignore[arg-type]
