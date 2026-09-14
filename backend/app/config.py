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

    alert_mem_used_pct_warning: float = 85.0
    alert_disk_used_pct_warning: float = 85.0
    alert_disk_used_pct_critical: float = 92.0
    alert_gpu_temp_c_warning: float = 85.0

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

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
