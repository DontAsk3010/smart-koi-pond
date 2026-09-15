from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_container_package_is_non_root_persistent_and_loopback_default() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    assert dockerfile.startswith("FROM python:3.12.14-slim")
    assert "SMART_KOI_HOST=127.0.0.1" in dockerfile
    assert "SMART_KOI_HISTORIAN_PATH=/var/lib/smart-koi-pond/historian.jsonl" in dockerfile
    assert "USER smartkoi" in dockerfile
    assert 'VOLUME ["/var/lib/smart-koi-pond"]' in dockerfile
    assert "http://127.0.0.1:8080/api/health" in dockerfile
    assert "ENV SMART_KOI_HOST=0.0.0.0" not in dockerfile

    ignored = set(dockerignore.splitlines())
    assert ".env" in ignored
    assert ".env.*" in ignored
    assert "secrets" in ignored
    assert "runtime-data" in ignored


def test_deployment_smoke_is_loopback_only_and_simulation_gated() -> None:
    workflow = (ROOT / ".github/workflows/deployment-package.yml").read_text(
        encoding="utf-8"
    )
    guide = (ROOT / "docs/VIRTUAL_POND_DEPLOYMENT_V1.md").read_text(
        encoding="utf-8"
    )

    assert "-p 127.0.0.1:18080:8080" in workflow
    assert "SMART_KOI_HOST=0.0.0.0" in workflow
    assert 'payload["execution_mode"] == "SIMULATION"' in workflow
    assert "do **not** expose the application server directly to the public Internet" in guide
    assert "SIMULATION / NO REAL DEVICE CONTROL" in guide
    assert "Site Integration & Commissioning" in guide
    assert "real actuator authority: `CLOSED`" in guide
    assert "high-risk automatic chemical dosing: `CLOSED`" in guide
