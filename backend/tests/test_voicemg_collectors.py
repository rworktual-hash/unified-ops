from app.monitoring.voicemg_ssh_collectors import _role, parse_nvidia_summary


def test_role_stt():
    assert _role("ai-stt1") == "stt"
    assert _role("ccaas-stt2") == "stt"


def test_role_vmg():
    assert _role("ai-vmg1") == "vmg"
    assert _role("QA-NewAIVMG") == "vmg"


def test_parse_nvidia_summary():
    sample = "0, 12 %, 1024 MiB, 8192 MiB\n1, 0 %, 512 MiB, 8192 MiB"
    count, summary = parse_nvidia_summary(sample)
    assert count == 2
    assert "0, 12 %" in summary
