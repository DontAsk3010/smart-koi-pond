# Smart Koi Pond — Virtual Pond Deployment V1

## Status

Deployment packaging for the **accepted Integrated Virtual Pond software baseline**. This file does not select a hosting vendor, domain, physical controller, or real-device authority.

Accepted software checkpoint at creation:

- main: `2c6a14b8e9bed1dee3594545771ef847ade1bd31`
- Final Integrated Virtual Pond acceptance: `17 PASS / 0 HOLD`
- execution authority: `SIMULATION`
- real actuator authority: `CLOSED`
- high-risk automatic chemical dosing: `CLOSED`

Google Drive authority remains controlling for architecture, security, configuration, update/rollback, and later physical commissioning.

## Where the Virtual Pond runs

The source code, version history, CI, and engineering evidence remain in GitHub. The runnable product is the same canonical Smart Koi Pond web application served by a host/server environment and opened with a web browser.

The container package in this repository is vendor-neutral packaging. A hosting provider, domain, reverse proxy, database/broker choice, and final physical host are replaceable deployment choices and are **not** made authoritative by this file.

## Security boundary

The built-in application HTTP server does not provide an independent production authentication system. Therefore:

- do **not** expose the application server directly to the public Internet;
- keep the default application bind at `127.0.0.1` when running directly on a host;
- when a container must bind `0.0.0.0`, restrict the host-published port to loopback/private infrastructure or place the service behind a separately governed authenticated/authorized supervisory gateway;
- no gateway or credential may grant control authority that the canonical runtime does not already authorize;
- controllers, brokers, databases, and physical I/O remain outside direct public reach;
- real secrets never enter the image, repository, CI artifacts, browser state, logs, or example configuration.

Binding `0.0.0.0` inside a container is a transport requirement only. It is **not** permission for public exposure and does not change execution or actuator authority.

## Container package

The repository `Dockerfile` packages the existing `smart-koi-pond-ui` entry point without replacing the runtime or creating another UI/control engine. It:

- uses the accepted Python 3.12 runtime family;
- installs the project package directly from repository source;
- runs as a non-root `smartkoi` user;
- keeps the application default bind at `127.0.0.1`;
- persists historian data under `/var/lib/smart-koi-pond`;
- exposes `/api/health` as the container healthcheck;
- starts the accepted Integrated Virtual Pond runtime in `SIMULATION / NO REAL DEVICE CONTROL`.

## Local browser run

Build:

```bash
docker build -t smart-koi-pond:local .
```

Run so the container can accept the port mapping while the **host exposure remains loopback-only**:

```bash
docker run --rm \
  --name smart-koi-pond \
  -e SMART_KOI_HOST=0.0.0.0 \
  -p 127.0.0.1:8080:8080 \
  -v smart-koi-runtime-data:/var/lib/smart-koi-pond \
  smart-koi-pond:local
```

Open `http://127.0.0.1:8080` in a browser.

This is the real accepted Virtual Pond software running in SIMULATION mode; it is not a throwaway UI mock. The browser surface remains bound to the canonical runtime, event stream, historian, verification, recovery, and playback semantics.

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `SMART_KOI_HOST` | `127.0.0.1` | HTTP bind address. External container bind requires controlled network/auth boundary. |
| `SMART_KOI_PORT` | `8080` | HTTP service port. |
| `SMART_KOI_HISTORIAN_PATH` | `/var/lib/smart-koi-pond/historian.jsonl` in the container | Persistent SIMULATION historian path. |

No secret values are defined here. A future deployment may inject approved secrets from its selected protected secret mechanism only after that deployment architecture is selected.

## Persistent data

Mount persistent storage at `/var/lib/smart-koi-pond`. Simulation history must remain identifiable as SIMULATION data and must not later be merged into indistinguishable LIVE operational history.

Before an update or rollback, preserve the accepted software commit identity, configuration lineage, historian/checkpoint data, and deployment manifest. A new build becomes LAST_GOOD only after the governed post-activation health/reconciliation/verification gate passes.

## Deployment health gate

A packaged deployment is healthy only when all of the following remain true:

1. `/api/health` returns an operational response from the canonical runtime.
2. Execution mode remains explicitly `SIMULATION` for this deployment stage.
3. UI/runtime data remains fail-honest: missing evidence is UNKNOWN/UNAVAILABLE rather than synthetic zero/normal.
4. Historian/playback remains read-only and point-in-time coherent.
5. No direct public command endpoint is exposed without the later governed authentication/authorization boundary.
6. No secret material is embedded in the image or repository.
7. Real actuator authority and high-risk automatic chemical dosing remain closed.
8. The existing fourteen accepted evidence lanes remain green.

## Later physical transition

This deployment packaging does not create a separate product. When final site hardware exists, validated sensor/actuator adapters and physical configuration are integrated into the same runtime during **Site Integration & Commissioning**. Optional HIL, bench, pilot, or shadow verification may be used when a specific integration risk warrants it; they are not mandatory rebuild stages.

`LIMITED_LIVE` and `FULL_LIVE` remain separately authorized modes and are not opened by browser deployment.
