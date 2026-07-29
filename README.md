```markdown
# ⚡ AltaXploit C2 Framework ⚡

### *Advanced Red Team Command & Control Infrastructure*

![Alta-Tracker Screenshot](image1.png)

<p align="center">
  <a href="https://github.com/AltaXploit"><img src="https://img.shields.io/badge/GitHub-AltaXploit-red?style=flat-square&logo=github"></a>
  <a href="https://www.alwaz.co.uk"><img src="https://img.shields.io/badge/Website-alwaz.co.uk-blue?style=flat-square&logo=google-chrome"></a>
  <a href="#"><img src="https://img.shields.io/badge/License-MIT-green?style=flat-square"></a>
  <a href="#"><img src="https://img.shields.io/badge/Platform-Linux%20%7C%20Kali-lightgrey?style=flat-square"></a>
  <a href="#"><img src="https://img.shields.io/badge/Python-3.8%2B-yellow?style=flat-square&logo=python"></a>
</p>

---

## 🧭 Table of Contents
- [🌟 Overview](#-overview)
- [🔥 Key Features](#-key-features)
- [💻 Command Reference & Screenshot](#-command-reference--screenshot)
- [🚀 Installation & Setup Guide](#-installation--setup-guide)
- [🔌 Port Architecture & Network Layout](#-port-architecture--network-layout)
- [⚙️ Advanced Configuration](#️-advanced-configuration)
- [⚠️ Legal Disclaimer & Disclaimer of Liability](#️-legal-disclaimer--disclaimer-of-liability)

---

## 🌟 Overview

**AltaXploit C2** is a next‑generation Red Team Command and Control framework engineered for stealth, resilience, and operational flexibility. Built around advanced PowerShell reverse shells, it operates **completely in‑memory** – never touching disk – to effortlessly bypass modern AV/EDR solutions. With integrated surveillance modules, a built‑in payload generator, and secure TLS communications, it provides everything a red team needs for covert engagements.

> 🛡️ *"With great power comes great responsibility!"* – AltaXploit Motto

---

## 🔥 Key Features

| Feature | Description |
|---------|-------------|
| 🧬 **In‑Memory Execution** | Payloads run purely in memory; no files written to disk, leaving minimal forensic footprint. |
| 🔒 **TLS Encrypted C2** | All traffic over **port 443** with self‑signed certificates, blending with normal HTTPS traffic. |
| 🎥 **Live Surveillance Suite** | Real‑time webcam, screen, and microphone streaming using **ffmpeg** and a local **Node Media Server** (port 1935). |
| 🧠 **Persistent Client Tracking** | Unique HWID‑based identification; automatically re‑attaches to reconnecting clients. |
| 🛠️ **One‑Click Payload Generator** | Produces stealthy Windows EXE (via .NET) with no console flash – ready for deployment. |
| 📂 **File Transfer** | Upload/download files to/from compromised hosts with progress feedback. |
| 💻 **Interactive PowerShell Shells** | Full interactive sessions with command history and color‑coded output. |

---

## 💻 Command Reference & Screenshot

![Command Menu Screenshot](image2.png)

### Interactive Shell Commands (within `attack <id>`)

| Command | Description |
|---------|-------------|
| `list` | Show all connected clients |
| `attack <id>` | Enter interactive shell with a client |
| `back` | Return to main prompt |
| `kill <id>` | Permanently terminate a client session |
| `upload <src> <dst>` | Upload a local file to the client |
| `download <file>` | Download a file from the client |
| `install spyware` | Install FFmpeg on the target (required for spy modules) |
| `spy camera` | Start live webcam stream |
| `spy screen` | Start live screen capture |
| `spy mic` | Start live microphone stream |
| `spy stop` | Stop all active streams |
| `generate payload` | Build a new Windows EXE payload |
| `help` | Display this command reference |
| `clear` | Clear the terminal |
| `exit` | Shut down the C2 server |

---

## 🚀 Installation & Setup Guide

> **💡 Recommended Environment:** Kali Linux (or any Debian‑based) with root access. The setup script installs all dependencies automatically.

### Step 1 – Clone the Repository
```bash
git clone https://github.com/AltaXploit/AltaXploit-C2.git
cd AltaXploit-C2
```

### Step 2 – Make Setup Executable
```bash
chmod +x setup.py
```

### Step 3 – Run the Dependency Installer
```bash
sudo python3 setup.py
```

**What this does:**
- 🐧 Installs system packages: `ffmpeg`, `mpv`, `vlc`, `nodejs`, `npm`, `openssl`, `python3-pip`, `python3-tk`, `wget`, and more.
- 🧩 Installs Python modules: `python-vlc`, `pycryptodome` (with `--break-system-packages` for Kali).
- 📦 Installs Node.js module `node-media-server` locally in the `script/` folder.
- 🔐 Generates self‑signed SSL certificates in `certs/`.
- 📁 Creates required directories (`Client-Data`, `script`, `certs`, `build`).
- 🧪 Verifies all executables and imports.

> ⏱️ The entire setup takes **3–5 minutes** depending on your connection speed.

### Step 4 – Launch the C2 Server
```bash
python3 C2.py
```

You will be prompted to enter your **LHOST IP** (the public IP where the server is reachable) – this is used for RTMP stream URLs. After that, you'll see the animated banner and the `AltaXploit>` prompt.

<p align="center">
  <img src="https://media.giphy.com/media/3o7abldj0b3rxrZUxW/giphy.gif" width="400">
</p>

---

## 🔌 Port Architecture & Network Layout

| Port | Protocol | Service | Purpose |
|------|----------|---------|---------|
| **443** | HTTPS/TLS | C2 Server | Main command & control channel (mandatory) |
| **1935** | RTMP | Node Media Server | Streaming video/audio for spy modules |

- The C2 server is **hardcoded** to listen on **port 443** – this mimics standard secure web traffic, making it harder to detect by network filters.
- The Node Media Server runs locally on **port 1935** and is automatically started when a `spy` command is issued. It pushes RTMP streams to the attacker's machine for viewing via the included GUI viewers (`cam.py`, `screen.py`, `microphone.py`).

> 🔥 **Pro Tip:** If you're behind a NAT, ensure port forwarding is configured for both ports.

---

## ⚙️ Advanced Configuration

### Customizing LHOST
The C2 server will ask for the LHOST IP at startup. You can also set it manually by editing the `LHOST` variable in `C2.py` (line ~40).

### Modifying SSL Certificates
Replace the self‑signed `cert.pem` and `key.pem` in `certs/` with your own signed certificates for added stealth.

### Disabling GUI Viewers
If you're running headless (no `DISPLAY`), you can comment out the GUI launch lines in `C2.py` (inside the `spy` command handlers) and use an external RTMP player like VLC to view streams at `rtmp://<LHOST>/live/stream`.

---

## ⚠️ Legal Disclaimer & Disclaimer of Liability

> **IMPORTANT:** *This software is provided solely for educational purposes, authorized penetration testing, and red teaming engagements with explicit written permission from the system owner. Unauthorized access to computer systems is illegal and punishable by law.*

- **Author's Liability:** The developer (**Muhammad Alwaz**) assumes **no responsibility** whatsoever for any misuse, damage, or illegal activities conducted with this framework.
- **User Accountability:** By downloading, installing, or using this tool, you agree that you are solely responsible for compliance with all applicable local, national, and international laws. You may not use this tool for any malicious or unlawful purpose.

> 🛡️ *Use responsibly – hack the planet, but only with consent!*

---

## 📬 Contact & Support

- **Developer:** Muhammad Alwaz
- **GitHub:** [AltaXploit](https://github.com/AltaXploit)
- **Website:** [alwaz.co.uk](https://www.alwaz.co.uk)

---

<p align="center">
  <b>Made with ❤️ for the Red Team Community</b>
</p>
```
