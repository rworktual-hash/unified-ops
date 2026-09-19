# VoiceMG SSH metrics

Read-only SSH collection for hosts with `project=voicemg` (9 hosts in `full_inventory.py`).

## What is collected

| Role | Detected by | Probes |
|------|-------------|--------|
| **stt** | `stt` in server name | Docker, nginx, containers, app processes, **nvidia-smi** summary |
| **vmg** | default | Docker, nginx, containers, app processes |

Optional `.env` lists extend probes safely (allowlisted commands only):

- `VOICEMG_APP_SERVICE_UNITS` — all VoiceMG hosts
- `VOICEMG_VMG_SERVICE_UNITS` — VMG hosts only
- `VOICEMG_STT_SERVICE_UNITS` — STT hosts only
- `VOICEMG_LOCAL_HEALTH_URLS` — localhost HTTP GET only

## API & UI

- `GET /api/voicemg/ssh-overview` — SSH snapshots (keep this)
- `GET /api/legacy-metrics/voicemg/extras` — live MariaDB `voicemg` extras (CPU, load, mem, active calls, MOS, stall, RTP, jitter, UDP). Match by IP then hostname. No new sidebar tabs.
- `GET /api/legacy-metrics/voicemg/history?range=5m|30m|1h|2h|6h|12h|today|yesterday|2d|week|custom&group=ai_ccaas|ccaas|all` — same windows as voicemg.worktual.tech. Optional `start`/`end` for custom. Live SELECT from `metrics_calls` + `metrics_system`. Short ranges poll; week / custom do not.
- Sidebar **VoiceMG** panel: **Live CCaaS / AI-CCaaS** cards + **5m / Today** charts + SSH table **Portal extras** + optional Server-card tiles when `project=voicemg`

## Guardrails

No writes, restarts, or config changes. Only predefined commands in `voicemg_ssh_collectors.py`.
