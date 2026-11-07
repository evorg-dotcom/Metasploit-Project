"""
Tests that the optional validation step blocks unapproved actions:
  * modules not on the allowlist are rejected outright
  * a refused confirmation aborts before anything runs
We never contact a real Metasploit server in these tests.
"""

import pytest

from labscout.scope import enforce_scope
from labscout.validate import MODULE_ALLOWLIST, ValidationError, run_validation

LAB_ALLOWLIST = ["192.168.56.101"]


def _scope():
    return enforce_scope("192.168.56.101", LAB_ALLOWLIST)


def test_module_not_on_allowlist_is_rejected():
    # An arbitrary / dangerous module name must be refused before any connect.
    with pytest.raises(ValidationError):
        run_validation(_scope(), "exploit/multi/handler", confirm=lambda m, t: True)


def test_refused_confirmation_aborts_without_running():
    # Even an allowlisted module must not run if the human says no.
    module = sorted(MODULE_ALLOWLIST)[0]
    result = run_validation(_scope(), module, confirm=lambda m, t: False)
    assert result.ran is False
    assert "Aborted" in result.output


def test_confirmation_receives_module_and_confirmed_target():
    # The confirm callback must be shown the exact module and scoped IP.
    module = sorted(MODULE_ALLOWLIST)[0]
    seen = {}

    def spy(m, t):
        seen["module"] = m
        seen["target"] = t
        return False  # still abort so we never reach the network

    run_validation(_scope(), module, confirm=spy)
    assert seen["module"] == module
    assert seen["target"] == "192.168.56.101"
