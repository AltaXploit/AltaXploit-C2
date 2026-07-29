![Alta-Tracker Screenshot](/image1.png)

# AltaXploit C2 Framework

**Developer:** Muhammad Alwaz

**Website:** [alwaz.co.uk](https://www.alwaz.co.uk)

---

## 🌟 Overview

**AltaXploit C2** is an advanced Red Team Command and Control framework designed for stealth operations, robust client management, and extensive post-exploitation capabilities. Built primarily around advanced PowerShell reverse shells, it operates heavily in-memory, ensuring complete fileless execution on the victim's machine to easily bypass modern Anti-Virus (AV) and Endpoint Detection and Response (EDR) solutions.

---

## ✨ Key Features

* **Fileless In-Memory Execution:** Payloads are executed directly in memory without writing payloads to disk, minimizing forensic footprint and avoiding traditional file-based detection mechanisms.


* **Encrypted TLS Communication:** Designed strictly around secure **port 443** using SSL with fake certificates to blend seamlessly with normal HTTPS web traffic.


* **Advanced Spyware & Surveillance Suite:** Integrates natively with `ffmpeg` and a local Node Media Server running on **port 1935** to capture real-time webcam streams, desktop screen monitoring, and microphone audio recordings.


* **Resilient Client Persistence & Management:** Tracks and manages multiple active targets with automated HWID identification and unique session handling.


* **Built-in Payload Generator:** Generates stealthy Windows EXE binaries compiled via .NET that utilize native Windows APIs without console flashing.



---

## 🚀 Installation & Setup Instructions

Follow these step-by-step instructions to clone, set up, and launch the AltaXploit C2 framework on your server:

```bash
# 1. Clone the repository
git clone https://github.com/AltaXploit/AltaXploit-C2.git

# 2. Navigate into the framework directory
cd AltaXploit-C2

# 3. Give execution permissions to the setup script
chmod +x setup.py

# 4. Run the setup script with administrative privileges
sudo python3 setup.py

# 5. Launch the C2 framework
python3 C2.py

```

---

## 🔌 Port Configuration & Architecture Note

* **Port 443 (Default & Mandatory):** The C2 server is hardcoded/designed to operate exclusively on **port 443** utilizing SSL with fake certificates. Do not change this port, as it mimics standard secure web traffic to evade basic network filters.


* **Port 1935 (Node Media Server):** Automatically runs locally to manage real-time streaming data (`rtmp`) needed for the framework's integrated camera, microphone, and screen spy features.
