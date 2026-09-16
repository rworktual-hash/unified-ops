from app.monitoring.infrastructure_ssh_collectors import (
    _role,
    parse_redis_info,
)


def test_role_postgres_from_name():
    assert _role("Ontology-Postgresql", "database") == "postgres"


def test_role_kafka_from_name():
    assert _role("Apache-Kafka", "nginx") == "kafka"


def test_role_mysql_database():
    assert _role("ur-db", "database") == "mysql"


def test_parse_redis_info():
    sample = """
role:master
connected_clients:42
used_memory:1048576
maxmemory:0
"""
    role, clients, mem = parse_redis_info(sample)
    assert role == "master"
    assert clients == 42
    assert mem == 1048576
