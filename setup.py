#!/usr/bin/env python3
"""
AltaXploit C2 – Dependency Installer
Installs: system packages, .NET SDK 8.0, Python modules (with --break-system-packages),
Node.js modules, SSL certificates, and directories.
Run as root (sudo) on Kali/Debian.
"""

import sys
import base64
import argparse
import os
import subprocess
import shutil
from pathlib import Path

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
REQUIRED_SYSTEM_PKGS = [
    "ffmpeg", "mpv", "vlc", "nodejs", "npm",
    "python3-pip", "python3-tk", "openssl", "wget",
    "gnupg", "software-properties-common"
]

PYTHON_MODULES = ["python-vlc", "pycryptodome"]
NODE_MODULES = ["node-media-server"]

C2_DIR = Path(__file__).parent.resolve()
CERT_DIR = C2_DIR / "certs"
SCRIPT_DIR = C2_DIR / "script"
DOTNET_REPO_DEB = "https://packages.microsoft.com/config/ubuntu/22.04/packages-microsoft-prod.deb"

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def run(cmd, check=True, cwd=None):
    subprocess.run(cmd, shell=True, check=check, cwd=cwd)

def has_cmd(name):
    return shutil.which(name) is not None

# ----------------------------------------------------------------------
# Installation steps
# ----------------------------------------------------------------------
def install_system_packages():
    print("[1/6] Installing system packages...")
    run("apt update -qq")
    run(f"apt install -y {' '.join(REQUIRED_SYSTEM_PKGS)}")

def install_dotnet():
    print("[2/6] Installing .NET SDK 8.0...")
    if has_cmd("dotnet"):
        ver = subprocess.run("dotnet --version", shell=True, capture_output=True, text=True).stdout.strip()
        if ver.startswith("8."):
            print(f"   .NET 8.x already installed (version {ver}).")
            return
    tmp = "/tmp/packages-microsoft-prod.deb"
    run(f"wget -q {DOTNET_REPO_DEB} -O {tmp}")
    run(f"dpkg -i {tmp}")
    run("apt update -qq")
    run("apt install -y dotnet-sdk-8.0")
    print(f"   Installed: {subprocess.run('dotnet --version', shell=True, capture_output=True, text=True).stdout.strip()}")

def install_python_modules():
    print("[3/6] Installing Python modules (using --break-system-packages)...")
    pip = shutil.which("pip3") or "pip3"
    for mod in PYTHON_MODULES:
        # Force override of externally-managed-environment protection
        run(f"{pip} install --break-system-packages {mod}")

def install_node_modules():
    print("[4/6] Installing Node.js modules...")
    if not has_cmd("npm"):
        run("apt install -y nodejs npm")
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    pkg_json = SCRIPT_DIR / "package.json"
    if not pkg_json.exists():
        pkg_json.write_text('{"name":"altaxploit-rtmp","version":"1.0.0"}')
    run(f"npm install {' '.join(NODE_MODULES)}", cwd=str(SCRIPT_DIR))

def generate_ssl():
    print("[5/6] Generating SSL certificates...")
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    cert = CERT_DIR / "cert.pem"
    key = CERT_DIR / "key.pem"
    if cert.exists() and key.exists():
        print("   Certificates already exist.")
        return
    run(f"openssl req -x509 -newkey rsa:4096 -nodes -out {cert} -keyout {key} -days 365 -subj '/CN=localhost'")

def create_dirs():
    print("[6/6] Creating directories...")
    for d in [C2_DIR / "Client-Data", SCRIPT_DIR, CERT_DIR, C2_DIR / "build"]:
        d.mkdir(parents=True, exist_ok=True)

def final_check():
    print("\n--- Final checks ---")
    for exe in ["ffmpeg", "mpv", "vlc", "node", "npm", "dotnet", "openssl", "python3"]:
        print(f"{exe:>10}: {'OK' if has_cmd(exe) else 'MISSING'}")
    # Quick Python module import test
    try:
        import vlc
        print("   python-vlc: OK")
    except ImportError:
        print("   python-vlc: MISSING")
    try:
        from Crypto.Cipher import AES
        print("   pycryptodome: OK")
    except ImportError:
        print("   pycryptodome: MISSING")
    print("\nSetup completed. You can now run: python3 C2.py")

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="AltaXploit C2 dependency installer")
    parser.add_argument("--skip-dotnet", action="store_true", help="Skip .NET SDK installation")
    args = parser.parse_args()

    if os.geteuid() != 0:
        print("This script must be run as root (sudo).", file=sys.stderr)
        sys.exit(1)

    if not shutil.which("apt"):
        print("This script only supports Debian-based systems (apt).", file=sys.stderr)
        sys.exit(1)

    install_system_packages()
    if not args.skip_dotnet:
        install_dotnet()
    install_python_modules()
    install_node_modules()
    generate_ssl()
    create_dirs()
    final_check()

if __name__ == "__main__":
    main()
