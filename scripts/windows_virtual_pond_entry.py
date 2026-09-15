"""Windows portable entry for the canonical Smart Koi Pond Virtual Pond.

This is packaging only. It starts the same integrated SIMULATION runtime and browser UI
used by the accepted application; it does not implement a second state/control engine.
"""

from __future__ import annotations

import os
import sys
import threading
import webbrowser
from pathlib import Path


def _application_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def _open_browser_later(url: str) -> None:
    if os.getenv("SMART_KOI_AUTO_OPEN_BROWSER", "1").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return
    timer = threading.Timer(1.5, webbrowser.open, args=(url,))
    timer.daemon = True
    timer.start()


def main() -> None:
    app_dir = _application_directory()
    runtime_dir = app_dir / "runtime-data"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    host = os.getenv("SMART_KOI_HOST", "127.0.0.1")
    port = os.getenv("SMART_KOI_PORT", "8080")
    historian = os.getenv(
        "SMART_KOI_HISTORIAN_PATH",
        str(runtime_dir / "historian.jsonl"),
    )

    os.environ["SMART_KOI_HOST"] = host
    os.environ["SMART_KOI_PORT"] = port
    os.environ["SMART_KOI_HISTORIAN_PATH"] = historian

    url = f"http://{host}:{port}"
    print("SMART KOI POND — VIRTUAL POND")
    print("SIMULATION / NO REAL DEVICE CONTROL")
    print(f"Opening: {url}")
    print(f"Historian: {historian}")
    print("Close this window to stop the local Virtual Pond runtime.")
    _open_browser_later(url)

    from smart_koi_pond.dashboard.app import main as run_virtual_pond

    run_virtual_pond()


if __name__ == "__main__":
    main()
