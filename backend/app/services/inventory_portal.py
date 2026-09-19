"""Read-only servers.worktual.tech inventory from MariaDB `server_inventory`.

Never selects password / secret / token columns.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from sqlalchemy import text

from app.config import settings
from app.db.legacy_metrics_session import get_legacy_metrics_engine
from app.services.live_cache import get_cached, set_cached

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SECRET_HINTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "ssh_pass",
    "hash",
)
_ONLINE_STATUSES = {"online", "running", "active", "up", "ok", "healthy"}


def _inventory_engine():
    if not settings.legacy_metrics_database_url:
        return None, "LEGACY_METRICS_DATABASE_URL not set"
    database = settings.legacy_infrastructure_database or "server_inventory"
    engine = get_legacy_metrics_engine(database)
    if engine is None:
        return None, "engine unavailable"
    return engine, database


def _empty(reason: str) -> dict:
    return {
        "ok": False,
        "reason": reason,
        "database": None,
        "dashboard": _empty_dashboard(),
        "clusters": [],
        "hosts": [],
        "baremetal": [],
        "vms": [],
    }


def _empty_dashboard() -> dict:
    return {
        "total_servers": 0,
        "online_servers": 0,
        "total_vms": 0,
        "active_vms": 0,
        "baremetal_count": 0,
        "host_count": 0,
        "cluster_count": 0,
        "cpu_total": None,
        "cpu_used": None,
        "cpu_pct": None,
        "ram_total_gb": None,
        "ram_used_gb": None,
        "ram_pct": None,
        "storage_total_gb": None,
        "storage_used_gb": None,
        "storage_pct": None,
    }


def _safe_columns(conn, table: str) -> list[str]:
    rows = conn.execute(
        text(
            "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :tbl "
            "ORDER BY ORDINAL_POSITION"
        ),
        {"tbl": table},
    ).all()
    out: list[str] = []
    for (name,) in rows:
        if not isinstance(name, str) or not _IDENT.match(name):
            continue
        lowered = name.lower()
        if any(hint in lowered for hint in _SECRET_HINTS):
            continue
        out.append(name)
    return out


def _select(alias: str, cols: list[str], prefix: str = "") -> str:
    parts = []
    for col in cols:
        as_name = f"{prefix}{col}" if prefix else col
        parts.append(f"{alias}.`{col}` AS `{as_name}`")
    return ", ".join(parts)


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    number = _num(value)
    if number is None:
        return None
    return int(number)


def _str(value: Any) -> str | None:
    if value is None:
        return None
    text_val = str(value).strip()
    return text_val or None


def _first(row, *names: str):
    for name in names:
        if name in row and row[name] is not None:
            return row[name]
    return None


def _as_gb(value: Any) -> float | None:
    number = _num(value)
    if number is None:
        return None
    if abs(number) >= 10_000_000:
        return number / (1024**3)
    return number


def _pct(used: float | None, total: float | None) -> float | None:
    if used is None or total is None or total <= 0:
        return None
    return round((used / total) * 100, 1)


def _is_online(status: Any) -> bool:
    if status is None:
        return False
    return str(status).strip().lower() in _ONLINE_STATUSES


def _table_exists(conn, name: str) -> bool:
    count = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :tbl"
        ),
        {"tbl": name},
    ).scalar()
    return bool(count)


def fetch_inventory_portal() -> dict:
    """Dashboard + baremetal + Proxmox hosts + VMs (no secrets)."""
    engine, extra = _inventory_engine()
    if engine is None:
        return _empty(extra)
    database = extra
    try:
        with engine.connect() as conn:
            if not _table_exists(conn, "baremetal_servers"):
                return {**_empty("server_inventory tables not found"), "database": database}

            bm_cols = _safe_columns(conn, "baremetal_servers")
            cluster_cols = _safe_columns(conn, "proxmox_clusters")
            host_cols = _safe_columns(conn, "proxmox_hosts")
            vm_cols = _safe_columns(conn, "virtual_machines")
            live_node_cols = _safe_columns(conn, "live_node_statistics")
            live_vm_cols = _safe_columns(conn, "live_vm_statistics")

            bm_rows = (
                conn.execute(
                    text(f"SELECT {_select('b', bm_cols)} FROM baremetal_servers b ORDER BY b.id")
                ).mappings().all()
                if bm_cols
                else []
            )
            cluster_rows = (
                conn.execute(
                    text(
                        f"SELECT {_select('c', cluster_cols)} FROM proxmox_clusters c ORDER BY c.id"
                    )
                ).mappings().all()
                if cluster_cols
                else []
            )
            host_rows = (
                conn.execute(
                    text(f"SELECT {_select('h', host_cols)} FROM proxmox_hosts h ORDER BY h.id")
                ).mappings().all()
                if host_cols
                else []
            )
            vm_rows = (
                conn.execute(
                    text(f"SELECT {_select('v', vm_cols)} FROM virtual_machines v ORDER BY v.id")
                ).mappings().all()
                if vm_cols
                else []
            )
            live_node_rows = (
                conn.execute(
                    text(
                        f"SELECT {_select('n', live_node_cols)} FROM live_node_statistics n"
                    )
                ).mappings().all()
                if live_node_cols
                else []
            )
            live_vm_rows = (
                conn.execute(
                    text(f"SELECT {_select('m', live_vm_cols)} FROM live_vm_statistics m")
                ).mappings().all()
                if live_vm_cols
                else []
            )

        live_nodes = {_str(row.get("node_name")): row for row in live_node_rows if row.get("node_name")}
        live_vms = _index_live_vms(live_vm_rows)

        clusters = [_map_cluster(row) for row in cluster_rows]
        cluster_by_id = {c["id"]: c for c in clusters}

        hosts = []
        for row in host_rows:
            cluster = cluster_by_id.get(_int(row.get("cluster_id")))
            live = live_nodes.get(_str(row.get("node_name")))
            hosts.append(_map_host(row, cluster, live))

        host_by_node = {h["node_name"]: h for h in hosts if h.get("node_name")}

        baremetal = [_map_baremetal(row) for row in bm_rows]
        vms = []
        for row in vm_rows:
            node_name = _str(row.get("node_name"))
            host = host_by_node.get(node_name) if node_name else None
            live = _lookup_live_vm(live_vms, row)
            vms.append(_map_vm(row, host, live))

        dashboard = _build_dashboard(clusters, hosts, baremetal, vms, live_node_rows, live_vm_rows)
        return {
            "ok": True,
            "database": database,
            "reason": None,
            "dashboard": dashboard,
            "clusters": clusters,
            "hosts": hosts,
            "baremetal": baremetal,
            "vms": vms,
        }
    except Exception as exc:
        return {**_empty(str(exc)), "database": database}


def _index_live_vms(rows) -> dict[tuple[str, str], Any]:
    index: dict[tuple[str, str], Any] = {}
    for row in rows:
        node = _str(row.get("node_name")) or ""
        for key in ("vmid_proxmox", "vm_id"):
            value = _str(row.get(key))
            if value:
                index[(node, value)] = row
    return index


def _lookup_live_vm(index: dict[tuple[str, str], Any], row) -> Any:
    node = _str(row.get("node_name")) or ""
    for key in ("vm_id", "vmid", "vmid_proxmox"):
        value = _str(row.get(key))
        if value and (node, value) in index:
            return index[(node, value)]
        if value and ("", value) in index:
            return index[("", value)]
    return None


def _map_baremetal(row) -> dict:
    ram = _first(row, "ram", "ram_gb", "memory_gb", "total_ram", "memory")
    cpu = _first(row, "cpu", "cpu_cores", "cores", "vcpu")
    return {
        "id": int(row["id"]),
        "order_id": _str(_first(row, "order_id")),
        "server_id": _str(_first(row, "server_id")),
        "hostname": _str(_first(row, "hostname", "host_name", "name")),
        "host_public_ip": _str(_first(row, "host_public_ip", "public_ip")),
        "ilo_private_ip": _str(_first(row, "ilo_private_ip")),
        "cluster": _str(_first(row, "cluster", "cluster_name")),
        "cluster_group": _str(_first(row, "cluster_group")),
        "os": _str(_first(row, "os", "operating_system", "os_name", "os_version")),
        "engineer": _str(_first(row, "engineer", "assigned_engineer", "owner", "managed_by")),
        "ram": _str(ram) if ram is not None else None,
        "cpu": _str(cpu) if cpu is not None else None,
        "location": _str(_first(row, "location", "datacenter", "site")),
        "status": _str(_first(row, "status")),
        "notes": _str(_first(row, "notes", "remarks", "description")),
    }


def _map_cluster(row) -> dict:
    total_cpu = _num(_first(row, "total_cpu"))
    total_ram = _as_gb(_first(row, "total_ram", "total_ram_gb"))
    total_storage = _as_gb(_first(row, "total_storage", "total_storage_gb"))
    return {
        "id": int(row["id"]),
        "cluster_name": _str(_first(row, "cluster_name", "name")) or f"cluster-{row['id']}",
        "cluster_label": _str(_first(row, "cluster_label", "label")),
        "description": _str(row.get("description")),
        "total_nodes": _int(_first(row, "total_nodes")) or 0,
        "total_cpu": total_cpu,
        "total_ram_gb": total_ram,
        "total_storage_gb": total_storage,
        "total_vms": _int(_first(row, "total_vms")) or 0,
        "used_cpu": None,
        "used_ram_gb": None,
        "used_storage_gb": None,
        "cpu_pct": None,
        "ram_pct": None,
        "storage_pct": None,
    }


def _map_host(row, cluster: dict | None, live) -> dict:
    live = live or {}
    status = _str(_first(live, "status") or row.get("status"))
    used_cpu = _num(_first(row, "used_cpu"))
    total_cpu = _num(_first(row, "total_cpu"))
    used_ram_gb = _as_gb(_first(row, "used_ram", "used_ram_gb"))
    total_ram_gb = _as_gb(_first(row, "total_ram", "total_ram_gb"))
    used_storage_gb = _as_gb(_first(row, "used_storage_gb", "used_storage"))
    total_storage_gb = _as_gb(_first(row, "total_storage_gb", "total_storage"))
    live_cpu = _num(_first(live, "cpu_util_pct"))
    live_ram_used = _as_gb(_first(live, "ram_used_bytes"))
    live_ram_total = _as_gb(_first(live, "ram_total_bytes"))
    live_storage_used = _as_gb(_first(live, "storage_used_bytes"))
    live_storage_total = _as_gb(_first(live, "storage_total_bytes"))
    return {
        "id": int(row["id"]),
        "node_name": _str(_first(row, "node_name", "hostname")) or f"node-{row['id']}",
        "cluster_id": _int(row.get("cluster_id")),
        "cluster_name": cluster["cluster_name"] if cluster else None,
        "cluster_label": cluster["cluster_label"] if cluster else None,
        "host_public_ip": _str(_first(row, "host_public_ip")),
        "host_private_ip": _str(_first(row, "host_private_ip")),
        "total_cpu": total_cpu,
        "used_cpu": used_cpu,
        "total_ram_gb": live_ram_total or total_ram_gb,
        "used_ram_gb": live_ram_used or used_ram_gb,
        "total_storage_gb": live_storage_total or total_storage_gb,
        "used_storage_gb": live_storage_used or used_storage_gb,
        "cpu_pct": live_cpu if live_cpu is not None else _pct(used_cpu, total_cpu),
        "ram_pct": _pct(live_ram_used or used_ram_gb, live_ram_total or total_ram_gb),
        "storage_pct": _pct(
            live_storage_used or used_storage_gb, live_storage_total or total_storage_gb
        ),
        "status": status,
        "uptime_seconds": _int(_first(live, "uptime_seconds")),
        "updated_at": _first(live, "updated_at"),
    }


def _map_vm(row, host: dict | None, live) -> dict:
    live = live or {}
    status = _str(_first(live, "status") or row.get("status"))
    ram = _first(row, "ram", "ram_gb", "memory_gb")
    disk = _first(row, "disk", "disk_gb", "storage_gb", "hdd")
    return {
        "id": int(row["id"]),
        "vm_id": _str(_first(row, "vm_id", "vmid")) or str(row["id"]),
        "node_name": _str(_first(row, "node_name")),
        "cluster_name": host["cluster_name"] if host else _str(_first(row, "cluster", "cluster_name")),
        "guest_hostname": _str(_first(row, "guest_hostname", "hostname", "name")),
        "guest_ip_private": _str(_first(row, "guest_ip_private")),
        "guest_ip_public": _str(_first(row, "guest_ip_public")),
        "guest_ip_ipv6": _str(_first(row, "guest_ip_ipv6")),
        "services": _str(_first(row, "services", "service")),
        "team": _str(_first(row, "team", "team_name")),
        "status": status,
        "cpu": _int(_first(row, "cpu", "cpu_cores", "vcpu")),
        "ram_gb": _as_gb(ram) if ram is not None else None,
        "disk_gb": _as_gb(disk) if disk is not None else None,
        "cpu_util_pct": _num(_first(live, "cpu_util_pct")),
        "ram_used_gb": _as_gb(_first(live, "ram_used_bytes")),
        "ram_total_gb": _as_gb(_first(live, "ram_total_bytes")),
        "storage_used_gb": _as_gb(_first(live, "storage_used_bytes")),
        "net_in_bps": _num(_first(live, "net_in_bytes_sec")),
        "net_out_bps": _num(_first(live, "net_out_bytes_sec")),
        "updated_at": _first(live, "updated_at"),
    }


def _build_dashboard(clusters, hosts, baremetal, vms, live_nodes, live_vms) -> dict:
    for cluster in clusters:
        members = [h for h in hosts if h.get("cluster_id") == cluster["id"]]
        used_cpu = sum(h["used_cpu"] or 0 for h in members)
        used_ram = sum(h["used_ram_gb"] or 0 for h in members)
        used_storage = sum(h["used_storage_gb"] or 0 for h in members)
        if members:
            cluster["used_cpu"] = used_cpu
            cluster["used_ram_gb"] = used_ram
            cluster["used_storage_gb"] = used_storage
            cluster["cpu_pct"] = _pct(used_cpu, cluster["total_cpu"])
            cluster["ram_pct"] = _pct(used_ram, cluster["total_ram_gb"])
            cluster["storage_pct"] = _pct(used_storage, cluster["total_storage_gb"])

    host_online = sum(1 for h in hosts if _is_online(h.get("status")))
    if not host_online and live_nodes:
        host_online = sum(1 for row in live_nodes if _is_online(row.get("status")))
    vm_active = sum(1 for vm in vms if _is_online(vm.get("status")))
    if not vm_active and live_vms:
        vm_active = sum(1 for row in live_vms if _is_online(row.get("status")))

    total_hosts = len(hosts)
    total_vms = len(vms)
    total_servers = len(baremetal) + len(hosts) + total_vms
    online_servers = host_online + vm_active

    cpu_total = sum((c["total_cpu"] or 0) for c in clusters) or None
    cpu_used = sum((c["used_cpu"] or 0) for c in clusters) or None
    ram_total = sum((c["total_ram_gb"] or 0) for c in clusters) or None
    ram_used = sum((c["used_ram_gb"] or 0) for c in clusters) or None
    storage_total = sum((c["total_storage_gb"] or 0) for c in clusters) or None
    storage_used = sum((c["used_storage_gb"] or 0) for c in clusters) or None

    if cpu_total == 0:
        cpu_total = None
    if ram_total == 0:
        ram_total = None
    if storage_total == 0:
        storage_total = None

    return {
        "total_servers": total_servers,
        "online_servers": online_servers,
        "total_vms": total_vms,
        "active_vms": vm_active,
        "baremetal_count": len(baremetal),
        "host_count": total_hosts,
        "cluster_count": len(clusters),
        "cpu_total": cpu_total,
        "cpu_used": cpu_used,
        "cpu_pct": _pct(cpu_used, cpu_total),
        "ram_total_gb": ram_total,
        "ram_used_gb": ram_used,
        "ram_pct": _pct(ram_used, ram_total),
        "storage_total_gb": storage_total,
        "storage_used_gb": storage_used,
        "storage_pct": _pct(storage_used, storage_total),
    }


def _empty_catalog(reason: str, database: str | None = None) -> dict:
    return {
        "ok": False,
        "reason": reason,
        "database": database,
        "did_total": 0,
        "did_allocated": 0,
        "ssl_total": 0,
        "ssl_expiring": 0,
        "domain_total": 0,
        "dids": [],
        "ssl": [],
        "domains": [],
        "providers": [],
        "clients": [],
    }


def fetch_inventory_catalog() -> dict:
    cached = get_cached("inventory_catalog")
    if cached is not None:
        return cached
    out = _fetch_inventory_catalog()
    set_cached("inventory_catalog", out)
    return out


def _fetch_inventory_catalog() -> dict:
    """Read-only DID / SSL / domain lists from server_inventory. No writes."""
    engine, extra = _inventory_engine()
    if engine is None:
        return _empty_catalog(extra)
    database = extra
    try:
        with engine.connect() as conn:
            dids = _load_dids(conn)
            ssl_rows = _load_ssl(conn)
            domains = _load_domains(conn)
            providers = _load_simple(
                conn,
                "did_providers",
                ("id", "provider_name", "contact_person", "support_email", "support_phone"),
            )
            clients = _load_simple(
                conn,
                "did_clients",
                ("id", "company_name", "company_id", "contact_name", "contact_email", "status"),
            )
        allocated = sum(1 for row in dids if (row.get("status") or "").lower() in {"allocated", "active", "in_use"})
        expiring = sum(1 for row in ssl_rows if (row.get("remaining_days") or 999) <= 30)
        return {
            "ok": True,
            "reason": None,
            "database": database,
            "did_total": len(dids),
            "did_allocated": allocated,
            "ssl_total": len(ssl_rows),
            "ssl_expiring": expiring,
            "domain_total": len(domains),
            "dids": dids,
            "ssl": ssl_rows,
            "domains": domains,
            "providers": providers,
            "clients": clients,
        }
    except Exception as exc:
        return _empty_catalog(str(exc), database)


def _load_simple(conn, table: str, keys: tuple[str, ...]) -> list[dict]:
    if not _table_exists(conn, table):
        return []
    cols = _safe_columns(conn, table)
    if "id" not in cols:
        return []
    rows = conn.execute(text(f"SELECT {_select('t', cols)} FROM `{table}` t ORDER BY t.id")).mappings().all()
    out = []
    for row in rows:
        item = {"id": int(row["id"])}
        for key in keys:
            if key == "id":
                continue
            item[key] = _str(_first(row, key))
        out.append(item)
    return out


def _load_dids(conn) -> list[dict]:
    if not _table_exists(conn, "did_numbers"):
        return []
    num_cols = _safe_columns(conn, "did_numbers")
    if "id" not in num_cols:
        return []
    prov_cols = _safe_columns(conn, "did_providers") if _table_exists(conn, "did_providers") else []
    alloc_cols = _safe_columns(conn, "did_allocations") if _table_exists(conn, "did_allocations") else []
    client_cols = _safe_columns(conn, "did_clients") if _table_exists(conn, "did_clients") else []
    sql = f"SELECT {_select('n', num_cols)}"
    joins = " FROM did_numbers n "
    if prov_cols:
        sql += ", " + _select("p", [c for c in prov_cols if c != "id"], "p_")
        joins += " LEFT JOIN did_providers p ON p.id = n.provider_id "
    if alloc_cols and "did_number_id" in alloc_cols:
        sql += ", " + _select("a", [c for c in alloc_cols if c != "id"], "a_")
        joins += """
            LEFT JOIN did_allocations a ON a.id = (
              SELECT x.id FROM did_allocations x
              WHERE x.did_number_id = n.id
              ORDER BY x.id DESC LIMIT 1
            )
        """
        if client_cols:
            sql += ", " + _select("c", [c for c in client_cols if c != "id"], "c_")
            joins += " LEFT JOIN did_clients c ON c.id = a.client_id "
    rows = conn.execute(text(sql + joins + " ORDER BY n.id LIMIT 500")).mappings().all()
    out = []
    for row in rows:
        status = _str(_first(row, "did_status", "a_status", "status"))
        out.append(
            {
                "id": int(row["id"]),
                "did_number": _str(_first(row, "did_number")) or "",
                "country_code": _str(_first(row, "country_code")),
                "area_code": _str(_first(row, "area_code")),
                "number_type": _str(_first(row, "number_type")),
                "status": status,
                "provider": _str(_first(row, "p_provider_name", "provider_name")),
                "client": _str(_first(row, "c_company_name", "kyc_for_company", "kyc_name")),
                "use_case": _str(_first(row, "a_use_case", "use_case")),
                "application": _str(_first(row, "a_application_name", "application_name")),
                "monthly_cost": _num(_first(row, "monthly_cost")),
                "purchase_date": _as_dt(_first(row, "purchase_date")),
                "allocated_date": _as_dt(_first(row, "a_allocated_date")),
            }
        )
    return out


def _load_ssl(conn) -> list[dict]:
    if not _table_exists(conn, "ssl_certificates"):
        return []
    cols = _safe_columns(conn, "ssl_certificates")
    if "id" not in cols:
        return []
    domain_cols = _safe_columns(conn, "domains") if _table_exists(conn, "domains") else []
    sql = f"SELECT {_select('s', cols)}"
    joins = " FROM ssl_certificates s "
    if domain_cols:
        sql += ", " + _select("d", [c for c in domain_cols if c != "id"], "d_")
        joins += " LEFT JOIN domains d ON d.id = s.domain_id "
    rows = conn.execute(text(sql + joins + " ORDER BY s.id")).mappings().all()
    out = []
    for row in rows:
        out.append(
            {
                "id": int(row["id"]),
                "hostname": _str(_first(row, "hostname", "common_name", "d_domain_name")) or "",
                "domain": _str(_first(row, "d_domain_name")),
                "issuer": _str(_first(row, "issuer")),
                "valid_from": _as_dt(_first(row, "valid_from")),
                "valid_to": _as_dt(_first(row, "valid_to")),
                "remaining_days": _remaining_days(
                    _first(row, "remaining_days"), _first(row, "valid_to")
                ),
                "status": _str(_first(row, "status")),
                "serial_number": _str(_first(row, "serial_number")),
                "last_checked": _as_dt(_first(row, "last_checked")),
            }
        )
    return out


def _load_domains(conn) -> list[dict]:
    if not _table_exists(conn, "domains"):
        return []
    cols = _safe_columns(conn, "domains")
    if "id" not in cols:
        return []
    rows = conn.execute(text(f"SELECT {_select('d', cols)} FROM domains d ORDER BY d.id")).mappings().all()
    return [
        {
            "id": int(row["id"]),
            "domain_name": _str(_first(row, "domain_name")) or "",
            "registrar": _str(_first(row, "registrar")),
            "renewal_date": _as_dt(_first(row, "renewal_date")),
            "team": _str(_first(row, "team")),
            "status": _str(_first(row, "status")),
            "notes": _str(_first(row, "notes")),
        }
        for row in rows
    ]


def _as_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    return None


def _remaining_days(stored: Any, valid_to: Any) -> int | None:
    remaining = _int(stored)
    if remaining is not None:
        return remaining
    expiry = valid_to.date() if isinstance(valid_to, datetime) else valid_to
    if isinstance(expiry, date):
        return (expiry - date.today()).days
    return None
