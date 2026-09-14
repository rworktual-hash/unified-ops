# Unified Ops frontend

React + Vite dashboard for **Unified Ops** (servers, metrics, alerts, chat, approvals).

## Local dev

```bash
npm install
npm run dev
```

API default: http://localhost:8000 (override with `VITE_API_URL` in `.env`).

## Production build (nlp-sm)

```bash
npm run build
```

Output in `dist/` — served by Nginx at https://observability.worktual.tech (see repo [`docs/SSH_PORTS_AND_PRODUCTION.md`](../docs/SSH_PORTS_AND_PRODUCTION.md)).

## Notes

- Server list comes from `GET /servers`; active hosts show metric cards, inactive as pending chips.
- Types include `ssh_auth_mode` and `has_ssh_password` (password never sent to the browser).
