"""System tray app — pystray + uvicorn in background thread."""

import threading
import webbrowser
from datetime import datetime

try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    pystray = None
    Image = None


def _create_icon_image():
    """Generate a purple 'N' icon using Pillow."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Purple rounded background
    draw.rounded_rectangle([2, 2, size - 2, size - 2], radius=12, fill=(108, 92, 231, 255))

    # White 'N'
    try:
        font = ImageFont.truetype("arial", 36)
    except OSError:
        font = ImageFont.load_default()
    draw.text((size // 2, size // 2), "N", fill="white", font=font, anchor="mm")
    return img


def _run_server(host, port):
    """Run uvicorn in a thread."""
    import uvicorn
    from ..web.app import create_app
    app = create_app()
    uvicorn.run(app, host=host, port=port, log_level="warning")


def run_tray(host="127.0.0.1", port=8511):
    """Launch system tray with embedded web server."""
    if pystray is None or Image is None:
        print("[tray] pystray or Pillow not installed. Install with:")
        print("  pip install pystray Pillow")
        print("[tray] Falling back to serve mode...")
        _run_server(host, port)
        return

    url = f"http://{host}:{port}"

    # Start server in background thread
    server_thread = threading.Thread(target=_run_server, args=(host, port), daemon=True)
    server_thread.start()

    def on_open(icon, item):
        webbrowser.open(url)

    def on_refresh(icon, item):
        try:
            from ..cli import cmd_refresh
            cmd_refresh()
        except Exception as e:
            print(f"[tray] Refresh error: {e}")

    def on_quit(icon, item):
        icon.stop()

    icon_image = _create_icon_image()

    icon = pystray.Icon(
        "TaskNemo",
        icon_image,
        "TaskNemo",
        menu=pystray.Menu(
            pystray.MenuItem("Open TaskNemo", on_open, default=True),
            pystray.MenuItem("Refresh Now", on_refresh),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", on_quit),
        ),
    )

    print(f"[tray] TaskNemo running at {url}")
    print("[tray] System tray icon active. Right-click for menu.")
    icon.run()
