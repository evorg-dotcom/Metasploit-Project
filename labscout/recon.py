"""
recon.py — Safe reconnaissance via a constrained Nmap wrapper.

Design rule: the AI model never invents or executes shell commands. Recon is
limited to a small, fixed set of named "profiles". Each profile maps to an
explicit, hard-coded list of Nmap arguments that this module controls. The
only variable ever passed through is the target, and that target has already
been approved by scope.enforce_scope() before it reaches here.

We build the argument list ourselves and hand it to subprocess as a LIST
(never a shell string), so there is no shell interpolation and no command
injection surface. Timing/aggression is kept conservative.

Nmap:        https://nmap.org/  (Nmap Public Source License, https://nmap.org/npsl/)
python-nmap: https://pypi.org/project/python-nmap/  (parses Nmap XML into Python)
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

from .scope import ScopeResult

# ---------------------------------------------------------------------------
# Recon profiles. These are the ONLY nmap invocations LabScout can make.
# The {target} placeholder is filled with an already-scope-checked IP.
# No profile uses -O/-sS requiring extra privilege by default, no NSE
# "intrusive"/"exploit" categories, nothing destructive.
# ---------------------------------------------------------------------------
RECON_PROFILES: dict[str, list[str]] = {
    # Quick TCP connect scan of the common ports, with service/version.
    "quick": ["-sT", "-sV", "--top-ports", "100", "-T3", "-Pn"],
    # Fuller service/version sweep across all TCP ports (slower).
    "services": ["-sT", "-sV", "-p-", "-T3", "-Pn"],
    # Safe default scripts only (NSE "default" category == -sC). The "safe"
    # script set avoids intrusive checks.
    "safe-scripts": ["-sT", "-sV", "-sC", "--script", "safe", "-T3", "-Pn"],
}


class ReconError(Exception):
    pass


@dataclass
class ReconResult:
    profile: str
    target: str
    raw_xml: str
    parsed: dict  # host -> {port -> {state, name, product, version}}


def nmap_available() -> bool:
    return shutil.which("nmap") is not None


def _build_argv(profile: str, target_ip: str) -> list[str]:
    if profile not in RECON_PROFILES:
        raise ReconError(
            f"Unknown recon profile '{profile}'. "
            f"Allowed: {sorted(RECON_PROFILES)}"
        )
    # XML to stdout (-oX -) so we can parse structured results.
    return ["nmap", *RECON_PROFILES[profile], "-oX", "-", target_ip]


def _parse_xml(xml_text: str) -> dict:
    """
    Parse Nmap XML with python-nmap if present, else a minimal stdlib parse.
    Returns {ip: {port: {...}}}.
    """
    try:
        import nmap  # python-nmap

        scanner = nmap.PortScanner()
        scanner.analyse_nmap_xml_scan(xml_text)
        out: dict = {}
        for host in scanner.all_hosts():
            ports = {}
            for proto in scanner[host].all_protocols():
                for port in scanner[host][proto]:
                    info = scanner[host][proto][port]
                    ports[port] = {
                        "state": info.get("state"),
                        "name": info.get("name"),
                        "product": info.get("product"),
                        "version": info.get("version"),
                    }
            out[host] = ports
        return out
    except Exception:
        # Fallback parse so the tool still works without python-nmap. Prefer
        # defusedxml (hardened against XML entity-expansion attacks); fall back
        # to the stdlib parser if it is not installed. The XML here is produced
        # by our own nmap subprocess, but parsing defensively costs nothing.
        try:
            from defusedxml.ElementTree import ParseError, fromstring
        except ImportError:
            from xml.etree.ElementTree import (
                ParseError,  # noqa: S405
                fromstring,  # noqa: S405
            )

        out = {}
        try:
            # defusedxml is used when available (see the import above); the
            # stdlib fallback parses our own nmap output, not arbitrary input.
            root = fromstring(xml_text)  # noqa: S314
        except ParseError:
            return out
        for host in root.findall("host"):
            addr_el = host.find("address")
            if addr_el is None:
                continue
            ip = addr_el.get("addr", "unknown")
            ports = {}
            for port in host.findall("./ports/port"):
                portid = int(port.get("portid", "0"))
                state_el = port.find("state")
                svc_el = port.find("service")
                ports[portid] = {
                    "state": state_el.get("state") if state_el is not None else None,
                    "name": svc_el.get("name") if svc_el is not None else None,
                    "product": svc_el.get("product") if svc_el is not None else None,
                    "version": svc_el.get("version") if svc_el is not None else None,
                }
            out[ip] = ports
        return out


def run_recon(scope: ScopeResult, profile: str = "quick", timeout: int = 1800) -> ReconResult:
    """
    Run a named recon profile against an already-scope-checked target.

    `scope` must be the ScopeResult returned by scope.enforce_scope(). We use
    scope.resolved_ip, not any raw user string, so we scan exactly what was
    validated.
    """
    if not nmap_available():
        raise ReconError(
            "nmap not found on PATH. Install it (e.g. 'sudo apt install nmap')."
        )

    argv = _build_argv(profile, scope.resolved_ip)
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            shell=False,  # explicit: never use a shell
        )
    except subprocess.TimeoutExpired as exc:
        raise ReconError(f"nmap timed out after {timeout}s") from exc

    if proc.returncode != 0 and not proc.stdout.strip():
        raise ReconError(f"nmap failed: {proc.stderr.strip()}")

    parsed = _parse_xml(proc.stdout)
    return ReconResult(
        profile=profile,
        target=scope.resolved_ip,
        raw_xml=proc.stdout,
        parsed=parsed,
    )
