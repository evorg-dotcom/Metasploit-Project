"""
Tests for the offline advisor and the Markdown report builder. Neither touches
the network; both work on already-parsed findings.
"""

from dataclasses import dataclass

from labscout.ai import ManualAdvisor
from labscout.recon import ReconResult
from labscout.report import build_report


@dataclass
class _Scope:
    raw_input: str = "192.168.56.101"
    resolved_ip: str = "192.168.56.101"
    matched_allowlist: str = "192.168.56.101"


FINDINGS = {
    "192.168.56.101": {
        21: {"state": "open", "name": "ftp", "product": "ProFTPD", "version": "1.3.5"},
        22: {"state": "open", "name": "ssh", "product": "OpenSSH", "version": "6.6.1p1"},
        23: {"state": "closed", "name": "telnet", "product": "", "version": ""},
    }
}


def test_manual_advisor_lists_open_ports_and_notes():
    text = ManualAdvisor().summarise(FINDINGS)
    assert "192.168.56.101" in text
    assert "21/tcp" in text and "22/tcp" in text
    # A closed port should not be reported as open.
    assert "23/tcp" not in text
    # Known services get a neutral learning note.
    assert "ssh_version" in text


def test_manual_advisor_handles_empty_findings():
    assert "No hosts" in ManualAdvisor().summarise({})


def test_report_contains_target_and_services():
    recon = ReconResult(profile="quick", target="192.168.56.101",
                        raw_xml="<xml/>", parsed=FINDINGS)
    md = build_report(_Scope(), recon, "advisor text here")
    assert "# LabScout Report" in md
    assert "192.168.56.101" in md
    assert "ProFTPD" in md
    assert "advisor text here" in md
    assert "Authorized lab use only" in md


def test_report_marks_no_open_ports():
    recon = ReconResult(profile="quick", target="192.168.56.101",
                        raw_xml="<xml/>",
                        parsed={"192.168.56.101": {80: {"state": "closed"}}})
    md = build_report(_Scope(), recon, "none")
    assert "No open ports" in md
