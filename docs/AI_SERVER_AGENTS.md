# AI server agents (living document)

Scope: **AI / GPU inventory hosts** in Unified Ops (today the working pair is **148** and **149**). Agents SSH to the matched inventory host only. They never write or execute on MariaDB `.222`.

This file is the current contract. Update it when a Level 4 check or Level 5 command is added or removed.

---

## Levels

| Level | Name | May the agent run it alone? | Status |
|-------|------|-----------------------------|--------|
| 4 | Safe execution (read-only) | Yes, on the 5-minute collect (when Celery is on) or when you click Collect | **Live** |
| 5 | Human approval | No. Investigate explains → pending approval → Approve → Confirm run | **Live (recollect / SSH verify; Docker restart on GPU only)** |
| 6 | Admin only | Never. Report and stop | **Blocked** |

---

## Level 4 — Safe execution (what it does now)

Read-only SSH. No restart, stop, kill, delete, or config change. Failures are logged (`collect_error`, fleet `servers_failed`). No recovery action.

| Check | What the agent / collector does |
|-------|----------------------------------|
| CPU load | `loadavg` from the host |
| RAM | Used % from `free` |
| Disk | Root filesystem used % |
| GPU util / memory / temp / status | `nvidia-smi` query |
| Docker | `systemctl is-active docker` + `docker ps` names/status (count + list) |
| Process sample | Top CPU processes (`ps`, head only) |
| Application logs | Last lines of syslog/messages; lines with password/token/secret are redacted |
| Network | Listen `:8000` / `:8011`, TCP counts, localhost ping |

**Automation:** Celery Beat every 5 minutes when `METRICS_SCHEDULED_COLLECT_ENABLED=true`. Same job as **Collect all**. Inactive hosts are skipped.

---

## Level 5 — Human approval (what the agent does now)

After **Investigate** (server card, SSH Collect alert, or live `.222` alert matched by IP):

1. Agent reads the host (same Level 4 tools).
2. It writes **Agent log** (reason / diagnosis). The alert is **not** closed.
3. It opens **one pending approval** with:
   - which alert
   - why
   - exact command in plain language
   - impact (what will / will not change)
4. You **Approve** or **Reject**.
5. Approve is not enough: **Confirm run** is required (API rejects `confirmed=false`).
6. Reject or Cancel = nothing runs.

### Commands the agent may run today (after Confirm run)

| Action | Who | What it does | What it does not do |
|--------|-----|----------------|---------------------|
| **Recollect metrics** | Any active host | SSH collect CPU/RAM/disk/GPU, store, re-evaluate alerts | Restart, delete, change config |
| **SSH verify** | Any active host | SSH connection test | Any change on the host |
| **Restart Docker** | **Active GPU only** (148/149 today) | `sudo systemctl restart docker` when Docker is down | Reboot, `nvidia-smi -r`, driver/CUDA update, kill processes, write `.222` |

Investigate writes the issue, the exact command, and the impact on the approval. Approve is not enough. Confirm run is required. Inactive GPU 165/166 stay skipped.

If collect failed → **SSH verify**. If GPU Docker is inactive → **Restart Docker**. Otherwise → **Recollect**. Kill GPU process / clear cache / delete logs / pause / failover / repair scripts stay unwired.

---

## Level 6 — Never (agent must not execute)

Reboot, shutdown, GPU reset, NVIDIA/CUDA or OS update, format disk, change SSH keys, delete model data, unknown scripts.

---

## Update log

| Date | Change |
|------|--------|
| 2026-09-21 | Document created. Level 4 read-only collect + extras. Level 5 Investigate → explanation → two-step confirm for recollect / SSH verify only. |
| 2026-09-22 | GPU-only remediations: agent explains issue + exact command; Docker restart (`sudo systemctl restart docker`) after Approve + Confirm run when Docker is down. Non-GPU hosts stay recollect / SSH verify. |

Add a row here whenever we add a command or a collect check.
