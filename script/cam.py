import tkinter as tk
import subprocess
import threading
import time
import random
import os

# RTMP stream URL
RTMP_URL = "rtmp://localhost/live/stream"

root = tk.Tk()
root.title("🔓 AltaXploit CAMERA MONITOR")
root.geometry("800x600")  # More compact size
root.configure(bg="#000000")
root.resizable(False, False)

# Main frame with hacker styling
main_frame = tk.Frame(root, bg="#000000", highlightbackground="#FF3300", highlightthickness=2)
main_frame.pack(fill="both", expand=True, padx=10, pady=10)

# Header with title and subtitle
header_frame = tk.Frame(main_frame, bg="#000000")
header_frame.pack(fill="x", pady=(5, 10))

title_label = tk.Label(
    header_frame, 
    text="🔓 AltaXploit CAMERA MONITOR",
    fg="#FF3300",
    bg="#000000",
    font=("Consolas", 16, "bold")
)
title_label.pack()

subtitle_label = tk.Label(
    header_frame,
    text='"All Your Cameras Are Belong To Us"',
    fg="#CC2200",
    bg="#000000",
    font=("Consolas", 10, "italic")
)
subtitle_label.pack()

# Status frame
status_frame = tk.Frame(main_frame, bg="#110000", highlightbackground="#440000", highlightthickness=1)
status_frame.pack(fill="x", padx=20, pady=(0, 10))

status_label = tk.Label(
    status_frame,
    text="STARTING RTMP SERVER...",
    fg="#FF3300",
    bg="#110000",
    font=("Consolas", 12, "bold")
)
status_label.pack(pady=5)

server_status_label = tk.Label(
    status_frame,
    text="RTMP Server: Starting...",
    fg="#CC2200",
    bg="#110000",
    font=("Consolas", 10)
)
server_status_label.pack(pady=(0, 5))

# Camera feed frame - now properly sized
camera_frame = tk.Frame(
    main_frame,
    bg="#000000",
    highlightbackground="#FF3300",
    highlightthickness=1
)
camera_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))

# Connection status
connection_frame = tk.Frame(main_frame, bg="#000000")
connection_frame.pack(fill="x", padx=20, pady=(0, 5))

connection_label = tk.Label(
    connection_frame,
    text="CONNECTION: ESTABLISHING | STATUS: OFFLINE | SHUTDOWN: --:--",
    fg="#CC2200",
    bg="#000000",
    font=("Consolas", 9)
)
connection_label.pack(side="left")

# Footer
footer_label = tk.Label(
    main_frame,
    text="[AltaXploit] // [RED TEAM ACTIVE] // [UNDETECTED]",
    fg="#660000",
    bg="#000000",
    font=("Consolas", 8, "bold")
)
footer_label.pack(side="bottom", pady=5)

# Variables
mpv_process = None
node_process = None
video_frame = None
is_active = False
server_ready = False

def start_rtmp_server():
    global node_process
    try:
        node_process = subprocess.Popen(
            ["node", "camserver.js"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=os.getcwd()
        )
        threading.Thread(target=monitor_server_output, daemon=True).start()
    except Exception as e:
        update_status(f"RTMP SERVER ERROR: {str(e)}", "red")

def monitor_server_output():
    global server_ready, is_active
    for line in node_process.stdout:
        line = line.strip()
        if "NodeMediaServer running on port 1935" in line:
            update_server_status("RTMP Server: RUNNING (Port 1935)", "#00FF00")
            server_ready = True
            update_status("WAITING FOR CAMERA STREAM...", "#FF3300")
        elif "start push" in line.lower():
            update_server_status("RTMP Server: STREAM DETECTED", "#00FF00")
            time.sleep(2)  # Wait for stable stream
            if not is_active:
                start_camera_feed()
        elif "error" in line.lower():
            update_server_status(f"RTMP Server: ERROR - {line[:50]}", "red")

def start_camera_feed():
    global mpv_process, video_frame, is_active
    try:
        # Create video frame that fills the camera_frame completely
        video_frame = tk.Frame(camera_frame, bg="black")
        video_frame.pack(fill="both", expand=True)
        
        root.update()
        video_frame_id = video_frame.winfo_id()
        
        mpv_cmd = [
            "mpv",
            "--no-terminal",
            "--hwdec=no",
            "--profile=low-latency",
            "--untimed",
            "--no-cache",
            "--vo=x11",
            f"--wid={video_frame_id}",
            "--no-keepaspect",  # Fill the entire frame
            "--fs",  # Fullscreen within container
            RTMP_URL
        ]
        mpv_process = subprocess.Popen(mpv_cmd)
        
        is_active = True
        update_status("✅ CAMERA FEED ACTIVE 🕶", "#00FF00")
        update_connection_status("CONNECTION: SECURE | STATUS: ONLINE | SHUTDOWN: --:--")
    except Exception as e:
        update_status(f"STREAM ERROR: {str(e)}", "red")

def update_status(text, color):
    status_label.config(text=text, fg=color)

def update_server_status(text, color):
    server_status_label.config(text=text, fg=color)

def update_connection_status(text):
    connection_label.config(text=text)

def on_closing():
    if mpv_process:
        mpv_process.terminate()
    if node_process:
        node_process.terminate()
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_closing)

# Start the server
start_rtmp_server()

root.mainloop()
