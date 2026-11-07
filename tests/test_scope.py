"""
Tests for scope enforcement. These are the most important tests in the
project: they prove LabScout refuses out-of-scope and public targets.
"""

import pytest

from labscout.scope import ScopeError, enforce_scope

LAB_ALLOWLIST = ["192.168.56.101", "10.0.0.0/24"]


def test_allowlisted_private_ip_is_accepted():
    result = enforce_scope("192.168.56.101", LAB_ALLOWLIST)
    assert result.resolved_ip == "192.168.56.101"
    assert result.matched_allowlist == "192.168.56.101"


def test_private_ip_inside_allowlisted_cidr_is_accepted():
    result = enforce_scope("10.0.0.55", LAB_ALLOWLIST)
    assert result.resolved_ip == "10.0.0.55"
    assert result.matched_allowlist == "10.0.0.0/24"


def test_public_ip_is_refused_even_if_someone_allowlists_it():
    # Public IPs must be refused by the private-space check regardless.
    with pytest.raises(ScopeError):
        enforce_scope("8.8.8.8", ["8.8.8.8"])


def test_private_ip_not_in_allowlist_is_refused():
    # Private but not on the list -> refused. No silent scope widening.
    with pytest.raises(ScopeError):
        enforce_scope("192.168.56.200", LAB_ALLOWLIST)


def test_empty_allowlist_refuses_everything():
    with pytest.raises(ScopeError):
        enforce_scope("192.168.56.101", [])


def test_another_private_host_outside_scope_is_refused():
    with pytest.raises(ScopeError):
        enforce_scope("172.16.5.5", LAB_ALLOWLIST)


@pytest.mark.parametrize("public", ["1.1.1.1", "93.184.216.34", "203.0.113.7"])
def test_various_public_ips_refused(public):
    with pytest.raises(ScopeError):
        enforce_scope(public, ["0.0.0.0/0"])  # even a wildcard can't allow public
