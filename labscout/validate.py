"""
validate.py — Optional, gated vulnerability validation.

This module is OFF by default. It exists so that, after recon, you can
confirm whether a specific known-vulnerable service on your Metasploitable 3
VM actually responds as expected. It does this by delegating to YOUR OWN
locally installed Metasploit Framework through its RPC API (pymetasploit3).
It contains no exploit code of its own; it only selects a published,
framework-provided module by name from a fixed allowlist and asks the
framework to run it against the one confirmed lab IP.

Every one of these safety properties is enforced here:

  * Module allowlist. Only module names in MODULE_ALLOWLIST may be used.
    An arbitrary module name from the model or the user is rejected.
  * Target re-pinning. RHOSTS is forced to scope.resolved_ip. A module
    cannot be pointed anywhere else.
  * Human confirmation. run_validation() calls a confirm() callback and
    aborts unless it returns True. The orchestrator wires this to a typed
    confirmation immediately before execution.
  * Audit logging. The caller logs the attempt and the outcome.
  * No post-exploitation. We request a minimal proof only. We never open
    interactive sessions, pivot, dump credentials, or persist.

pymetasploit3: https://pypi.org/project/pymetasploit3/
               https://github.com/DanMcInerney/pymetasploit3
Metasploit Framework: https://github.com/rapid7/metasploit-framework (BSD-3-clause)

NOTE: This is lab-only validation scaffolding. It assumes a running msfrpcd
and an isolated Metasploitable 3 target. Nothing here should ever be pointed
at a system you do not own and control.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass

from .scope import ScopeResult

# ---------------------------------------------------------------------------
# The ONLY modules LabScout may ask the framework to run. These are all
# well-documented auxiliary/scanner-style checks matched to services that
# Metasploitable 3 ships deliberately. Keep this list short and auditable.
# Extend it consciously; do not let the model or config append to it.
# ---------------------------------------------------------------------------
MODULE_ALLOWLIST: set[str] = {
    # Lightweight service/version checks and login scanners aimed at the
    # intentionally-weak services on Metasploitable 3.
    "auxiliary/scanner/ssh/ssh_version",
    "auxiliary/scanner/ftp/ftp_version",
    "auxiliary/scanner/smb/smb_version",
    "auxiliary/scanner/http/http_version",
}


class ValidationError(Exception):
    pass


@dataclass
class ValidationResult:
    module: str
    target: str
    output: str
    ran: bool


ConfirmFn = Callable[[str, str], bool]  # (module, target) -> proceed?


def _connect(host: str, port: int):
    """
    Connect to a locally running Metasploit RPC server. Password comes from
    the MSF_RPC_PASSWORD environment variable; it is never read from config
    or hard-coded.
    """
    password = os.environ.get("MSF_RPC_PASSWORD")
    if not password:
        raise ValidationError(
            "MSF_RPC_PASSWORD is not set. Start msfrpcd with a password and "
            "export it, e.g.:\n"
            "  export MSF_RPC_PASSWORD='choose-a-strong-one'\n"
            "  msfrpcd -P \"$MSF_RPC_PASSWORD\" -S -a 127.0.0.1 -p 55553"
        )
    try:
        from pymetasploit3.msfrpc import MsfRpcClient
    except ImportError as exc:
        raise ValidationError(
            "pymetasploit3 is not installed. 'pip install pymetasploit3' to "
            "enable the optional validation step."
        ) from exc

    try:
        return MsfRpcClient(password, server=host, port=port, ssl=False)
    except Exception as exc:  # pragma: no cover - needs a live server
        raise ValidationError(
            f"Could not reach Metasploit RPC at {host}:{port}: {exc}"
        ) from exc


def run_validation(
    scope: ScopeResult,
    module: str,
    confirm: ConfirmFn,
    host: str = "127.0.0.1",
    port: int = 55553,
) -> ValidationResult:
    """
    Run a single allowlisted module against the confirmed lab target, but
    ONLY after the confirm() callback returns True.

    Safety order of operations:
      1. Reject any module not on MODULE_ALLOWLIST.
      2. Ask for human confirmation for this exact (module, target).
      3. Force RHOSTS to the scope-approved IP.
      4. Execute and capture output. No sessions, no persistence.
    """
    if module not in MODULE_ALLOWLIST:
        raise ValidationError(
            f"Module '{module}' is not on the allowlist. "
            f"Allowed: {sorted(MODULE_ALLOWLIST)}"
        )

    # Human-in-the-loop gate. Abort unless explicitly approved.
    if not confirm(module, scope.resolved_ip):
        return ValidationResult(module=module, target=scope.resolved_ip,
                                output="Aborted by operator at confirmation.",
                                ran=False)

    client = _connect(host, port)

    # Allowlist names look like "auxiliary/scanner/ssh/ssh_version".
    # pymetasploit3 wants the type ("auxiliary") and the remaining path
    # ("scanner/ssh/ssh_version") separately.
    mtype, mpath = module.split("/", 1)
    mod = client.modules.use(mtype, mpath)

    # Re-pin the target. The module physically cannot be aimed elsewhere.
    mod["RHOSTS"] = scope.resolved_ip

    # Execute. We read back the console output as our minimal proof of impact.
    try:
        result = mod.execute()
    except Exception as exc:  # pragma: no cover - needs a live server
        raise ValidationError(f"Module execution failed: {exc}") from exc

    return ValidationResult(
        module=module,
        target=scope.resolved_ip,
        output=str(result),
        ran=True,
    )
