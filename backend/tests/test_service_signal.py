from app.monitoring.service_signal import mysql_service_active, postgres_service_active


def test_mysql_prefers_sql_status():
    assert (
        mysql_service_active(systemd_ok=False, db_connections=10, db_uptime_seconds=None)
        is True
    )


def test_mysql_systemd_only():
    assert mysql_service_active(systemd_ok=True, db_connections=None, db_uptime_seconds=None)


def test_postgres_connections():
    assert postgres_service_active(systemd_ok=False, db_connections=5) is True
