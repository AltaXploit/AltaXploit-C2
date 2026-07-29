import tkinter as tk
import platform
import subprocess
import threading
import time
import os
import vlc
import random

# === CONFIGURATION ===
RTMP_URL = "rtmp://localhost/live/screen"
NODE_SCRIPT = "screenshare.js"
STREAM_LABEL = "🛡 AltaXploit - LIVE SURVEILLANCE"

# === ROOT WINDOW ===
root = tk.Tk()
root.title(STREAM_LABEL)
root.geometry("1280x720")
root.configure(bg="#000000")
root.resizable(True, True)

# === MAIN FRAME ===
main_frame = tk.Frame(root, bg="#000000", bd=0)
main_frame.pack(fill="both", expand=True, padx=0, pady=0)

# === HEADER (hacker look) ===
header_frame = tk.Frame(main_frame, bg="#000000")
header_frame.pack(fill="x", pady=(6, 4))

title_label = tk.Label(
    header_frame,
    text=STREAM_LABEL,
    font=("Consolas", 18, "bold"),
    fg="#FF4444",
    bg="#000000"
)
title_label.pack()

# === ANIMATED GLOW (optional flicker/glow) ===
def flicker_text():
    colors = ["#FF3333", "#CC0000", "#FF4444", "#AA0000"]
    title_label.config(fg=random.choice(colors))
    root.after(400, flicker_text)
flicker_text()

# === STATUS TEXT (Top Right) ===
status_label = tk.Label(
    root,
    text="🔴 Awaiting RTMP Stream...",
    font=("Consolas", 10),
    fg="#FF6600",
    bg="#000000"
)
status_label.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)

# === VIDEO CONTAINER ===
video_frame = tk.Frame(main_frame, bg="black", bd=0)
video_frame.pack(fill="both", expand=True, padx=0, pady=0)

# === LOADING LABEL (shows inside video_frame) ===
loading_label = tk.Label(
    video_frame,
    text="⏳ Waiting for screen feed...",
    font=("Consolas", 14, "bold"),
    fg="#FF6600",
    bg="black"
)
loading_label.place(relx=0.5, rely=0.5, anchor="center")

# === GLOBALS ===
vlc_instance = vlc.Instance("--no-xlib")
vlc_player = vlc_instance.media_player_new()
node_process = None

def update_status(text, color):
    status_label.config(text=text, fg=color)

# === START RTMP NODE SERVER ===
def start_rtmp_server():
    global node_process
    try:
        node_process = subprocess.Popen(
            ["node", NODE_SCRIPT],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=os.getcwd(),
            bufsize=1
        )
        threading.Thread(target=monitor_server_output, daemon=True).start()
    except Exception as e:
        update_status(f"RTMP Server Error: {str(e)}", "red")

def monitor_server_output():
    for line in node_process.stdout:
        line = line.strip()
        print("[RTMP]", line)
        if "NodeMediaServer" in line:
            update_status("✅ RTMP Server Ready", "#00FF00")
        elif "start push" in line.lower():
            update_status("🟢 LIVE Screen Feed Detected", "#00FF00")
            # Remove loading label once stream detected
            loading_label.place_forget()
            time.sleep(1)
            play_stream()

# === VLC STREAM PLAYER ===
def play_stream():
    video_id = video_frame.winfo_id()
    system = platform.system()
    try:
        if system == "Linux":
            vlc_player.set_xwindow(video_id)
        elif system == "Windows":
            vlc_player.set_hwnd(video_id)
        elif system == "Darwin":
            vlc_player.set_nsobject(video_id)

        media = vlc_instance.media_new(RTMP_URL)
        vlc_player.set_media(media)
        vlc_player.play()
    except Exception as e:
        update_status(f"VLC Error: {str(e)}", "red")

# === CLEAN EXIT ===
def on_close():
    if vlc_player:
        vlc_player.stop()
    if node_process:
        node_process.terminate()
    root.destroy()
root.protocol("WM_DELETE_WINDOW", on_close)

# === STARTUP ===
start_rtmp_server()
root.mainloop()
