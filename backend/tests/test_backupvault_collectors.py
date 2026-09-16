import unittest

from app.monitoring.backupvault_ssh_collectors import (
    build_app_service_cmd,
    build_backup_totals_cmd,
    build_healthcheck_cmd,
    build_last_backup_cmd,
    parse_latest_backup,
    parse_backup_totals,
    parse_mysql_replica,
    parse_mysql_status,
    parse_postgres_replica,
    parse_storage,
)


class BackupVaultParserTests(unittest.TestCase):
    def test_mysql_replica_modern(self):
        output = """
Replica_IO_Running: Yes
Replica_SQL_Running: Yes
Seconds_Behind_Source: 4
"""
        self.assertEqual(parse_mysql_replica(output), (True, True, 4))

    def test_mysql_replica_legacy(self):
        output = """
Slave_IO_Running: No
Slave_SQL_Running: Yes
Seconds_Behind_Master: NULL
"""
        self.assertEqual(parse_mysql_replica(output), (False, True, None))

    def test_mysql_status(self):
        output = "Threads_connected\t12\nSlow_queries\t5\nUptime\t900\n"
        self.assertEqual(parse_mysql_status(output), (12, 5, 900))

    def test_postgres_replica(self):
        self.assertEqual(parse_postgres_replica("t|8"), (True, 8))
        self.assertEqual(parse_postgres_replica("f|-1"), (False, None))

    def test_storage_prefers_data_mount(self):
        output = """Filesystem 1024-blocks Used Available Capacity Mounted on
/dev/a 1000 800 200 80% /
/dev/b 1000 900 100 90% /var/lib/mysql
"""
        self.assertEqual(parse_storage(output)[0:2], ("/var/lib/mysql", 90.0))

    def test_latest_backup(self):
        when, size, path = parse_latest_backup("1600000000.0|12345|/backup/a.tar")
        self.assertIsNotNone(when)
        self.assertEqual(size, 12345)
        self.assertEqual(path, "/backup/a.tar")

    def test_backup_totals(self):
        self.assertEqual(parse_backup_totals("4|123456"), (4, 123456))

    def test_safe_command_builders(self):
        self.assertIn("/srv/backupvault", build_last_backup_cmd(["/srv/backupvault"]))
        self.assertIn("/srv/backupvault", build_backup_totals_cmd(["/srv/backupvault"]))
        self.assertEqual(
            build_app_service_cmd("backupvault-worker"),
            "systemctl is-active backupvault-worker 2>/dev/null || echo inactive",
        )
        self.assertEqual(
            build_healthcheck_cmd("http://127.0.0.1:8080/health"),
            "curl -fsS --max-time 5 http://127.0.0.1:8080/health 2>/dev/null | head -c 400",
        )


if __name__ == "__main__":
    unittest.main()
