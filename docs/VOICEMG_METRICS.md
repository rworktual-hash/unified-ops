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

- `GET /api/voicemg/ssh-overview`
- Sidebar **VoiceMG** panel after fleet collect

## Guardrails

No writes, restarts, or config changes. Only predefined commands in `voicemg_ssh_collectors.py`.
