from pathlib import Path

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

    # Optional read-only DB for email-management.worktual.tech (parsed mail logs)
    email_mgmt_database_url: str | None = None
    email_mgmt_events_table: str = "email_logs"
    email_mgmt_col_id: str = "id"
    email_mgmt_col_time: str = "event_time"
    email_mgmt_col_event: str = "event"
    email_mgmt_col_direction: str = "direction"
    email_mgmt_col_from: str = "from_address"
    email_mgmt_col_to: str = "to_address"
    email_mgmt_col_subject: str = "subject"
    email_mgmt_col_status: str = "status"
    email_mgmt_col_dsn: str = "dsn"
    email_mgmt_col_queue_id: str = "queue_id"
    email_mgmt_col_host: str | None = None
    email_mgmt_sync_batch_size: int = 500
    # Map remote host/IP values to inventory server_name: "82.113.72.84:email-mgmt-1,10.180.0.84:email-mgmt-private"
    email_mgmt_host_server_map: str = (
        "82.113.72.84:email-mgmt-1,82.113.72.80:email-mgmt-2,10.180.0.84:email-mgmt-private"
    )
    email_mgmt_default_server_name: str = "email-mgmt-1"

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


settings = Settings()
