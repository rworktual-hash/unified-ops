from pathlib import Path
import re

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env into os.environ so CREDENTIAL_*_PATH vars work (not only Settings fields).
_backend_dir = Path(__file__).resolve().parents[1]
_project_root = _backend_dir.parent
load_dotenv(_project_root / ".env")
load_dotenv(_backend_dir / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "mysql+pymysql://unified_ops:unified_ops_dev@127.0.0.1:3307/unified_ops"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173"

    ssh_connect_timeout: int = 15
    ssh_command_timeout: int = 10
    ssh_gpu_command_timeout: int = 30
    ssh_strict_host_keys: bool = False
    default_ssh_private_key_path: str | None = None

    redis_url: str = "redis://127.0.0.1:6379/0"
    metrics_collect_interval_seconds: float = 300.0
    # When true, Celery Beat schedules collect_all_active_servers_task (needs Redis + worker + beat).
    metrics_scheduled_collect_enabled: bool = False

    alert_mem_used_pct_warning: float = 85.0
    alert_disk_used_pct_warning: float = 85.0
    alert_disk_used_pct_critical: float = 92.0
    alert_gpu_temp_c_warning: float = 85.0

    # Comma-separated IPs for GPU product SSH collect pilot, or * for all gpu servers.
    gpu_product_collect_ips: str = "81.17.61.148"

    allowlist_restart_services: str = ""

    llm_model: str = "worktual-gemma"
    llm_base_url: str = "http://173.234.75.166:8011/v1"
    llm_api_key: str = "dummy"
    llm_timeout_seconds: float = 120.0

    auth_enabled: bool = True
    jwt_secret: str = "change-me-in-production"
    jwt_expire_minutes: int = 60 * 24 * 7
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None

    # Optional read-only DB for campaign-db (worktual_email_campaign on 10.180.0.203)
    email_mgmt_database_url: str | None = None
    email_mgmt_events_table: str = "email_log_realtime"
    email_mgmt_col_id: str = "id"
    email_mgmt_col_time: str = "log_datetime"
    email_mgmt_col_event: str = "event_type"
    email_mgmt_col_direction: str = "direction"
    email_mgmt_col_from: str = "mail_from"
    email_mgmt_col_to: str = "mail_to"
    email_mgmt_col_subject: str = "subject"
    email_mgmt_col_status: str = "status"
    email_mgmt_col_dsn: str = "dsn"
    email_mgmt_col_queue_id: str = "queue_id"
    email_mgmt_col_host: str | None = "server"
    email_mgmt_sync_batch_size: int = 500
    # Optional: only count/sync rows where category column equals this (e.g. transactional app mail).
    email_mgmt_col_category: str | None = None
    email_mgmt_category_filter: str | None = None
    # Celery beat: read-only incremental sync (needs REDIS_URL + worker + beat restart).
    email_mgmt_scheduled_sync_enabled: bool = False
    email_mgmt_sync_interval_seconds: float = 120.0
    # Map remote host/IP values to inventory server_name: "82.113.72.84:email-mgmt-1,10.180.0.84:email-mgmt-private"
    email_mgmt_host_server_map: str = (
        "82.113.72.84:email-mgmt-1,82.113.72.80:email-mgmt-2,10.180.0.84:email-mgmt-private"
    )
    email_mgmt_default_server_name: str = "email-mgmt-1"

    # Read-only SSH insights on email gateways (queue, services, pflogsumm) — no MariaDB required.
    email_ssh_insights_enabled: bool = True
    email_ssh_command_timeout: int = 25
    # Comma-separated IPs or empty = all inventory rows with project=email.
    email_ssh_insights_ips: str = ""

    # Strictly read-only SSH status probes on BackupVault app/database hosts.
    backupvault_ssh_insights_enabled: bool = True
    backupvault_ssh_command_timeout: int = 30
    # Comma-separated IPs; empty or "*" = all project=backupvault hosts.
    backupvault_ssh_insights_ips: str = ""
    # Comma-separated absolute paths checked for newest backup file and totals.
    backupvault_backup_paths: str = "/backup,/backups,/var/backups"
    # Optional extra app units, e.g. "backupvault,backupvault-worker".
    backupvault_app_service_units: str = ""
    # Optional localhost-only health URLs, e.g. "http://127.0.0.1:8080/health".
    backupvault_local_health_urls: str = ""

    # Read-only SSH probes on project=infrastructure hosts.
    infrastructure_ssh_insights_enabled: bool = True
    infrastructure_ssh_command_timeout: int = 30
    infrastructure_ssh_insights_ips: str = ""
    infrastructure_app_service_units: str = ""
    infrastructure_local_health_urls: str = ""
    # PBX/SIP systemd units; empty = built-in defaults in collector.
    infrastructure_pbx_service_units: str = ""
    infrastructure_sip_service_units: str = ""
    infrastructure_redis_service_units: str = ""
    # Comma-separated redis-cli probes: default, /path/to.sock, 127.0.0.1:6379
    infrastructure_redis_cli_probes: str = ""
    infrastructure_kong_service_units: str = ""
    infrastructure_grafana_service_units: str = ""

    # Read-only SSH on project=voicemg hosts (VMG / STT apps).
    voicemg_ssh_insights_enabled: bool = True
    voicemg_ssh_command_timeout: int = 30
    voicemg_ssh_insights_ips: str = ""
    voicemg_app_service_units: str = ""
    voicemg_vmg_service_units: str = ""
    voicemg_stt_service_units: str = ""
    voicemg_local_health_urls: str = ""

    # Legacy portal metrics — MySQL on server-management (10.180.1.222; SSH 4204, MySQL usually 3306).
    # Use information_schema or a known database in the URL; per-stream LEGACY_*_DATABASE overrides.
    legacy_metrics_database_url: str | None = None
    legacy_metrics_sync_batch_size: int = 500
    legacy_metrics_scheduled_sync_enabled: bool = False
    legacy_metrics_sync_interval_seconds: float = 300.0
    # Optional host/IP -> inventory server_name map (same pattern as email).
    legacy_metrics_host_server_map: str = ""
    legacy_metrics_default_server_name: str | None = None

    # AI Insights / server fleet metrics (enable after inspect-legacy-metrics-db.py).
    legacy_ai_insights_sync_enabled: bool = False
    legacy_ai_insights_database: str | None = None
    legacy_ai_insights_table: str = "ai_server_metrics"
    legacy_ai_insights_col_id: str = "id"
    legacy_ai_insights_col_time: str = "timestamp"
    legacy_ai_insights_col_host: str = "server_id"
    legacy_ai_insights_metric_cols: str = (
        "cpu_utilization,memory_utilization,storage_utilization,load_average,gpu_utilization"
    )

    # BackupVault job/history metrics from legacy portal DB.
    legacy_backupvault_sync_enabled: bool = False
    legacy_backupvault_database: str | None = None
    legacy_backupvault_table: str = "backup_runs"
    legacy_backupvault_col_id: str = "id"
    legacy_backupvault_col_time: str = "started_at"
    legacy_backupvault_col_host: str = "target_id"
    legacy_backupvault_metric_cols: str = "status,file_size_bytes"

    # VoiceMG portal metrics.
    legacy_voicemg_sync_enabled: bool = False
    legacy_voicemg_database: str | None = None
    legacy_voicemg_table: str = "metrics_system"
    legacy_voicemg_col_id: str = "id"
    legacy_voicemg_col_time: str = "ts"
    legacy_voicemg_col_host: str = "server_id"
    legacy_voicemg_metric_cols: str = "cpu_pct,load1,mem_used_mb,mem_total_mb"

    # Infrastructure / server-inventory style metrics (server_inventory DB).
    legacy_infrastructure_sync_enabled: bool = False
    legacy_infrastructure_database: str | None = None
    legacy_infrastructure_table: str = "ai_server_metrics_history"
    legacy_infrastructure_col_id: str = "history_id"
    legacy_infrastructure_col_time: str = "timestamp"
    legacy_infrastructure_col_host: str = "server_id"
    legacy_infrastructure_metric_cols: str = "cpu_util,mem_util,io_wait,tcp_established"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def email_mgmt_host_map(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for part in self.email_mgmt_host_server_map.split(","):
            part = part.strip()
            if not part or ":" not in part:
                continue
            host, name = part.split(":", 1)
            out[host.strip()] = name.strip()
        return out

    @property
    def email_ssh_insights_ips_set(self) -> set[str]:
        raw = self.email_ssh_insights_ips.strip()
        if not raw or raw == "*":
            return set()
        return {p.strip() for p in raw.split(",") if p.strip()}

    @property
    def backupvault_ssh_insights_ips_set(self) -> set[str]:
        raw = self.backupvault_ssh_insights_ips.strip()
        if not raw or raw == "*":
            return set()
        return {p.strip() for p in raw.split(",") if p.strip()}

    @property
    def backupvault_backup_paths_list(self) -> list[str]:
        return self._validated_csv(
            self.backupvault_backup_paths,
            pattern=r"^/[A-Za-z0-9._/\-]+$",
        )

    @property
    def backupvault_app_service_units_list(self) -> list[str]:
        return self._validated_csv(
            self.backupvault_app_service_units,
            pattern=r"^[A-Za-z0-9@._-]+$",
        )

    @property
    def backupvault_local_health_urls_list(self) -> list[str]:
        urls = self._validated_csv(
            self.backupvault_local_health_urls,
            pattern=r"^https?://(127\.0\.0\.1|localhost)(:[0-9]{1,5})?(/[A-Za-z0-9._~/%+\-]*)?$",
        )
        return urls

    @property
    def infrastructure_ssh_insights_ips_set(self) -> set[str]:
        raw = self.infrastructure_ssh_insights_ips.strip()
        if not raw or raw == "*":
            return set()
        return {p.strip() for p in raw.split(",") if p.strip()}

    @property
    def infrastructure_app_service_units_list(self) -> list[str]:
        return self._validated_csv(
            self.infrastructure_app_service_units,
            pattern=r"^[A-Za-z0-9@._-]+$",
        )

    @property
    def infrastructure_local_health_urls_list(self) -> list[str]:
        return self._validated_csv(
            self.infrastructure_local_health_urls,
            pattern=r"^https?://(127\.0\.0\.1|localhost)(:[0-9]{1,5})?(/[A-Za-z0-9._~/%+\-]*)?$",
        )

    @property
    def infrastructure_pbx_service_units_list(self) -> list[str]:
        return self._validated_csv(
            self.infrastructure_pbx_service_units,
            pattern=r"^[A-Za-z0-9@._-]+$",
        )

    @property
    def infrastructure_sip_service_units_list(self) -> list[str]:
        return self._validated_csv(
            self.infrastructure_sip_service_units,
            pattern=r"^[A-Za-z0-9@._-]+$",
        )

    @property
    def infrastructure_redis_service_units_list(self) -> list[str]:
        return self._validated_csv(
            self.infrastructure_redis_service_units,
            pattern=r"^[A-Za-z0-9@._:-]+$",
        )

    @property
    def infrastructure_redis_cli_probes_list(self) -> list[str]:
        return self._validated_csv(
            self.infrastructure_redis_cli_probes,
            pattern=(
                r"^(default|/[A-Za-z0-9._/\-]+|(127\.0\.0\.1|localhost):[0-9]{1,5})$"
            ),
        )

    @property
    def infrastructure_kong_service_units_list(self) -> list[str]:
        return self._validated_csv(
            self.infrastructure_kong_service_units,
            pattern=r"^[A-Za-z0-9@._:-]+$",
        )

    @property
    def infrastructure_grafana_service_units_list(self) -> list[str]:
        return self._validated_csv(
            self.infrastructure_grafana_service_units,
            pattern=r"^[A-Za-z0-9@._:-]+$",
        )

    @property
    def voicemg_ssh_insights_ips_set(self) -> set[str]:
        raw = self.voicemg_ssh_insights_ips.strip()
        if not raw or raw == "*":
            return set()
        return {p.strip() for p in raw.split(",") if p.strip()}

    @property
    def voicemg_app_service_units_list(self) -> list[str]:
        return self._validated_csv(
            self.voicemg_app_service_units,
            pattern=r"^[A-Za-z0-9@._-]+$",
        )

    @property
    def voicemg_vmg_service_units_list(self) -> list[str]:
        return self._validated_csv(
            self.voicemg_vmg_service_units,
            pattern=r"^[A-Za-z0-9@._-]+$",
        )

    @property
    def voicemg_stt_service_units_list(self) -> list[str]:
        return self._validated_csv(
            self.voicemg_stt_service_units,
            pattern=r"^[A-Za-z0-9@._-]+$",
        )

    @property
    def voicemg_local_health_urls_list(self) -> list[str]:
        return self._validated_csv(
            self.voicemg_local_health_urls,
            pattern=r"^https?://(127\.0\.0\.1|localhost)(:[0-9]{1,5})?(/[A-Za-z0-9._~/%+\-]*)?$",
        )

    @property
    def legacy_metrics_host_map(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for part in self.legacy_metrics_host_server_map.split(","):
            part = part.strip()
            if not part or ":" not in part:
                continue
            host, name = part.split(":", 1)
            out[host.strip()] = name.strip()
        return out

    @staticmethod
    def _metric_cols(raw: str) -> list[str]:
        return [c.strip() for c in raw.split(",") if c.strip()]

    @property
    def legacy_ai_insights_metric_cols_list(self) -> list[str]:
        return Settings._metric_cols(self.legacy_ai_insights_metric_cols)

    @property
    def legacy_backupvault_metric_cols_list(self) -> list[str]:
        return Settings._metric_cols(self.legacy_backupvault_metric_cols)

    @property
    def legacy_voicemg_metric_cols_list(self) -> list[str]:
        return Settings._metric_cols(self.legacy_voicemg_metric_cols)

    @property
    def legacy_infrastructure_metric_cols_list(self) -> list[str]:
        return Settings._metric_cols(self.legacy_infrastructure_metric_cols)

    @staticmethod
    def _validated_csv(raw: str, *, pattern: str) -> list[str]:
        items = [item.strip() for item in raw.split(",") if item.strip()]
        out: list[str] = []
        for item in items:
            if not re.fullmatch(pattern, item):
                continue
            out.append(item)
        return out


settings = Settings()
