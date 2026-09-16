import unittest

from app.monitoring.backupvault_ssh_collectors import (
    parse_latest_backup,
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


if __name__ == "__main__":
    unittest.main()
