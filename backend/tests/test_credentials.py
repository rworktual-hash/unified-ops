import os
from unittest.mock import patch

import pytest

from app.services.credentials import CredentialError, resolve_private_key_path


def test_skips_placeholder_and_uses_existing_key(tmp_path):
    real = tmp_path / "id_rsa"
    real.write_text("dummy")
    with patch.dict(
        os.environ,
        {
            "CREDENTIAL_GPU_KEY_1_PATH": str(real),
            "DEFAULT_SSH_PRIVATE_KEY_PATH": "/absolute/path/to/credentials/unified_ops_ed25519",
        },
        clear=False,
    ):
        assert resolve_private_key_path("gpu_key_1") == str(real)


def test_missing_key_errors():
    with patch.dict(os.environ, {"CREDENTIAL_GPU_KEY_1_PATH": "/no/such/key"}, clear=False):
        with patch("app.services.credentials.settings") as settings:
            settings.default_ssh_private_key_path = "/absolute/path/to/credentials/unified_ops_ed25519"
            with patch("os.path.isfile", return_value=False):
                with pytest.raises(CredentialError, match="Private key file not found"):
                    resolve_private_key_path("missing_ref")


def test_null_ref_falls_back_to_gpu_key(tmp_path):
    real = tmp_path / "id_rsa"
    real.write_text("dummy")
    with patch.dict(os.environ, {"CREDENTIAL_GPU_KEY_1_PATH": str(real)}, clear=False):
        with patch("app.services.credentials.settings") as settings:
            settings.default_ssh_private_key_path = None
            assert resolve_private_key_path(None) == str(real)
