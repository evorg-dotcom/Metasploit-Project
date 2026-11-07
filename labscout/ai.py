"""
ai.py — Pluggable AI advisor with a safe, no-key default.

The model's ONLY job in LabScout is to read structured recon findings and
suggest, in plain English, which services look interesting and what a
learner might investigate next. The model never chooses targets, never
builds commands, and never triggers execution. Its output is advisory text
that a human reads. Tool execution always goes through the constrained
runners with their own allowlists and confirmation gates.

Three providers:
  * ManualAdvisor  (default) - no LLM, no key. A small rules-based
    summariser so the whole project runs offline and for free.
  * OpenAIAdvisor  - reads OPENAI_API_KEY from the environment.
  * OllamaAdvisor  - talks to a local Ollama server, no external key.

API keys are read from the environment only. They are never logged, never
written to disk, and never passed to any other component.
"""

from __future__ import annotations

import json
import os
from typing import Protocol


class Advisor(Protocol):
    def summarise(self, findings: dict) -> str: ...


# ---------------------------------------------------------------------------
# Default: no model required.
# ---------------------------------------------------------------------------
# Maps a service name (as Nmap reports it) to a short, neutral learning note
# and a pointer to the kind of allowlisted check that would confirm it. This
# is deliberately generic education, not an attack recipe.
_SERVICE_NOTES = {
    "ssh": "SSH is exposed. On Metasploitable 3 this often allows weak-"
           "credential logins. Learning check: auxiliary/scanner/ssh/ssh_version.",
    "ftp": "FTP is exposed. Metasploitable services commonly allow anonymous "
           "or weak logins. Learning check: auxiliary/scanner/ftp/ftp_version.",
    "http": "An HTTP service is running. Worth enumerating pages and versions. "
            "Learning check: auxiliary/scanner/http/http_version.",
    "https": "An HTTPS service is running. Note the cert and server version. "
             "Learning check: auxiliary/scanner/http/http_version.",
    "microsoft-ds": "SMB is exposed. A classic enumeration surface on "
                    "Metasploitable 3. Learning check: "
                    "auxiliary/scanner/smb/smb_version.",
    "netbios-ssn": "NetBIOS/SMB is exposed. See the SMB version scanner "
                   "(auxiliary/scanner/smb/smb_version).",
    "telnet": "Telnet is exposed and sends traffic in cleartext. Note the "
              "banner and version. Learning check: "
              "auxiliary/scanner/telnet/telnet_version.",
    "smtp": "An SMTP mail service is running. Worth noting the banner and "
            "whether user enumeration is possible. Learning check: "
            "auxiliary/scanner/smtp/smtp_version.",
    "mysql": "A MySQL database is exposed on the network. Note the version. "
             "Learning check: auxiliary/scanner/mysql/mysql_version.",
    "postgresql": "A PostgreSQL database is exposed. Note the version. "
                  "Learning check: auxiliary/scanner/postgres/postgres_version.",
    "irc": "An IRC service is running. Record the server software and version "
           "string, which identify the build.",
    "vnc": "A VNC remote-desktop service is exposed. Note whether it prompts "
           "for authentication. Learning check: auxiliary/scanner/vnc/vnc_none_auth.",
    "rmiregistry": "A Java RMI registry is exposed. Note the port and that RMI "
                   "endpoints are worth enumerating for versions.",
    "distccd": "A distcc build daemon is exposed. Record that it is present and "
               "its version; it is a known Metasploitable service.",
}


