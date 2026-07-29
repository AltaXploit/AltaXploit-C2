import tkinter as tk
import subprocess
import threading
import time
import random
import math

RTMP_URL = "rtmp://localhost/live/mic"

root = tk.Tk()
root.title("🔒 AltaXploit MIC MONITOR")
root.geometry("620x400")
root.configure(bg="#000000")
root.resizable(False, False)

# Create a canvas for the hacker background
canvas = tk.Canvas(root, bg="black", highlightthickness=0)
canvas.pack(fill="both", expand=True)

# Matrix rain effect in red shades
class MatrixRain:
    def __init__(self, canvas):
        self.canvas = canvas
        self.width = canvas.winfo_width()
        self.height = canvas.winfo_height()
        self.font_size = 12
        self.drops = []
        self.colors = ["#FF3300", "#CC2900", "#992200", "#660000"]
        self.symbols = ["0", "1", "0", "1", "░", "▒", "▓", "█", "<>", "{}", "[]", "||"]

        self.columns = self.width // self.font_size
        for i in range(self.columns):
            self.drops.append(random.randint(-20, 0))

        self.animate()

    def animate(self):
        self.canvas.delete("matrix")
        self.width = self.canvas.winfo_width()
        self.height = self.canvas.winfo_height()

        for i in range(len(self.drops)):
            y = self.drops[i]
            char = random.choice(self.symbols)
            color = random.choice(self.colors)

            self.canvas.create_text(
                i * self.font_size, y,
                text=char,
                fill=color,
                font=("Consolas", self.font_size),
                anchor="nw",
                tags="matrix"
            )

            if y > self.height or random.random() > 0.95:
                self.drops[i] = 0
            else:
                self.drops[i] = y + self.font_size

        root.after(50, self.animate)

matrix = MatrixRain(canvas)

# Main frame with hacker styling (red/black)
main_frame = tk.Frame(
    canvas,
    bg="#000000",
    highlightbackground="#FF3300",
    highlightthickness=1
)
main_frame.place(relx=0.5, rely=0.5, anchor="center", width=580, height=360)

# Title with lock emoji and red color
title_label = tk.Label(
    main_frame,
    text="🔒 AltaXploit MIC MONITOR",
    fg="#FF3300",
    bg="#000000",
    font=("Consolas", 18, "bold")
)
title_label.pack(pady=(15, 5))

# Subtitle - hacker style quote
subtitle_label = tk.Label(
    main_frame,
    text='"Silence is not an option."',
    fg="#CC2200",
    bg="#000000",
    font=("Consolas", 11, "italic")
)
subtitle_label.pack(pady=(0, 15))

# Status panel (starts with enabling mic)
status_frame = tk.Frame(
    main_frame,
    bg="#110000",
    highlightbackground="#440000",
    highlightthickness=1
)
status_frame.pack(pady=10, padx=20, fill="x")

status_label = tk.Label(
    status_frame,
    text="ENABLING MICROPHONE...",
    fg="#FF3300",
    bg="#110000",
    font=("Consolas", 14, "bold")
)
status_label.pack(pady=15, padx=20)

# Volume visualization
volume_canvas = tk.Canvas(
    main_frame,
    bg="#000000",
    height=80,
    highlightbackground="#440000",
    highlightthickness=1
)
volume_canvas.pack(fill="x", padx=20, pady=(5, 10))

# Create volume bars
volume_bars = []
for i in range(40):
    bar = volume_canvas.create_rectangle(
        i * 15 + 5, 70,
        i * 15 + 12, 70,
        fill="#FF3300",
        outline=""
    )
    volume_bars.append(bar)

# Connection status
connection_frame = tk.Frame(
    main_frame,
    bg="#000000"
)
connection_frame.pack(fill="x", padx=20, pady=(5, 5))

connection_label = tk.Label(
    connection_frame,
    text="CONNECTION: ACTIVE | STATUS: OFFLINE | SHUTDOWN: --:--",
    fg="#CC2200",
    bg="#000000",
    font=("Consolas", 9)
)
connection_label.pack(side="left")

# Footer with hacker tags
footer_label = tk.Label(
    main_frame,
    text="[AltaXploit] // [UNDETECTED] // [AUTO-SHUTDOWN ENABLED]",
    fg="#660000",
    bg="#000000",
    font=("Consolas", 9)
)
footer_label.pack(side="bottom", pady=5)

# Animation variables
ffplay_process = None
node_process = None
stop_loading = False
volume_levels = [0] * 40
is_active = False
shutdown_timer = None
shutdown_countdown = 0

