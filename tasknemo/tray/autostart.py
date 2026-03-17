"""Windows auto-start registration using Task Scheduler."""

import os
import subprocess
import sys


def install_autostart():
    """Register TaskNemo tray app to start at logon via Task Scheduler."""
    python_exe = sys.executable.replace("python.exe", "pythonw.exe")
    if not os.path.exists(python_exe):
        python_exe = sys.executable

    script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    tray_script = os.path.join(script_dir, "tasknemo_tray.py")

    task_name = "TaskNemoTray"

    # Remove existing task if present
    subprocess.run(
        ["schtasks", "/delete", "/tn", task_name, "/f"],
        capture_output=True,
    )

    # Create new scheduled task
    result = subprocess.run(
        [
            "schtasks", "/create",
            "/tn", task_name,
            "/tr", f'"{python_exe}" "{tray_script}"',
            "/sc", "onlogon",
            "/rl", "limited",
            "/f",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print(f"[autostart] Registered '{task_name}' to run at logon.")
        print(f"[autostart] Command: {python_exe} {tray_script}")
    else:
        print(f"[autostart] Failed to register task: {result.stderr}")
        print("[autostart] Try running as administrator.")

    return result.returncode == 0


def uninstall_autostart():
    """Remove TaskNemo from auto-start."""
    result = subprocess.run(
        ["schtasks", "/delete", "/tn", "TaskNemoTray", "/f"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("[autostart] Removed TaskNemoTray from auto-start.")
    else:
        print(f"[autostart] No task found or removal failed: {result.stderr}")
    return result.returncode == 0
