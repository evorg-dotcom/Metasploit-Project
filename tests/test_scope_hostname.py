"""
Tests for hostname resolution in scope enforcement. A hostname can map to more
than one address, so scope must check every one and fail closed if any is out
of lab scope. We monkeypatch the resolver so no real DNS lookup happens.
"""

import socket

import pytest

from labscout import scope as scope_mod
from labscout.scope import ScopeError, enforce_scope

ALLOWLIST = ["192.168.56.101"]


def _fake_getaddrinfo(addrs):
    """Build a getaddrinfo replacement that returns the given IP strings."""
    def _inner(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, 0)) for a in addrs]
    return _inner


def test_hostname_resolving_to_allowlisted_private_ip_is_accepted(monkeypatch):
    monkeypatch.setattr(scope_mod.socket, "getaddrinfo",
                        _fake_getaddrinfo(["192.168.56.101"]))
    result = enforce_scope("my-lab-vm.local", ALLOWLIST)
    assert result.resolved_ip == "192.168.56.101"


def test_hostname_with_any_public_address_is_refused(monkeypatch):
    # Resolves to a private allowlisted IP AND a public one -> refuse the lot.
    monkeypatch.setattr(scope_mod.socket, "getaddrinfo",
                        _fake_getaddrinfo(["192.168.56.101", "8.8.8.8"]))
    with pytest.raises(ScopeError):
        enforce_scope("sneaky.example.com", ALLOWLIST)


def test_hostname_resolving_only_to_unlisted_private_is_refused(monkeypatch):
    monkeypatch.setattr(scope_mod.socket, "getaddrinfo",
                        _fake_getaddrinfo(["192.168.56.200"]))
    with pytest.raises(ScopeError):
        enforce_scope("other-vm.local", ALLOWLIST)


def test_unresolvable_hostname_is_refused(monkeypatch):
    def _boom(host, port, *args, **kwargs):
        raise socket.gaierror("name resolution failed")
    monkeypatch.setattr(scope_mod.socket, "getaddrinfo", _boom)
    with pytest.raises(ScopeError):
        enforce_scope("nope.invalid", ALLOWLIST)
