from flask import Flask, send_file, render_template, jsonify, request
import os
import psutil
import subprocess
import time
import glob
import configparser

app = Flask(__name__)

SCRIPTS = "/home/ohyz/pc-control/scripts"

def get_apps():

    apps = []

    desktop_files = (
        glob.glob("/usr/share/applications/*.desktop") +
        glob.glob(os.path.expanduser("~/.local/share/applications/*.desktop"))
    )

    allowed = [
        "firefox",
        "discord",
        "steam",
        "code - oss",
        "spotify",
        "telegram",
        "dota 2",
        "nekobox"
    ]

    for file in desktop_files:

        try:

            config = configparser.ConfigParser(interpolation=None)
            config.read(file, encoding="utf-8")

            if "Desktop Entry" not in config:
                continue

            entry = config["Desktop Entry"]

            name = entry.get("Name")
            exec_cmd = entry.get("Exec")
            icon = entry.get("Icon")

            if not name or not exec_cmd:
                continue

            exec_cmd = exec_cmd.split()[0]

            # фильтр приложений
            if name.lower() not in allowed:
                continue

            apps.append({
                "name": name,
                "exec": exec_cmd,
                "icon": icon
            })

        except:
            pass

    return apps

@app.route("/apps")
def apps():
    return jsonify(get_apps())


@app.route("/")
def home():
    return render_template("index.html")

@app.route("/files")
def files():
    return render_template("files.html")

# --- Power ---
@app.route("/shutdown")
def shutdown():
    os.system(f"{SCRIPTS}/shutdown.sh")
    return "ok"

@app.route("/sleep")
def sleep():
    os.system(f"{SCRIPTS}/sleep.sh")
    return "ok"

@app.route("/reboot")
def reboot():
    os.system(f"{SCRIPTS}/reboot.sh")
    return "ok"

# --- Volume ---
@app.route("/volume_up")
def volume_up():
    os.system(f"{SCRIPTS}/volume_up.sh")
    return "ok"

@app.route("/volume_down")
def volume_down():
    os.system(f"{SCRIPTS}/volume_down.sh")
    return "ok"

@app.route("/volume_set", methods=["POST"])
def volume_set():
    data = request.get_json()
    level = int(data.get("level", 50))
    level = max(0, min(100, level))
    os.system(f"{SCRIPTS}/volume_set.sh {level}")
    return "ok"

@app.route("/volume_get")
def volume_get():
    result = subprocess.run(
        ["pactl", "get-sink-volume", "@DEFAULT_SINK@"],
        capture_output=True, text=True
    )
    vol = 50
    for part in result.stdout.split():
        if part.endswith("%"):
            try:
                vol = int(part.replace("%", ""))
                break
            except:
                pass
    return jsonify({"volume": vol})

# --- Display ---
@app.route("/display_off")
def display_off():
    os.system(f"{SCRIPTS}/display_off.sh")
    return "ok"

@app.route("/display_on")
def display_on():
    os.system(f"{SCRIPTS}/display_on.sh")
    return "ok"


@app.route("/run_app", methods=["POST"])
def run_app():
    data = request.get_json()
    cmd = data.get("cmd")

    if cmd:
        subprocess.Popen([cmd])

    return "ok"

@app.route("/icon/<name>")
def icon(name):

    steam_cache = os.path.expanduser(
        "~/.local/share/Steam/appcache/librarycache"
    )

    # steam_icon_570 → 570/logo.png
    if name.startswith("steam_icon_"):

        appid = name.replace("steam_icon_", "")
        icon_path = os.path.join(steam_cache, appid, "logo.png")

        if os.path.exists(icon_path):
            return send_file(icon_path)

    # fallback linux icons
    icon_dirs = [
        "/usr/share/icons/hicolor",
        "/usr/share/icons/Papirus",
        "/usr/share/icons/Adwaita",
        "/usr/share/pixmaps"
    ]

    sizes = ["256x256","128x128","64x64","48x48","32x32"]

    for base in icon_dirs:

        if base.endswith("pixmaps"):
            for ext in ["png","svg"]:
                p = os.path.join(base, f"{name}.{ext}")
                if os.path.exists(p):
                    return send_file(p)

        else:
            for size in sizes:
                for ext in ["png","svg","jpg"]:

                    p = os.path.join(base, size, "apps", f"{name}.{ext}")

                    if os.path.exists(p):
                        return send_file(p)

    return ""

# --- Status ---
@app.route("/status")
def status():
    vm = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.5)

    gpu_percent = 0
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2
        )
        gpu_percent = int(result.stdout.strip())
    except:
        pass

    uptime_sec = int(time.time() - psutil.boot_time())
    hours = uptime_sec // 3600
    minutes = (uptime_sec % 3600) // 60

    procs = []
    try:
        for p in sorted(psutil.process_iter(["name", "memory_info"]),
                        key=lambda x: x.info["memory_info"].rss if x.info["memory_info"] else 0,
                        reverse=True)[:5]:
            mem_mb = p.info["memory_info"].rss // (1024 * 1024)
            if mem_mb > 10:
                procs.append({
                    "name": p.info["name"],
                    "mem": f"{mem_mb} MB" if mem_mb < 1024 else f"{mem_mb/1024:.1f} GB"
                })
    except:
        pass

    return jsonify({
        "cpu": round(cpu),
        "ram": round(vm.percent),
        "ram_used": round(vm.used / (1024**3), 1),
        "ram_total": round(vm.total / (1024**3), 1),
        "gpu": gpu_percent,
        "uptime": f"{hours}h {minutes:02d}m",
        "processes": procs
    })

@app.route("/terminal", methods=["POST"])
def terminal():

    data = request.json
    cmd = data.get("cmd")

    if not cmd:
        return jsonify({"output": ""})

    try:

        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True
        )

        output = result.stdout + result.stderr

    except Exception as e:
        output = str(e)

    return jsonify({"output": output})

@app.route("/shell")
def shell():
    return render_template("shell.html")

@app.route("/media_status")
def media_status():

    try:

        title = subprocess.check_output(
            ["playerctl","metadata","xesam:title"],
            text=True
        ).strip()

        artist = subprocess.check_output(
            ["playerctl","metadata","xesam:artist"],
            text=True
        ).strip()

        player = subprocess.check_output(
            ["playerctl","-p","playerctld","status"],
            text=True
        ).strip()

        art = subprocess.check_output(
            ["playerctl","metadata","mpris:artUrl"],
            text=True
        ).strip()

    except:

        title = ""
        artist = ""
        player = ""
        art = ""

    return jsonify({
        "title": title,
        "artist": artist,
        "player": player,
        "art": art
    })

@app.route("/script/<name>")
def run_script(name):

    scripts = {
        "dev": "dev_workspace.sh",
        "update": "update_system.sh",
        "lock": "lock_pc.sh",
    }

    if name in scripts:

        path = f"/home/ohyz/pc-control/scripts/{scripts[name]}"

        subprocess.Popen([path])

    return "ok"

@app.route("/scripts")
def scripts_page():
    return render_template("scripts.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)