# LabScout

A small, lab-only AI pentesting assistant for a single Metasploitable 3 VM on an isolated host-only network. It is built for a student learning environment. It does safe reconnaissance first, explains what it found in plain language, and writes a report. Any step beyond recon is optional, narrowly scoped to the one confirmed lab target, and requires you to confirm by hand immediately before it runs.

This project is for authorized use against your own equipment only. It will refuse any target that is not a private address, and it will refuse any target that is not on a lab allowlist you configure yourself.

LabScout is the automated front end of a larger learning project: working through the full penetration testing lifecycle against a Metasploitable 3 VM I own. LabScout handles the early, repeatable phases (reconnaissance and advisory) and deliberately stops there. The manual exploitation learning that comes after is written up separately in [`docs/METASPLOITABLE3_LAB_GUIDE.md`](docs/METASPLOITABLE3_LAB_GUIDE.md), and is kept out of the tool on purpose. Built with help from Claude (Anthropic's AI assistant); I reviewed the code and ran the tests myself.

## What was and was not tested

The code in this repository was written and its automated tests were run in a development container. All 31 unit tests pass and `ruff` is clean (see "Tests" below). No scan was performed against any real or virtual machine during development, because there was no Metasploitable 3 VM attached. The recon and validation paths that talk to nmap and Metasploit are genuinely runnable, but they have not been exercised end to end against a live target here. When the README shows an example session, it is clearly labeled as illustrative. You should expect to run it yourself against your own VM to see real output.

## Scope and safety assumptions

The design assumes one locally hosted Metasploitable 3 VM on an isolated host-only network, and nothing else. The following rules are enforced in code, not just documented:

1. The target is never hard-coded. You enter it at runtime and you confirm it before anything happens.
2. Two independent checks must both pass before any action. The target must resolve to an address inside explicit lab ranges (RFC 1918 private space, loopback, or link-local), and it must match an entry in the allowlist you set in `config/lab.yaml`. Public, documentation, and other reserved addresses are rejected. A private address that is not on your allowlist is also rejected.
3. The AI model never builds or runs commands. It only reads structured findings and writes advisory text for you to read. Tool execution goes through constrained runners.
4. Recon is limited to a fixed set of named nmap profiles. There is no arbitrary command execution, and arguments are passed as a list rather than through a shell, so there is no command injection surface.
5. The optional validation step is off unless you pass `--allow-validation`. Even then it will only run a module from a short allowlist, it forces the target back to the confirmed lab IP, and it aborts unless you type a confirmation right before it runs.
6. No stealth, evasion, persistence, destructive actions, credential dumping, lateral movement, data exfiltration, or post-exploitation. The validation step requests a minimal proof only.
7. Every action and every refusal is written to an append-only audit log.

## Curated websites and tools

Every link below was checked during development. Where a license is stated, it is taken from the project's own repository or site. Licenses change, so confirm the current terms yourself before you rely on them.

**Metasploitable 3** — the target VM.
https://github.com/rapid7/metasploitable3
A deliberately vulnerable VM built by Rapid7 for practising against Metasploit. Released under a BSD-style license (see the repository's COPYING file). This is the one and only intended target for this project. Note that the Windows build is based on Windows Server 2008 and must be built locally rather than distributed, per Microsoft licensing.

**Nmap** — reconnaissance engine.
https://nmap.org/  and  https://github.com/nmap/nmap
The scanner LabScout drives for host and service discovery. Licensed under the Nmap Public Source License (NPSL), which the project describes as based on but not identical to GPLv2, and which restricts redistribution inside proprietary products. License text: https://nmap.org/npsl/ . Because the NPSL has redistribution conditions, LabScout treats nmap as an external tool you install yourself rather than bundling it.

**python-nmap** — parsing recon output in Python.
https://pypi.org/project/python-nmap/
A Python library that runs nmap and parses its XML output into Python objects. Used by `recon.py` to turn scan results into structured data. If it is not installed, `recon.py` falls back to Python's standard-library XML parser, so it is recommended but not required.

**Metasploit Framework** — the engine behind the optional validation step.
https://github.com/rapid7/metasploit-framework
The open-source edition is released under a 3-clause BSD license (see the repository's LICENSE file). LabScout never embeds exploit code. The optional validation step connects to your own locally running Metasploit RPC server and asks it to run a named, allowlisted auxiliary module.

**pymetasploit3** — Python bridge to Metasploit RPC.
https://github.com/DanMcInerney/pymetasploit3  and  https://pypi.org/project/pymetasploit3/
A Python 3 library that talks to the Metasploit RPC service (`msfrpcd`). Used by `validate.py` only when you enable validation. It is optional; the recon and reporting paths do not need it.

**OWASP** — background and methodology.
https://owasp.org/
A widely used reference for web application security concepts. Useful for understanding the HTTP services Metasploitable 3 exposes. Listed as a learning resource rather than a code dependency.

Optional AI providers, used only if you set `ai_provider` away from the default:

**OpenAI Python SDK** — https://pypi.org/project/openai/ and https://platform.openai.com/docs . A hosted service that needs an API key. LabScout reads the key from the `OPENAI_API_KEY` environment variable and never stores it.

**Ollama** — https://ollama.com/ and https://github.com/ollama/ollama . Runs open models locally with no external API key. LabScout talks to it over its local HTTP endpoint.

The default provider is `manual`, which uses no model at all. The project is fully usable offline and without any API key.

## Architecture

```
            you type + confirm a target
                      |
                      v
            +-------------------+
            |  scope.py         |  private-range check AND allowlist check
            |  (fail closed)    |  -> rejects everything else
            +-------------------+
                      | ScopeResult (confirmed IP only)
                      v
            +-------------------+     +-------------------+
            |  recon.py         |     |  ai.py            |
            |  fixed nmap       |---->|  advisor reads    |
            |  profiles, no     |     |  findings, writes |
            |  shell            |     |  text (no exec)   |
            +-------------------+     +-------------------+
                      |                       |
                      v                       v
            +-------------------------------------+
            |  report.py  ->  Markdown report     |
            +-------------------------------------+
                      |
                      v   (only with --allow-validation)
            +-------------------+
            |  validate.py      |  module allowlist + RHOSTS re-pinned
            |                   |  + typed confirmation -> your local msfrpcd
            +-------------------+

   audit.py records every action and refusal to an append-only log.
```

The control boundary is `scope.py`. Nothing acts on a target without a `ScopeResult`, and a `ScopeResult` only exists for a target that passed both checks. The model sits off to the side as an advisor and has no path to execution.

## Project files

```
labscout/
  __init__.py        version marker
  scope.py           target scope enforcement (the safety core)
  config.py          loads and validates config/lab.yaml
  recon.py           constrained nmap recon runner
  validate.py        optional, gated Metasploit validation
  ai.py              manual / OpenAI / Ollama advisor
  report.py          Markdown report builder
  audit.py           append-only action log
  orchestrator.py    the CLI that wires it together
config/
  lab.example.yaml   copy to lab.yaml and edit
tests/
  test_scope.py              scope acceptance and rejection
  test_scope_hostname.py     hostname resolves to many IPs; fail closed
  test_validation_guard.py   module allowlist and confirmation gate
  test_recon_argv.py         recon profile and no-shell-injection checks
  test_config.py             config loading and rejection
  test_advisor_and_report.py offline advisor and report rendering
pyproject.toml               packaging, console entry point, lint/test config
requirements.txt
.github/workflows/ci.yml     lint + tests on Python 3.10-3.12
.gitignore
```

## Install

Prerequisites: Python 3.10 or newer, and nmap installed on your system (`sudo apt install nmap` on Debian/Ubuntu, or from https://nmap.org/download ). Metasploit and pymetasploit3 are only needed if you plan to use the optional validation step.

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

```
cp config/lab.example.yaml config/lab.yaml
```

Edit `config/lab.yaml` and set `allowlist` to your Metasploitable 3 VM's host-only IP, for example `192.168.56.101`. Keep the list as tight as you can. `config/lab.yaml` is gitignored so your real setup is not committed.

## Run

Recon and report, using the default offline advisor:

```
python -m labscout.orchestrator --target 192.168.56.101 --profile quick
```

You will be asked to confirm the target before anything runs. The report is written to `labscout_report.md` and actions are logged to `labscout_audit.log`.

To use an AI advisor, set `ai_provider` in the config to `openai` or `ollama`. For OpenAI, export your key first:

```
export OPENAI_API_KEY='...'
```

## Optional validation step

This is off by default. To enable it you need a running Metasploit RPC server and pymetasploit3 installed.

```
pip install pymetasploit3
export MSF_RPC_PASSWORD='choose-a-strong-one'
msfrpcd -P "$MSF_RPC_PASSWORD" -S -a 127.0.0.1 -p 55553
python -m labscout.orchestrator --target 192.168.56.101 --allow-validation
```

You will be shown the allowlisted modules, you pick one, and you must type a confirmation immediately before it runs. The password is read from the environment and is never written to disk.

## Example lab session (illustrative)

The following shows the shape of a run. It is illustrative, not captured from a live scan.

```
$ python -m labscout.orchestrator --target 192.168.56.101 --profile quick

You are about to let LabScout act on: 192.168.56.101
Configured lab allowlist: ['192.168.56.101']
Confirm this is YOUR isolated lab VM and you are authorized [type 'yes' to proceed]: yes
[scope] OK: 192.168.56.101 (matched 192.168.56.101)
[recon] Running profile 'quick'...

Recon summary (manual, no AI model):

Host 192.168.56.101:
  21/tcp   ftp   ProFTPD 1.3.5
      note: FTP is exposed. Metasploitable services commonly allow anonymous
      or weak logins. Learning check: auxiliary/scanner/ftp/ftp_version.
  22/tcp   ssh   OpenSSH 6.6.1p1
      note: SSH is exposed. ... Learning check: auxiliary/scanner/ssh/ssh_version.
  80/tcp   http  Apache httpd 2.4.7

[report] Written to labscout_report.md
```

What a refused, out-of-scope target looks like (this behavior is covered by the tests):

```
$ python -m labscout.orchestrator --target 8.8.8.8
...
[scope] REFUSED: Target '8.8.8.8' resolves to 8.8.8.8, which is a PUBLIC or
out-of-scope address. LabScout only operates on private lab addresses. Refusing.
```

## Tests

```
pytest -q
```

The suite proves the parts that matter most for safety. It checks that allowlisted private targets are accepted, that public addresses are refused even if someone tries to allowlist them, that a private address not on the allowlist is refused, that an empty allowlist refuses everything, that validation modules outside the allowlist are rejected, that a refused confirmation aborts before any network contact, and that recon only builds known nmap profiles and passes the target as a single non-shell argument. As of the last run, all 16 tests pass.

## Limitations

This is a learning MVP, not a professional scanner. The recon profiles are deliberately conservative and will miss things a tuned scan would find. The manual advisor is a small rules engine, not real analysis. The validation step is scaffolding around a handful of version and login scanners, and it is only as reliable as your local Metasploit setup. The scope check protects against pointing the tool at the wrong place, but it cannot verify that your lab is truly isolated at the network level, which is your responsibility.

## Resetting the lab VM

Take a VirtualBox or VMware snapshot of the Metasploitable 3 VM right after you build it and before you test. To reset, restore that snapshot. Because Metasploitable 3 is built locally from the Rapid7 repository rather than distributed as an image, you can also rebuild it from scratch with the project's `build` scripts if a snapshot is not available.

## Extending it safely

If you add a recon profile, keep it in the fixed `RECON_PROFILES` dictionary and avoid aggressive timing and intrusive scripts. If you add a validation module, add its exact name to `MODULE_ALLOWLIST` consciously and keep the list short and reviewable. Do not give the AI advisor any path to execution. Keep the two scope checks in place, and keep the confirmation gate in front of anything that acts on the target. If you ever want to test a different machine, build a separate isolated lab for it and change the allowlist deliberately rather than widening scope at runtime.
