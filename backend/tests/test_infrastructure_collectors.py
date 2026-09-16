from app.monitoring.infrastructure_ssh_collectors import (
    _role,
    build_redis_ping_cmd,
    evaluate_redis_service,
    evaluate_telephony_service,
    parse_redis_info,
    pbx_service_units,
    redis_cli_args_from_probe,
    redis_service_units,
    sip_service_units,
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


def test_default_pbx_sip_units():
    assert "asterisk" in pbx_service_units()
    assert "kamailio" in sip_service_units()
    assert "redis-server" in redis_service_units()


def test_redis_cli_probe_args():
    assert redis_cli_args_from_probe("default") == ""
    assert redis_cli_args_from_probe("/var/run/redis/redis.sock") == (
        "-s /var/run/redis/redis.sock"
    )
    assert build_redis_ping_cmd("127.0.0.1:6379").startswith("timeout 5 redis-cli -h 127.0.0.1")


def test_evaluate_redis_pong():
    assert (
        evaluate_redis_service(
            unit_up=[False],
            pong_ok=True,
            process_count=0,
            docker_redis_containers=0,
        )
        is True
    )


def test_evaluate_telephony_process_fallback():
    assert (
        evaluate_telephony_service(
            unit_up=[False, False],
            process_count=2,
            docker_active=False,
            containers_running=0,
        )
        is True
    )


def test_evaluate_telephony_all_failed():
    assert (
        evaluate_telephony_service(
            unit_up=[False],
            process_count=0,
            docker_active=False,
            containers_running=0,
        )
        is False
    )
