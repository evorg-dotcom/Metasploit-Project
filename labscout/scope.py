"""
scope.py — Target scope enforcement.

This module is the safety core of LabScout. Nothing in the project is
allowed to touch a host unless scope.py has approved it. Two independent
checks must BOTH pass before any address is considered in scope:

  1. The address must resolve to an IP that lives inside RFC 1918 / loopback
     private space (never a public, routable IP).
  2. The address must match an entry in the operator-configured lab
     allowlist (config/lab.yaml).

Public IPs, third-party systems, and anything outside the allowlist are
rejected. The project never auto-discovers hosts or widens scope on its own.

RFC 1918 private ranges and loopback are defined by the Python standard
library `ipaddress` module (is_private / is_loopback), which we rely on
here rather than hand-rolling CIDR math.
Reference: https://docs.python.org/3/library/ipaddress.html
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass


class ScopeError(Exception):
    """Raised whenever a target fails any scope check. Fail closed."""


@dataclass(frozen=True)
class ScopeResult:
    """The outcome of a successful scope check."""
    raw_input: str          # what the operator typed, e.g. "192.168.56.101"
    resolved_ip: str        # the IP we actually validated and will act on
    matched_allowlist: str  # the allowlist entry (host or CIDR) it matched


def _resolve_all_ips(target: str) -> list[ipaddress._BaseAddress]:
    """
    Turn an operator-supplied target into the full list of IPs it maps to.

    Accepts a literal IP (returned as a single-item list) or a hostname. A
    hostname is resolved with getaddrinfo, which returns every address the
    name maps to across IPv4 and IPv6. We return all of them so the caller
    can fail closed if ANY one is out of scope. gethostbyname only returned
    the first IPv4 result, which let a name that also pointed at a public
    address slip through; checking every resolved address closes that gap.
    """
    target = target.strip()
    # Fast path: already a literal IP address.
    try:
        return [ipaddress.ip_address(target)]
    except ValueError:
        pass

    # Otherwise treat it as a hostname and resolve every address it maps to.
    try:
        infos = socket.getaddrinfo(target, None)
    except socket.gaierror as exc:
        raise ScopeError(f"Could not resolve target '{target}': {exc}") from exc

    ips: list[ipaddress._BaseAddress] = []
    seen: set[str] = set()
    for info in infos:
        addr = info[4][0]
        # IPv6 scoped addresses can carry a %zone suffix; drop it for parsing.
        addr = addr.split("%", 1)[0]
        if addr in seen:
            continue
        seen.add(addr)
        try:
            ips.append(ipaddress.ip_address(addr))
        except ValueError:
            continue
    if not ips:
        raise ScopeError(f"Could not resolve target '{target}' to any IP address.")
    return ips


# The exact ranges a real host-only / internal lab network uses. We match
# against these explicitly rather than trusting ipaddress.is_private, because
# is_private also returns True for documentation (RFC 5737, e.g. 203.0.113.0/24)
# and other reserved ranges that are not legitimate lab space. Keeping the set
# tight is the safer default.
_LAB_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),       # RFC 1918
    ipaddress.ip_network("172.16.0.0/12"),    # RFC 1918
    ipaddress.ip_network("192.168.0.0/16"),   # RFC 1918
    ipaddress.ip_network("127.0.0.0/8"),      # loopback
    ipaddress.ip_network("169.254.0.0/16"),   # link-local
    ipaddress.ip_network("fc00::/7"),         # IPv6 unique local
    ipaddress.ip_network("::1/128"),          # IPv6 loopback
    ipaddress.ip_network("fe80::/10"),        # IPv6 link-local
]


def _is_private(ip: ipaddress._BaseAddress) -> bool:
    """
    True only for addresses inside the explicit lab ranges above (RFC 1918,
    loopback, link-local, IPv6 ULA). Public, multicast, documentation, and
    other reserved ranges are all treated as out of scope.
    """
    return any(ip in net for net in _LAB_RANGES)


def _match_allowlist(ip: ipaddress._BaseAddress, allowlist: list[str]) -> str | None:
    """
    Return the allowlist entry the IP matches, or None.

    Each allowlist entry may be a single IP ("192.168.56.101") or a CIDR
    network ("192.168.56.0/24"). The operator controls this list in
    config/lab.yaml; the code never adds to it.
    """
    for entry in allowlist:
        entry = entry.strip()
        if not entry:
            continue
        try:
            network = ipaddress.ip_network(entry, strict=False)
        except ValueError:
            # A malformed allowlist entry is ignored rather than trusted.
            continue
        if ip in network:
            return entry
    return None


def enforce_scope(target: str, allowlist: list[str]) -> ScopeResult:
    """
    The single entry point every tool must call before acting on a target.

    Raises ScopeError if ANY check fails. Returns a ScopeResult only when
    the target is both private AND on the allowlist. This function has no
    side effects and performs no scanning.
    """
    if not allowlist:
        raise ScopeError(
            "Lab allowlist is empty. Refusing to act on any target. "
            "Populate the 'allowlist' field in config/lab.yaml first."
        )

    ips = _resolve_all_ips(target)

    # Fail closed: EVERY address the target resolves to must be in lab space.
    # If a hostname maps to several addresses and any one is public, refuse the
    # whole target rather than acting on the private ones.
    for ip in ips:
        if not _is_private(ip):
            raise ScopeError(
                f"Target '{target}' resolves to {ip}, which is a PUBLIC or "
                f"out-of-scope address. LabScout only operates on private "
                f"(RFC 1918 / loopback) lab addresses. Refusing."
            )

    # Act only on an address that is also on the allowlist. We validated above
    # that every resolved address is private; now require an allowlist match.
    for ip in ips:
        matched = _match_allowlist(ip, allowlist)
        if matched is not None:
            return ScopeResult(
                raw_input=target,
                resolved_ip=str(ip),
                matched_allowlist=matched,
            )

    raise ScopeError(
        f"Target '{target}' ({', '.join(str(i) for i in ips)}) is private but "
        f"is NOT in the configured lab allowlist {allowlist}. Refusing. Add it "
        f"to config/lab.yaml only if it is genuinely your lab VM."
    )
