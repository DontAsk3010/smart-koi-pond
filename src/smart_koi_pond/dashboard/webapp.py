import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from smart_koi_pond.dashboard.animated_pond_ui import (
    ANIMATED_POND_SCRIPT,
    ANIMATED_POND_STYLE,
)
from smart_koi_pond.dashboard.equipment_detail_ui import (
    EQUIPMENT_DETAIL_SCRIPT,
    EQUIPMENT_DETAIL_STYLE,
)
from smart_koi_pond.dashboard.fault_controls_ui import FAULT_CONTROLS_UI_SCRIPT
from smart_koi_pond.dashboard.filtration_backwash_causality_ui import (
    FILTRATION_BACKWASH_CAUSALITY_SCRIPT,
    FILTRATION_BACKWASH_CAUSALITY_STYLE,
)
from smart_koi_pond.dashboard.governance_status_ui import (
    GOVERNANCE_STATUS_SCRIPT,
    GOVERNANCE_STATUS_STYLE,
)
from smart_koi_pond.dashboard.incident_recovery_story_ui import (
    INCIDENT_RECOVERY_STORY_SCRIPT,
    INCIDENT_RECOVERY_STORY_STYLE,
)
from smart_koi_pond.dashboard.integrated_control_ui import INTEGRATED_CONTROL_UI_SCRIPT
from smart_koi_pond.dashboard.integrated_virtual_pond_ui import (
    INTEGRATED_VIRTUAL_POND_SCRIPT,
    INTEGRATED_VIRTUAL_POND_STYLE,
)
from smart_koi_pond.dashboard.modular_ui import MODULAR_UI_SCRIPT
from smart_koi_pond.dashboard.reference_profile_ui import REFERENCE_PROFILE_UI_SCRIPT
from smart_koi_pond.dashboard.service import RuntimeApplicationService
from smart_koi_pond.dashboard.sidebar_navigation_ui import (
    SIDEBAR_NAVIGATION_SCRIPT,
    SIDEBAR_NAVIGATION_STYLE,
)
from smart_koi_pond.dashboard.source_water_ui import SOURCE_WATER_UI_SCRIPT
from smart_koi_pond.dashboard.trend_event_ui import (
    TREND_EVENT_SCRIPT,
    TREND_EVENT_STYLE,
)
from smart_koi_pond.dashboard.virtual_pond_home_ui import (
    VIRTUAL_POND_HOME_SCRIPT,
    VIRTUAL_POND_HOME_STYLE,
)
from smart_koi_pond.dashboard.web_ui import INDEX_HTML

COMPOSED_INDEX_HTML = INDEX_HTML.replace(
    "</head>",
    (
        f"{ANIMATED_POND_STYLE}"
        f"{INTEGRATED_VIRTUAL_POND_STYLE}"
        f"{GOVERNANCE_STATUS_STYLE}"
        f"{EQUIPMENT_DETAIL_STYLE}"
        f"{TREND_EVENT_STYLE}"
        f"{INCIDENT_RECOVERY_STORY_STYLE}"
        f"{FILTRATION_BACKWASH_CAUSALITY_STYLE}"
        f"{VIRTUAL_POND_HOME_STYLE}"
        f"{SIDEBAR_NAVIGATION_STYLE}</head>"
    ),
).replace(
    "</body>",
    (
        f"<script>{MODULAR_UI_SCRIPT}</script>"
        f"<script>{ANIMATED_POND_SCRIPT}</script>"
        f"<script>{FAULT_CONTROLS_UI_SCRIPT}</script>"
        f"<script>{INTEGRATED_VIRTUAL_POND_SCRIPT}</script>"
        f"<script>{SOURCE_WATER_UI_SCRIPT}</script>"
        f"<script>{INTEGRATED_CONTROL_UI_SCRIPT}</script>"
        f"<script>{REFERENCE_PROFILE_UI_SCRIPT}</script>"
        f"<script>{GOVERNANCE_STATUS_SCRIPT}</script>"
        f"<script>{EQUIPMENT_DETAIL_SCRIPT}</script>"
        f"<script>{TREND_EVENT_SCRIPT}</script>"
        f"<script>{INCIDENT_RECOVERY_STORY_SCRIPT}</script>"
        f"<script>{FILTRATION_BACKWASH_CAUSALITY_SCRIPT}</script>"
        f"<script>{VIRTUAL_POND_HOME_SCRIPT}</script>"
        f"<script>{SIDEBAR_NAVIGATION_SCRIPT}</script></body>"
    ),
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