# Animate enabling mic effect with dots
def animate_enabling():
    if stop_loading:
        return
    current_text = status_label.cget("text")
    base_text = "ENABLING MICROPHONE"
    if "..." in current_text:
        status_label.config(text=base_text)
    else:
        dots = "." * (len(current_text) - len(base_text) + 1)
        status_label.config(text=base_text + dots)
    root.after(500, animate_enabling)

# Animate the volume visualization
def animate_volume():
    global volume_levels
    if is_active:
        base_level = random.randint(30, 70)
        for i in range(40):
            wave = math.sin(i / 3.0 + time.time() / 2) * 0.5 + 0.5
            volume_levels[i] = max(1, min(70, int(base_level * wave + random.randint(-5, 5))))
    else:
        volume_levels = [max(0, l - 2) for l in volume_levels]

    for i, bar in enumerate(volume_bars):
        height = volume_levels[i]
        volume_canvas.coords(bar, i * 15 + 5, 70 - height, i * 15 + 12, 70)
        intensity = min(255, height * 3)
        color = f"#FF{format(255 - intensity, '02X')}00"  # Red gradient
        volume_canvas.itemconfig(bar, fill=color)

    root.after(50, animate_volume)

def launch_ffplay():
    global ffplay_process
    if ffplay_process is None:
        try:
            cmd = [
                "ffplay", "-fflags", "nobuffer", "-flags", "low_delay", "-framedrop",
                "-window_title", "AltaXploit Mic Stream", "-autoexit", "-nodisp", RTMP_URL
            ]
            ffplay_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            handle_stream_error(f"FFPLAY ERROR: {str(e)}")

def handle_stream_error(message):
    global is_active, stop_loading, shutdown_countdown, ffplay_process, node_process

    is_active = False
    stop_loading = False
    status_label.config(text=f"⚠️ {message}", fg="#FF0000")
    connection_label.config(text="CONNECTION: DOWN | STATUS: ERROR | SHUTDOWN IN: 5s")

    if ffplay_process:
        try:
            ffplay_process.kill()
        except:
            pass
        ffplay_process = None

    if node_process:
        try:
            node_process.kill()
        except:
            pass
        node_process = None

    # Start shutdown countdown with 5 seconds now
    shutdown_countdown = 5
    update_shutdown_countdown()

def update_shutdown_countdown():
    global shutdown_countdown, shutdown_timer

    if shutdown_countdown > 0:
        connection_label.config(text=f"CONNECTION: DOWN | STATUS: ERROR | SHUTDOWN IN: {shutdown_countdown}s")
        shutdown_countdown -= 1
        shutdown_timer = root.after(1000, update_shutdown_countdown)
    else:
        # Perform shutdown
        connection_label.config(text="CONNECTION: TERMINATED | STATUS: OFFLINE | SHUTDOWN: NOW")
        status_label.config(text="🔒 SYSTEM SHUTDOWN COMPLETE", fg="#FF3300")

        # Kill all processes
        global ffplay_process, node_process
        if ffplay_process:
            try:
                ffplay_process.kill()
            except:
                pass
            ffplay_process = None

        if node_process:
            try:
                node_process.kill()
            except:
                pass
            node_process = None

        # Close application after 2 seconds
        root.after(2000, root.destroy)

def check_stream_health():
    """Periodically check the health of the stream"""
    global node_process, is_active

    if node_process:
        # Check if node process is still running
        if node_process.poll() is not None and is_active:
            handle_stream_error("STREAM PROCESS TERMINATED")
            return

    # Schedule the next health check
    if is_active:
        root.after(5000, check_stream_health)

def run_node_and_monitor():
    global node_process, ffplay_process, stop_loading, is_active

    try:
        node_process = subprocess.Popen(
            ["node", "microphone.js"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
    except Exception as e:
        handle_stream_error(f"NODE START FAILED: {str(e)}")
        return

    # Start periodic health checks
    threading.Thread(target=monitor_node_output, args=(node_process,), daemon=True).start()
    root.after(5000, check_stream_health)

def monitor_node_output(proc):
    global stop_loading, is_active

    for line in proc.stdout:
        if "start push /live/mic" in line:
            stop_loading = True
            is_active = True
            status_label.config(text="✅ MICROPHONE HACKED 🕶", fg="#FF3300")
            connection_label.config(text="CONNECTION: ACTIVE | STATUS: ONLINE | SHUTDOWN: --:--")
            launch_ffplay()
        elif "donePublish" in line or "disconnected" in line:
            handle_stream_error("MICROPHONE OFFLINE")
            break

# Start animations
animate_enabling()
animate_volume()

# Start monitoring Node server
threading.Thread(target=run_node_and_monitor, daemon=True).start()

root.mainloop()
