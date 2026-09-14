# Metasploit-Project
A Ongoing Project that goes through each stage of a Penetration Test!
# 🔐 Penetration Testing Lifecycle Lab

## 📌 Overview
This project demonstrates a full penetration testing engagement using a Metaspolitable lab environment.

## 🧭 Methodology
- Reconnaissance
- Scanning & Enumeration
- Exploitation
- Privilege Escalation
- Post-Exploitation
- Reporting

## 🛠 Tools Used
- Nmap
- Burp Suite
- Gobuster
- Nikto

## 🎯 Target
Metaspolitable3 (local lab)

## 🚨 Key Findings
- SQL Injection vulnerability
- Directory exposure
- Weak authentication

## 🧠 Defensive Insight
Includes detection strategies using SIEM tools like Splunk and Azure Sentinel.

## 🧰 Automation Scripts
[`scripts/`](scripts) has a set of bash helpers for driving Metasploit
through the lab workflow above - workspace setup, nmap recon + import,
listener/payload generation, session management, loot collection, and a
CSV/HTML report export. See [`docs/SCRIPTS.md`](docs/SCRIPTS.md) for a
breakdown of what each one does and how to run it.
