"""
Tests for config loading and validation. These check that a malformed or
unsafe config is rejected rather than silently accepted.
"""

import pytest

from labscout.config import ConfigError, load_config


def _write(tmp_path, text):
    p = tmp_path / "lab.yaml"
    p.write_text(text)
    return p


def test_valid_config_loads(tmp_path):
    cfg = load_config(_write(tmp_path, """
allowlist:
  - "192.168.56.101"
default_target: "192.168.56.101"
ai_provider: "manual"
msf_port: 55553
"""))
    assert cfg.allowlist == ["192.168.56.101"]
    assert cfg.default_target == "192.168.56.101"
    assert cfg.ai_provider == "manual"
    assert cfg.msf_port == 55553


def test_missing_file_is_rejected(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "does-not-exist.yaml")


def test_empty_allowlist_is_rejected(tmp_path):
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, "allowlist: []\n"))


def test_blank_allowlist_entries_are_dropped(tmp_path):
    # Blank entries must not survive, or they could be treated as entries.
    cfg = load_config(_write(tmp_path, """
allowlist:
  - "   "
  - "192.168.56.101"
  - ""
"""))
    assert cfg.allowlist == ["192.168.56.101"]


def test_all_blank_allowlist_is_rejected(tmp_path):
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, "allowlist:\n  - '  '\n  - ''\n"))


def test_non_integer_msf_port_is_rejected(tmp_path):
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, """
allowlist:
  - "192.168.56.101"
msf_port: "not-a-number"
"""))


def test_unknown_ai_provider_is_rejected(tmp_path):
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, """
allowlist:
  - "192.168.56.101"
ai_provider: "definitely-not-a-provider"
"""))
