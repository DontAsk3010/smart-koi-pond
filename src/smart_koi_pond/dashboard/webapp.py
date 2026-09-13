import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from smart_koi_pond.dashboard.animated_pond_ui import (
    ANIMATED_POND_SCRIPT,
    ANIMATED_POND_STYLE,
)
from smart_koi_pond.dashboard.modular_ui import MODULAR_UI_SCRIPT
from smart_koi_pond.dashboard.service import RuntimeApplicationService
from smart_koi_pond.dashboard.web_ui import INDEX_HTML

COMPOSED_INDEX_HTML = INDEX_HTML.replace(
    "</head>",
    f"{ANIMATED_POND_STYLE}</head>",
).replace(
    "</body>",
    f"<script>{MODULAR_UI_SCRIPT}</script><script>{ANIMATED_POND_SCRIPT}</script></body>",
)


def _handler_type(service: RuntimeApplicationService):
    class Handler(BaseHTTPRequestHandler):
        server_version = "SmartKoiPond/0.1"

        def _send_json(self, payload, status: int = HTTPStatus.OK) -> None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                body = COMPOSED_INDEX_HTML.encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return

            if parsed.path == "/api/health":
                snapshot = service.last_snapshot
                registry = snapshot.capability.registry
                self._send_json(
                    {
                        "status": "ok",
                        "execution_mode": snapshot.execution_mode,
                        "run_id": snapshot.run_id,
                        "baseline_status": (
                            registry.baseline.status if registry is not None else None
                        ),
                    }
                )
                return

            query = parse_qs(parsed.query)
            try:
                if parsed.path == "/api/runtime":
                    after = int(query.get("after", ["0"])[0])
                    self._send_json(service.publication(after_sequence=after))
                    return

                if parsed.path == "/api/history":
                    limit = int(query.get("limit", ["100"])[0])
                    if not 1 <= limit <= 5000:
                        raise ValueError("limit must be between 1 and 5000")
                    self._send_json({"frames": service.history(limit=limit)})
                    return

                if parsed.path == "/api/playback":
                    frame = int(query["frame"][0])
                    self._send_json(service.playback(frame))
                    return

                if parsed.path == "/api/incident":
                    incident_id = str(query["id"][0])
                    self._send_json(
                        {
                            "incident_id": incident_id,
                            "events": service.incident_evidence(incident_id),
                        }
                    )
                    return
            except (KeyError, TypeError, ValueError) as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return

            self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/api/command":
                self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 64_000:
                    raise ValueError("invalid request body length")
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(body, dict):
                    raise ValueError("request body must be a JSON object")
                action = str(body["action"])
                payload = body.get("payload", {})
                if not isinstance(payload, dict):
                    raise ValueError("payload must be a JSON object")
                role = self.headers.get("X-Koi-Role", "viewer").lower()
                snapshot = service.command(action, payload, role=role)
                if snapshot is not service.last_snapshot:
                    raise RuntimeError("command snapshot is not the canonical current snapshot")
                self._send_json(
                    {
                        "accepted": True,
                        "action": action,
                        "publication": service.publication(after_sequence=0),
                    }
                )
            except PermissionError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.FORBIDDEN)
            except (KeyError, RuntimeError, TypeError, ValueError) as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

        def log_message(self, format: str, *args) -> None:
            return

    return Handler


def create_server(
    service: RuntimeApplicationService,
    *,
    host: str = "127.0.0.1",
    port: int = 8080,
) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), _handler_type(service))


def serve(
    service: RuntimeApplicationService,
    *,
    host: str = "127.0.0.1",
    port: int = 8080,
) -> None:
    server = create_server(service, host=host, port=port)
    service.start_background()
    try:
        server.serve_forever()
    finally:
        server.server_close()
        service.stop_background()
