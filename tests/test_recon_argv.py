"""
Tests that recon only ever builds allowlisted nmap argument lists against the
scoped IP, and refuses unknown profiles. We do not actually run nmap here.
"""

import pytest

from labscout.recon import RECON_PROFILES, ReconError, _build_argv


def test_known_profile_builds_expected_argv():
    argv = _build_argv("quick", "192.168.56.101")
    assert argv[0] == "nmap"
    assert argv[-1] == "192.168.56.101"
    assert "-oX" in argv  # structured XML output requested


def test_unknown_profile_is_rejected():
    with pytest.raises(ReconError):
        _build_argv("everything-aggressive", "192.168.56.101")


def test_target_is_last_arg_and_not_shell_interpolated():
    # The target is passed as its own argv element (list form), so a value
    # like this cannot inject a second command via a shell.
    argv = _build_argv("quick", "192.168.56.101; rm -rf /")
    assert argv[-1] == "192.168.56.101; rm -rf /"
    # It is a single element; subprocess(shell=False) treats it as one arg.
    assert argv.count("192.168.56.101; rm -rf /") == 1


def test_no_profile_uses_aggressive_timing():
    for name, flags in RECON_PROFILES.items():
        assert "-T5" not in flags, f"{name} should not use -T5 aggressive timing"
