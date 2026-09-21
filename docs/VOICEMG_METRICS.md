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
- `GET /api/legacy-metrics/voicemg/extras` — live MariaDB `voicemg` extras (CPU, load, mem, disk, active calls, MOS, stall, RTP, jitter, UDP, FDs, threads, NIC, IPC, process). Match by IP then hostname. No new sidebar tabs.
- `GET /api/legacy-metrics/voicemg/history?range=5m|30m|1h|2h|6h|12h|today|yesterday|2d|week|custom&group=ai_ccaas|ccaas|all` — same windows as voicemg.worktual.tech. Optional `start`/`end` for custom and `server_id` to switch one host. Live SELECT from `metrics_calls` + `metrics_system` plus `metrics_process` / `metrics_disk` / `metrics_net` / `metrics_kernel` / `metrics_ipc` / `metrics_gateway` when those tables exist. Missing columns stay empty — no skip of the chart itself. Short ranges poll; week / custom do not.
- Sidebar **VoiceMG** panel: **Live CCaaS / AI-CCaaS** cards (click host to switch series) + disk % / calls-by-product bars + utilization charts + SSH table **Portal extras** + optional Server-card tiles when `project=voicemg`

## MariaDB utilization charts

All read-only. Charts stay visible even when `.222` has no rows for that metric.

| Chart | Source heuristic |
|-------|------------------|
| Active calls, MOS, jitter, loss, RTP Mbps | `metrics_calls` |
| RTP vs expected G.711 | `rtp_mbps_*` + `rtp_mbps_exp` |
| CPU / MEM % | `metrics_system` |
| RX errors / drops, NIC RX/TX | `metrics_net` or system/net columns |
| Open FDs / threads / UDP sockets | `metrics_process` |
| Inter-server sent/recv + latency | `metrics_ipc` |
| Runqueue / buffers / cached | `metrics_kernel` or system internals |
| UDP packets/s | `metrics_calls` or process UDP pps |
| Gateway process CPU/MEM | process / `metrics_gateway` |
| RTP GB total | `rtp_gb` or `rtp_bytes / 1e9` |
| Disk % bar + line | `metrics_disk` or `disk_used_pct` |
| Calls by product | latest extras grouped by `product` |

## Guardrails

No writes, restarts, or config changes. Only predefined commands in `voicemg_ssh_collectors.py`.
