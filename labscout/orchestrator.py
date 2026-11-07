"""
orchestrator.py — The CLI that drives a LabScout session.

Flow (recon-first, human-gated):
  1. Load config and build the lab allowlist.
  2. Ask the operator for the target and make them confirm it.
  3. Enforce scope (private + allowlisted) or abort.
  4. Run safe recon.
  5. Summarise findings (manual rules engine or an AI advisor).
  6. ONLY if --allow-validation was passed: offer one allowlisted validation
     module and require a second, typed confirmation immediately before it runs.
  7. Write a report.

Nothing in steps 4-7 ever runs against anything but the single confirmed,
in-scope IP.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

from . import __version__
from .ai import build_advisor
from .audit import AuditLog
from .config import ConfigError, load_config
from .recon import ReconError, run_recon
from .report import build_report
from .scope import ScopeError, enforce_scope
from .validate import MODULE_ALLOWLIST, ValidationError, run_validation


def _confirm(prompt: str) -> bool:
    """Require the operator to type 'yes' exactly. Anything else is a no."""
    try:
        answer = input(f"{prompt} [type 'yes' to proceed]: ").strip().lower()
    except EOFError:
        return False
    return answer == "yes"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="labscout",
        description="Lab-only, recon-first assistant for an isolated "
                    "Metasploitable 3 VM. Authorized use only.",
    )
    parser.add_argument("--config", default="config/lab.yaml",
                        help="Path to lab config (default: config/lab.yaml)")
    parser.add_argument("--target", default=None,
                        help="Target IP/host (must be in the lab allowlist)")
    parser.add_argument("--profile", default="quick",
                        choices=["quick", "services", "safe-scripts"],
                        help="Recon profile (default: quick)")
    parser.add_argument("--report", default="labscout_report.md",
                        help="Where to write the Markdown report")
    parser.add_argument("--allow-validation", action="store_true",
                        help="Enable the optional, gated validation step")
    parser.add_argument("--version", action="version",
                        version=f"LabScout {__version__}")
    args = parser.parse_args(argv)

    # One id for this whole run, stamped on every audit line.
    session_id = uuid.uuid4().hex[:12]
    audit = AuditLog(session=session_id)
    print("LabScout — authorized lab use only. Single isolated "
          "Metasploitable 3 VM.")
    print(f"[session] {session_id}")

    # 1. Config
    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"[config] {exc}", file=sys.stderr)
        return 2

    # 2. Target selection + confirmation
    target = args.target or cfg.default_target
    if not target:
        try:
            target = input("Enter the lab target IP: ").strip()
        except EOFError:
            print("[scope] No target provided.", file=sys.stderr)
            return 2

    print(f"\nYou are about to let LabScout act on: {target}")
    print(f"Configured lab allowlist: {cfg.allowlist}")
    if not _confirm("Confirm this is YOUR isolated lab VM and you are authorized"):
        print("[scope] Not confirmed. Aborting.", file=sys.stderr)
        audit.record("target_not_confirmed", target=target)
        return 1

    # 3. Scope enforcement
    try:
        scope = enforce_scope(target, cfg.allowlist)
    except ScopeError as exc:
        print(f"[scope] REFUSED: {exc}", file=sys.stderr)
        audit.record("scope_refused", target=target, reason=str(exc))
        return 1
    audit.record("scope_ok", target=target, resolved=scope.resolved_ip,
                 matched=scope.matched_allowlist)
    print(f"[scope] OK: {scope.resolved_ip} (matched {scope.matched_allowlist})")

    # 4. Recon
    print(f"[recon] Running profile '{args.profile}'...")
    try:
        recon_result = run_recon(scope, profile=args.profile)
    except ReconError as exc:
        print(f"[recon] {exc}", file=sys.stderr)
        audit.record("recon_failed", target=scope.resolved_ip, reason=str(exc))
        return 1
    audit.record("recon_ok", target=scope.resolved_ip, profile=args.profile,
                 hosts=list(recon_result.parsed.keys()))

    # 5. Advisor summary
    advisor = build_advisor(cfg.ai_provider, cfg)
    try:
        advisor_text = advisor.summarise(recon_result.parsed)
    except Exception as exc:
        advisor_text = f"(advisor unavailable: {exc})"
    print("\n" + advisor_text + "\n")

    # 6. Optional validation (only if explicitly enabled)
    validation_results = []
    if args.allow_validation:
        print("[validate] Optional validation is enabled.")
        print(f"[validate] Allowlisted modules: {sorted(MODULE_ALLOWLIST)}")
        try:
            chosen = input(
                "Enter one allowlisted module to run (or blank to skip): "
            ).strip()
        except EOFError:
            chosen = ""
        if chosen:
            def confirm_fn(module: str, tgt: str) -> bool:
                return _confirm(
                    f"About to run {module} against {tgt}. This is the last "
                    f"check before execution"
                )
            audit.record("validation_requested", module=chosen,
                         target=scope.resolved_ip)
            try:
                vres = run_validation(
                    scope, chosen, confirm_fn,
                    host=cfg.msf_host, port=cfg.msf_port,
                )
                validation_results.append(vres)
                audit.record("validation_done", module=chosen,
                             target=scope.resolved_ip, ran=vres.ran)
            except ValidationError as exc:
                print(f"[validate] {exc}", file=sys.stderr)
                audit.record("validation_error", module=chosen,
                             target=scope.resolved_ip, reason=str(exc))

    # 7. Report
    report_md = build_report(scope, recon_result, advisor_text, validation_results)
    Path(args.report).write_text(report_md, encoding="utf-8")
    print(f"[report] Written to {args.report}")
    audit.record("report_written", path=args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
