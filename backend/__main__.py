from __future__ import annotations

import argparse
import os
import tempfile
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from .app import create_app
from .storage import default_data_dir


def serve(data_dir: Path, port: int, *, preview: bool, open_browser: bool) -> None:
    app = create_app(data_dir, preview=preview)
    server = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0" if preview else "127.0.0.1", port=port,
                                          proxy_headers=False, access_log=False))
    if open_browser:
        def ready() -> None:
            for _ in range(200):
                if server.started:
                    webbrowser.open(f"http://127.0.0.1:{port}/")
                    return
                if server.should_exit:
                    return
                time.sleep(0.1)
        threading.Thread(target=ready, daemon=True).start()
        print(f"Koma Studio: http://127.0.0.1:{port}/ (Ctrl+C to stop)", flush=True)
    server.run()
    if not server.started:
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Koma Studio on this device.")
    parser.add_argument("--port", type=int, default=os.environ.get("ANIMESTUDIO_PORT", "8765"))
    parser.add_argument("--data-dir", type=Path, help="Override the private workspace folder.")
    parser.add_argument("--open-browser", action="store_true", help="Open the local studio once it is ready.")
    parser.add_argument("--preview", action="store_true", help="Development only: serve a temporary, synthetic demo on all interfaces.")
    options = parser.parse_args()
    if not 1 <= options.port <= 65535:
        parser.error("The port must be between 1 and 65535.")
    if options.preview:
        if options.data_dir or options.open_browser:
            parser.error("The demo preview always uses a separate temporary workspace.")
        with tempfile.TemporaryDirectory(prefix="koma-demo-") as temporary:
            serve(Path(temporary), options.port, preview=True, open_browser=False)
    else:
        override = os.environ.get("ANIMESTUDIO_DATA_DIR")
        folder = options.data_dir or (Path(override) if override else default_data_dir())
        serve(folder, options.port, preview=False, open_browser=options.open_browser)


if __name__ == "__main__":
    main()