class ManualAdvisor:
    """Rules-based, offline advisor. Always available."""

    def summarise(self, findings: dict) -> str:
        lines: list[str] = ["Recon summary (manual, no AI model):", ""]
        if not findings:
            return "No hosts or open ports were parsed from the scan."
        for host, ports in findings.items():
            lines.append(f"Host {host}:")
            open_ports = {p: i for p, i in ports.items()
                          if (i.get("state") or "") == "open"}
            if not open_ports:
                lines.append("  (no open ports found)")
                continue
            for port, info in sorted(open_ports.items()):
                name = info.get("name") or "unknown"
                product = info.get("product") or ""
                version = info.get("version") or ""
                banner = " ".join(x for x in (product, version) if x)
                lines.append(f"  {port}/tcp  {name}  {banner}".rstrip())
                note = _SERVICE_NOTES.get(name)
                if note:
                    lines.append(f"      note: {note}")
            lines.append("")
        lines.append(
            "Next steps are suggestions only. Any validation step is optional, "
            "runs one allowlisted module against the confirmed lab IP, and "
            "requires you to confirm immediately before it runs."
        )
        return "\n".join(lines)


class OpenAIAdvisor:
    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model

    def summarise(self, findings: dict) -> str:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY not set. Export it, or set ai_provider: manual."
            )
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "openai package not installed. 'pip install openai' or use "
                "ai_provider: manual."
            ) from exc

        client = OpenAI(api_key=api_key)
        prompt = (
            "You are a lab-only teaching assistant for a student practising on "
            "their own isolated Metasploitable 3 VM. Given these Nmap findings "
            "(JSON), explain in plain language which services are interesting "
            "and what the student might learn about each. Do NOT provide exploit "
            "commands or payloads. Keep it to recon interpretation and learning "
            "pointers.\n\n" + json.dumps(findings, indent=2)
        )
        resp = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return resp.choices[0].message.content or "(no response)"


class OllamaAdvisor:
    """
    Talks to Ollama's /api/generate endpoint.

    Two modes, chosen by `host`:
      * Local (default): host = http://127.0.0.1:11434. No key needed. This
        also serves cloud models (e.g. "gemma4:cloud") when the desktop app
        is signed in, because the local server forwards them.
      * Direct cloud: host = https://ollama.com. Requires an API key, read
        from the OLLAMA_API_KEY environment variable and sent as a Bearer
        header. The key is never read from config or written to disk.

    Ref: https://docs.ollama.com/api/introduction.md  and  cloud.md
    """

    def __init__(self, model: str = "llama3.2:3b",
                 host: str = "http://127.0.0.1:11434"):
        self.model = model
        self.host = host.rstrip("/")

    def summarise(self, findings: dict) -> str:
        import urllib.error
        import urllib.request

        prompt = (
            "You are a lab-only teaching assistant for a student practising on "
            "their own isolated Metasploitable 3 VM. Given these Nmap findings "
            "(JSON), explain which services are interesting and what to learn "
            "about each. Do not provide exploit commands or payloads.\n\n"
            + json.dumps(findings, indent=2)
        )
        payload = json.dumps(
            {"model": self.model, "prompt": prompt, "stream": False}
        ).encode()

        headers = {"Content-Type": "application/json"}
        # Only attach a key when talking to a remote host. Localhost needs none.
        api_key = os.environ.get("OLLAMA_API_KEY")
        is_remote = not self.host.startswith(("http://127.0.0.1",
                                              "http://localhost"))
        if is_remote:
            if not api_key:
                raise RuntimeError(
                    f"Host {self.host} is remote but OLLAMA_API_KEY is not set. "
                    f"Export your key, or point ollama_host at localhost and "
                    f"sign the Ollama app in for cloud models."
                )
            headers["Authorization"] = f"Bearer {api_key}"

        req = urllib.request.Request(
            f"{self.host}/api/generate", data=payload, headers=headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Could not reach Ollama at {self.host}: {exc}. Is the Ollama "
                f"app/server running? For local use, start it and try again."
            ) from exc
        return data.get("response", "(no response)")


def build_advisor(provider: str, cfg) -> Advisor:
    if provider == "openai":
        return OpenAIAdvisor(model=cfg.openai_model)
    if provider == "ollama":
        return OllamaAdvisor(model=cfg.ollama_model, host=cfg.ollama_host)
    return ManualAdvisor()
