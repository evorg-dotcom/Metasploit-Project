"""
config.py — Load and validate the operator's lab configuration.

The lab target is never hard-coded. The operator declares it in
config/lab.yaml, and must confirm it interactively at runtime (see
orchestrator.py). This module only loads and sanity-checks the file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


class ConfigError(Exception):
    """Raised when the lab config is missing or malformed."""


@dataclass
class LabConfig:
    allowlist: list[str] = field(default_factory=list)
    # Default target is only a convenience prompt value; it must still pass
    # scope enforcement and must still be confirmed by the operator.
    default_target: str | None = None
    # AI provider: "manual" (no model, default), "openai", or "ollama".
    ai_provider: str = "manual"
    openai_model: str = "gpt-4o-mini"
    ollama_model: str = "llama3.2:3b"
    ollama_host: str = "http://127.0.0.1:11434"
    # Metasploit RPC connection (only used if the operator enables the
    # optional validation step). Password comes from an env var, never here.
    msf_host: str = "127.0.0.1"
    msf_port: int = 55553


def load_config(path: str | os.PathLike) -> LabConfig:
    p = Path(path)
    if not p.exists():
        raise ConfigError(
            f"Config file not found: {p}. Copy config/lab.example.yaml to "
            f"config/lab.yaml and edit it for your lab."
        )
    try:
        raw = yaml.safe_load(p.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Could not parse {p}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"{p} must contain a YAML mapping at the top level.")

    allowlist = raw.get("allowlist", [])
    if not isinstance(allowlist, list):
        raise ConfigError(
            f"{p} 'allowlist' must be a YAML list of lab IPs/CIDRs."
        )
    # Drop blanks and surrounding whitespace so a stray empty item can never
    # be treated as a (matchless) entry downstream.
    clean_allowlist = [str(x).strip() for x in allowlist if str(x).strip()]
    if not clean_allowlist:
        raise ConfigError(
            f"{p} must define a non-empty 'allowlist' list of lab IPs/CIDRs."
        )

    try:
        msf_port = int(raw.get("msf_port", 55553))
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{p} 'msf_port' must be an integer: {exc}") from exc

    cfg = LabConfig(
        allowlist=clean_allowlist,
        default_target=raw.get("default_target"),
        ai_provider=str(raw.get("ai_provider", "manual")).lower(),
        openai_model=str(raw.get("openai_model", "gpt-4o-mini")),
        ollama_model=str(raw.get("ollama_model", "llama3.2:3b")),
        ollama_host=str(raw.get("ollama_host", "http://127.0.0.1:11434")),
        msf_host=str(raw.get("msf_host", "127.0.0.1")),
        msf_port=msf_port,
    )

    if cfg.ai_provider not in {"manual", "openai", "ollama"}:
        raise ConfigError(
            f"ai_provider must be one of: manual, openai, ollama "
            f"(got '{cfg.ai_provider}')."
        )
    return cfg
